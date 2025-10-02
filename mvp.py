import os
from dotenv import load_dotenv
import pyupbit
import requests
import pandas as pd
from openai import OpenAI
import json
import time
import logging
from datetime import datetime, timedelta
import numpy as np

# === 설정 로드 ===
def load_config():
    """설정 파일에서 설정을 로드합니다."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("config.json 파일을 찾을 수 없습니다. 기본값 사용")
        return get_default_config()
    except json.JSONDecodeError as e:
        logging.error(f"config.json 파일 파싱 오류: {e}. 기본값 사용")
        return get_default_config()

def get_default_config():
    """기본 설정값을 반환합니다."""
    return {
        "trading": {"base_trade_ratio": 0.15, "stop_loss_percent": 15, "min_trade_amount": 5000},
        "technical_analysis": {"rsi_oversold": 30, "rsi_overbought": 70, "data_period_days": 30},
        "market_conditions": {"bull_market_threshold": 10, "bear_market_threshold": -10, 
                            "fear_greed_extreme_fear": 25, "fear_greed_extreme_greed": 75},
        "coins": {
            "list": ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"],
            "target_allocation": {"KRW-BTC": 0.25, "KRW-ETH": 0.25, "KRW-SOL": 0.30, "KRW-XRP": 0.20}
        },
        "cache": {"cache_file": "news_cache.json", "cache_duration_hours": 4},
        "safety": {"min_cash_ratio": 0.15, "max_portfolio_concentration": 0.45},
        "check_intervals": {
            "extreme_volatility_threshold": 8.0, "extreme_volatility_interval": 15,
            "high_volatility_threshold": 5.0, "high_volatility_interval": 30,
            "medium_volatility_threshold": 2.0, "medium_volatility_interval": 60,
            "low_volatility_interval": 120, "default_interval": 60
        }
    }

# 설정 로드
CONFIG = load_config()

# 편의를 위한 상수 정의 (config에서 추출)
PORTFOLIO_COINS = CONFIG["coins"]["list"]
TARGET_ALLOCATION = CONFIG["coins"]["target_allocation"]
BASE_TRADE_RATIO = CONFIG["trading"]["base_trade_ratio"]
STOP_LOSS_PERCENT = CONFIG["trading"]["stop_loss_percent"]
MIN_TRADE_AMOUNT = CONFIG["trading"]["min_trade_amount"]
RSI_OVERSOLD = CONFIG["technical_analysis"]["rsi_oversold"]
RSI_OVERBOUGHT = CONFIG["technical_analysis"]["rsi_overbought"]
FEAR_GREED_EXTREME_FEAR = CONFIG["market_conditions"]["fear_greed_extreme_fear"]
FEAR_GREED_EXTREME_GREED = CONFIG["market_conditions"]["fear_greed_extreme_greed"]
DATA_PERIOD = CONFIG["technical_analysis"]["data_period_days"]
CACHE_FILE = CONFIG["cache"]["cache_file"]
CACHE_DURATION = CONFIG["cache"]["cache_duration_hours"] * 60 * 60  # 시간을 초로 변환
BULL_MARKET_THRESHOLD = CONFIG["market_conditions"]["bull_market_threshold"]
BEAR_MARKET_THRESHOLD = CONFIG["market_conditions"]["bear_market_threshold"]
MIN_CASH_RATIO = CONFIG["safety"]["min_cash_ratio"]
MAX_PORTFOLIO_CONCENTRATION = CONFIG["safety"]["max_portfolio_concentration"]

# 체크 주기 설정
CHECK_INTERVALS = CONFIG["check_intervals"]
HIGH_VOLATILITY_THRESHOLD = 5  # 5% 이상 변동성 시 고변동성



def get_portfolio_data():
    """4개 코인 포트폴리오 데이터 수집 - 다중 타임프레임"""
    portfolio_data = {}
    
    timeframes = {
        'day': DATA_PERIOD,      # 일봉 30일
        'hour4': 168,           # 4시간봉 1주일 (168시간)
        'hour1': 168            # 1시간봉 1주일
    }
    
    for ticker in PORTFOLIO_COINS:
        try:
            coin_name = ticker.split('-')[1]
            portfolio_data[coin_name] = {}
            
            for tf, count in timeframes.items():
                interval = tf.replace('hour', '')  # 'hour4' -> '4', 'hour1' -> '1'
                if tf == 'day':
                    interval = 'day'
                elif tf == 'hour4':
                    interval = 'minute240'  # 4시간 = 240분
                elif tf == 'hour1':
                    interval = 'minute60'   # 1시간 = 60분
                
                df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
                if df is not None:
                    portfolio_data[coin_name][tf] = df
                else:
                    print(f"❌ {ticker} {tf} 데이터 수집 실패")
            
            if portfolio_data[coin_name]:
                print(f"✅ {coin_name} 다중 타임프레임 데이터 수집 완료")
            
        except Exception as e:
            print(f"❌ {ticker} 오류: {e}")
    
    return portfolio_data

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_fear_greed_index():
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1")
        data = resp.json()
        return {
            "value": data['data'][0]['value'],
            "text": data['data'][0]['value_classification']
        }
    except Exception as e:
        return {"value": None, "text": None}

def get_news_headlines():
    try:
        # 캐시 파일이 있으면, 4시간 이내면 캐시 데이터 반환
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
            if time.time() - cache["timestamp"] < CACHE_DURATION:
                return cache["data"]
        # API 호출 및 캐시 저장
        news_api_key = os.getenv("NEWS_API_KEY")
        if not news_api_key:
            print("⚠️ 뉴스 API 키가 없어 뉴스 수집을 건너뜁니다.")
            return []
        
        # 포트폴리오 코인들의 뉴스 수집
        all_headlines = []
        coin_names = []
        
        # 포트폴리오 코인 이름 추출 및 검색 키워드 생성
        for ticker in PORTFOLIO_COINS:
            coin_name = ticker.split('-')[1].lower()
            if coin_name == 'btc':
                coin_names.extend(['bitcoin', 'btc'])
            elif coin_name == 'eth':
                coin_names.extend(['ethereum', 'eth'])
            elif coin_name == 'sol':
                coin_names.extend(['solana', 'sol'])
            elif coin_name == 'xrp':
                coin_names.extend(['ripple', 'xrp'])
            else:
                coin_names.append(coin_name)
        
        # 각 코인에 대해 뉴스 검색 (API 제한을 고려하여 한 번에 여러 키워드로 검색)
        search_query = " OR ".join(coin_names[:10])  # API 제한 고려하여 최대 10개 키워드
        
        resp = requests.get(f"https://newsdata.io/api/1/latest?apikey={news_api_key}&q={search_query}")
        data = resp.json()
        
        if data.get('results'):
            for item in data['results']:
                headline = item.get('title', '')
                if headline:
                    all_headlines.append(headline)
        
        # 중복 제거 및 관련성 높은 뉴스만 필터링
        unique_headlines = list(dict.fromkeys(all_headlines))  # 중복 제거
        
        with open(CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "data": unique_headlines}, f)
        
        print(f"📰 포트폴리오 코인 뉴스 수집: {len(unique_headlines)}개")
        return unique_headlines
        
    except Exception as e:
        logging.error(f"뉴스 수집 실패: {e}")
        return get_free_crypto_news()

def get_free_crypto_news():
    """무료 암호화폐 뉴스 소스 (Reddit 기반) - 포트폴리오 코인 중심"""
    try:
        url = "https://www.reddit.com/r/CryptoCurrency/hot.json?limit=25"
        headers = {'User-Agent': 'AI-Trading-Bot/1.0'}
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        headlines = []
        
        # 포트폴리오 코인 키워드 정의
        portfolio_keywords = {
            'bitcoin': ['bitcoin', 'btc', 'Bitcoin', 'BTC'],
            'ethereum': ['ethereum', 'eth', 'Ethereum', 'ETH'],
            'solana': ['solana', 'sol', 'Solana', 'SOL'],
            'ripple': ['ripple', 'xrp', 'Ripple', 'XRP']
        }
        
        if 'data' in data and 'children' in data['data']:
            for post in data['data']['children']:
                title = post['data']['title']
                score = post['data']['score']
                
                if score > 3:  # 점수 기준 낮춤 (더 많은 뉴스 수집)
                    # 포트폴리오 코인 관련 뉴스인지 확인
                    is_relevant = False
                    for coin, keywords in portfolio_keywords.items():
                        if any(keyword in title for keyword in keywords):
                            is_relevant = True
                            break
                    
                    # 일반적인 암호화폐 뉴스도 포함
                    general_crypto_keywords = ['crypto', 'cryptocurrency', 'blockchain', 'DeFi', 'NFT', 'altcoin', 'bull', 'bear', 'pump', 'dump']
                    if not is_relevant:
                        is_relevant = any(keyword.lower() in title.lower() for keyword in general_crypto_keywords)
                    
                    if is_relevant:
                        headlines.append(title)
        
        print(f"📰 Reddit 뉴스 수집: {len(headlines)}개 (포트폴리오 코인 중심)")
        return headlines[:15]  # 상위 15개로 증가
        
    except Exception as e:
        logging.warning(f"무료 뉴스 수집 실패: {e}")
        return []

def analyze_news_sentiment(headlines):
    """뉴스 감정 분석 및 긴급 이벤트 감지 - 포트폴리오 코인 특화"""
    if not headlines:
        return {"sentiment": "neutral", "emergency": False, "events": []}
    
    # 긴급 키워드 정의 (포트폴리오 코인 추가)
    emergency_negative = ["hack", "hacked", "stolen", "exploit", "attack", "collapse", "bankrupt", "scam", "rugpull", "crash", "dump"]
    emergency_positive = ["ETF approved", "approved", "institutional", "Tesla", "Microsoft", "MicroStrategy", "adoption", "pump", "moon", "breakthrough"]
    regulatory_risk = ["SEC", "ban", "illegal", "lawsuit", "investigation", "probe", "fine", "regulatory"]
    
    # 포트폴리오 코인별 특별 이벤트
    coin_specific_positive = {
        'bitcoin': ['halving', 'mining', 'store of value', 'digital gold'],
        'ethereum': ['merge', 'staking', 'defi', 'smart contract', 'gas fee reduction'],
        'solana': ['fast transaction', 'ecosystem growth', 'nft', 'validator'],
        'ripple': ['payment', 'bank partnership', 'cross border', 'legal victory']
    }
    
    coin_specific_negative = {
        'bitcoin': ['energy consumption', 'mining ban'],
        'ethereum': ['gas fee', 'scalability issue'],
        'solana': ['network outage', 'downtime'],
        'ripple': ['sec lawsuit', 'delisting']
    }
    
    sentiment_score = 0
    emergency_events = []
    coin_mentions = {'bitcoin': 0, 'ethereum': 0, 'solana': 0, 'ripple': 0}
    
    for headline in headlines:
        headline_lower = headline.lower()
        
        # 긴급 부정 이벤트
        for keyword in emergency_negative:
            if keyword in headline_lower:
                sentiment_score -= 3
                emergency_events.append(f"🚨 위험: {keyword}")
        
        # 긴급 긍정 이벤트  
        for keyword in emergency_positive:
            if keyword in headline_lower:
                sentiment_score += 2
                emergency_events.append(f"🚀 호재: {keyword}")
        
        # 규제 리스크
        for keyword in regulatory_risk:
            if keyword in headline_lower:
                sentiment_score -= 1
                emergency_events.append(f"⚖️ 규제: {keyword}")
        
        # 포트폴리오 코인별 특별 이벤트 분석
        for coin, positive_keywords in coin_specific_positive.items():
            if any(kw in headline_lower for kw in positive_keywords):
                sentiment_score += 1
                coin_mentions[coin] += 1
                emergency_events.append(f"💎 {coin.upper()} 호재")
        
        for coin, negative_keywords in coin_specific_negative.items():
            if any(kw in headline_lower for kw in negative_keywords):
                sentiment_score -= 1
                coin_mentions[coin] += 1
                emergency_events.append(f"⚠️ {coin.upper()} 악재")
        
        # 일반적인 코인 언급 체크
        coin_keywords = {
            'bitcoin': ['bitcoin', 'btc'],
            'ethereum': ['ethereum', 'eth'],
            'solana': ['solana', 'sol'],
            'ripple': ['ripple', 'xrp']
        }
        
        for coin, keywords in coin_keywords.items():
            if any(kw in headline_lower for kw in keywords):
                coin_mentions[coin] += 1
    
    # 감정 분류
    if sentiment_score >= 4:
        sentiment = "very_bullish"
    elif sentiment_score >= 2:
        sentiment = "bullish"
    elif sentiment_score <= -4:
        sentiment = "very_bearish"
    elif sentiment_score <= -2:
        sentiment = "bearish"
    else:
        sentiment = "neutral"
    
    # 가장 많이 언급된 코인 정보 추가
    most_mentioned_coin = max(coin_mentions, key=coin_mentions.get) if max(coin_mentions.values()) > 0 else None
    
    return {
        "sentiment": sentiment,
        "score": sentiment_score,
        "emergency": abs(sentiment_score) >= 3,
        "events": emergency_events[:5],  # 상위 5개로 증가
        "coin_mentions": coin_mentions,
        "focus_coin": most_mentioned_coin
    }



def analyze_multi_timeframe(coin_data):
    """다중 타임프레임 종합 분석"""
    analysis = {}
    
    for timeframe, df in coin_data.items():
        if df is not None and len(df) >= 20:
            rsi = calculate_rsi(df['close']).iloc[-1]
            ma5 = df['close'].rolling(window=5).mean().iloc[-1]
            ma20 = df['close'].rolling(window=20).mean().iloc[-1]
            
            # 트렌드 강도 계산
            trend_strength = "neutral"
            if ma5 > ma20 * 1.02:  # 2% 이상 차이
                trend_strength = "strong_bullish"
            elif ma5 > ma20:
                trend_strength = "bullish"
            elif ma5 < ma20 * 0.98:
                trend_strength = "strong_bearish"
            elif ma5 < ma20:
                trend_strength = "bearish"
            
            analysis[timeframe] = {
                "rsi": rsi,
                "ma5": ma5,
                "ma20": ma20,
                "trend_strength": trend_strength,
                "current_price": df['close'].iloc[-1],
                "volume_avg": df['volume'][-5:].mean()
            }
    
    return analysis

def make_portfolio_summary(portfolio_data, fng, news):
    """포트폴리오 전체 요약 생성 - 다중 타임프레임 지원"""
    portfolio_summary = {
        "coins": {},
        "fear_greed_index": fng,
        "news_headlines": news,
        "timestamp": time.time()
    }
    
    # 각 코인별 다중 타임프레임 분석
    for coin, timeframe_data in portfolio_data.items():
        if not timeframe_data:
            continue
            
        # 일봉 기준 기본 정보
        day_data = timeframe_data.get('day')
        if day_data is not None and len(day_data) >= 20:
            # 다중 타임프레임 분석
            multi_tf_analysis = analyze_multi_timeframe(timeframe_data)
            
            # 트렌드 일치도 계산
            trend_alignment = calculate_trend_alignment(multi_tf_analysis)
            
            portfolio_summary["coins"][coin] = {
                "current_price": day_data['close'].iloc[-1],
                "recent_close": day_data['close'][-5:].tolist(),
                "change_rate": (day_data['close'].iloc[-1] - day_data['close'].iloc[-5]) / day_data['close'].iloc[-5] * 100,
                "volume": day_data['volume'][-5:].mean(),
                "multi_timeframe": multi_tf_analysis,
                "trend_alignment": trend_alignment,
                # 레거시 호환성
                "rsi": multi_tf_analysis.get('day', {}).get('rsi', 50),
                "ma5": multi_tf_analysis.get('day', {}).get('ma5', 0),
                "ma20": multi_tf_analysis.get('day', {}).get('ma20', 0)
            }
    
    # 전체 시장 상황 분석 추가
    portfolio_summary["market_condition"] = analyze_market_condition(portfolio_summary)
    
    return portfolio_summary

def analyze_market_condition(portfolio_summary):
    """전체 시장 상황 분석"""
    if not portfolio_summary.get("coins"):
        return {"condition": "unknown", "confidence": 0}
    
    # 포트폴리오 평균 변화율 계산
    total_change = 0
    total_volatility = 0
    coin_count = 0
    bullish_coins = 0
    bearish_coins = 0
    
    for coin, data in portfolio_summary["coins"].items():
        change_rate = data.get("change_rate", 0)
        total_change += change_rate
        total_volatility += abs(change_rate)
        coin_count += 1
        
        # 트렌드 정렬 분석
        alignment = data.get("trend_alignment", "mixed_signals")
        if "bullish" in alignment:
            bullish_coins += 1
        elif "bearish" in alignment:
            bearish_coins += 1
    
    if coin_count == 0:
        return {"condition": "unknown", "confidence": 0}
    
    avg_change = total_change / coin_count
    avg_volatility = total_volatility / coin_count
    
    # 공포탐욕지수 고려
    fng_value = portfolio_summary.get("fear_greed_index", {}).get("value", 50)
    
    # 시장 상황 판단
    market_condition = "sideways"  # 기본값
    confidence = 0.5
    
    if avg_change > BULL_MARKET_THRESHOLD and bullish_coins > bearish_coins:
        if fng_value > FEAR_GREED_EXTREME_GREED:
            market_condition = "bull_market_overheated"
            confidence = 0.8
        else:
            market_condition = "bull_market"
            confidence = 0.7
    elif avg_change < BEAR_MARKET_THRESHOLD and bearish_coins > bullish_coins:
        if fng_value < FEAR_GREED_EXTREME_FEAR:
            market_condition = "bear_market_oversold"
            confidence = 0.8
        else:
            market_condition = "bear_market"
            confidence = 0.7
    elif avg_volatility > HIGH_VOLATILITY_THRESHOLD:
        market_condition = "high_volatility"
        confidence = 0.6
    
    return {
        "condition": market_condition,
        "confidence": confidence,
        "avg_change": avg_change,
        "avg_volatility": avg_volatility,
        "bullish_coins": bullish_coins,
        "bearish_coins": bearish_coins,
        "fng_value": fng_value
    }

def calculate_trend_alignment(multi_tf_analysis):
    """다중 타임프레임 트렌드 일치도 계산"""
    bullish_count = 0
    bearish_count = 0
    total_timeframes = len(multi_tf_analysis)
    
    for tf_name, analysis in multi_tf_analysis.items():
        trend = analysis.get('trend_strength', 'neutral')
        if 'bullish' in trend:
            bullish_count += 2 if 'strong' in trend else 1
        elif 'bearish' in trend:
            bearish_count += 2 if 'strong' in trend else 1
    
    if bullish_count > bearish_count * 1.5:
        return "strong_bullish_alignment"
    elif bullish_count > bearish_count:
        return "bullish_alignment"
    elif bearish_count > bullish_count * 1.5:
        return "strong_bearish_alignment"
    elif bearish_count > bullish_count:
        return "bearish_alignment"
    else:
        return "mixed_signals"



def get_portfolio_ai_signals(portfolio_summary, max_retries=3):
    """포트폴리오 기반 AI 신호 시스템 - Rate Limiting 포함"""
    client = OpenAI()
    
    # 개선된 포트폴리오 전용 프롬프트 - 뉴스/이벤트 반영 + 리스크 관리 강화
    prompt = (
        "You're a cryptocurrency portfolio trading AI expert managing a diversified portfolio of BTC, ETH, SOL, and XRP. "
        "Your strategy focuses on: "
        "1. Event-driven analysis with real-time news sentiment integration "
        "2. Multi-timeframe technical analysis with adaptive market regime recognition "
        "3. Enhanced momentum trading with volatility-adjusted position sizing "
        "4. Dynamic correlation analysis and intelligent diversification "
        "5. Explicit risk management with stop-loss and take-profit guidance "
        "\n"
        "🚨 CRITICAL: Analyze news headlines for market-moving events with severity weighting: "
        "- Regulatory developments (SEC/government approvals, bans, lawsuits, legal clarity) "
        "- Institutional adoption (ETF flows, corporate treasury adds, whale movements) "
        "- Technical/security events (network upgrades, hacks, outages) "
        "- Macro catalysts (Fed policy, inflation data, geopolitical tensions) "
        "\n"
        "For each coin, provide comprehensive analysis: "
        "- Signal: STRONG_BUY, BUY, HOLD, SELL, EMERGENCY_SELL "
        "- Confidence: 0.0-1.0 (weight news impact + technical confluence) "
        "- Reasoning: Combine news sentiment + technical analysis + market context "
        "- Stop_Loss: Suggested downside risk protection (percentage) "
        "- Take_Profit: Suggested profit-taking level (percentage) "
        "- Recommended_Size: Allocation ratio based on signal confidence and volatility "
        "\n"
        f"Enhanced Guidelines: "
        f"📊 Technical Analysis: "
        f"- RSI < {RSI_OVERSOLD}: Strong oversold (BUY if no negative news) "
        f"- RSI > {RSI_OVERBOUGHT}: Overbought (SELL/HOLD, reduce positions) "
        f"- Multi-timeframe alignment: Confirm day/4hr/1hr trend direction "
        f"- Volume validation: >150% average confirms breakouts/breakdowns "
        f"📰 News Sentiment Integration: "
        f"- Positive regulatory/institutional news: Increase BUY confidence +0.2 "
        f"- Negative regulatory/security news: Increase SELL confidence +0.3 "
        f"- Major partnerships/upgrades: Boost STRONG_BUY signals "
        f"📈 Market Psychology: "
        f"- Fear & Greed < {FEAR_GREED_EXTREME_FEAR}: Contrarian opportunity (if no bad news) "
        f"- Fear & Greed > {FEAR_GREED_EXTREME_GREED}: Distribution zone (take profits) "
        f"- High market correlation (>0.8): Reduce diversification assumptions "
        f"⚡ Enhanced Signals: "
        f"- EMERGENCY_SELL: Major hacks, severe regulatory crackdowns, 15%+ drops with bad news "
        f"- STRONG_BUY: ETF approvals + oversold + volume surge + positive news confluence "
        f"- Adapt to volatility: High vol = smaller positions but faster reactions "
        "\n"
        "Please provide analysis in JSON format with enhanced reasoning and risk management: "
        "{"
        "  \"BTC\": {\"signal\": \"STRONG_BUY\", \"confidence\": 0.9, \"reason\": \"ETF inflow surge + RSI(25) oversold + bullish MA cross + institutional FOMO\", \"stop_loss\": -0.05, \"take_profit\": 0.12, \"recommended_size\": 0.25}, "
        "  \"ETH\": {\"signal\": \"HOLD\", \"confidence\": 0.6, \"reason\": \"Neutral technicals, awaiting staking rewards clarity\", \"stop_loss\": -0.03, \"take_profit\": 0.08, \"recommended_size\": 0.25}, "
        "  \"SOL\": {\"signal\": \"BUY\", \"confidence\": 0.8, \"reason\": \"Ecosystem growth + volume breakout + oversold bounce\", \"stop_loss\": -0.04, \"take_profit\": 0.1, \"recommended_size\": 0.3}, "
        "  \"XRP\": {\"signal\": \"SELL\", \"confidence\": 0.7, \"reason\": \"Regulatory uncertainty + overbought RSI(75) + distribution pattern\", \"stop_loss\": -0.02, \"take_profit\": 0.07, \"recommended_size\": 0.2}"
        "}"
    )
    
    # Rate Limiting과 재시도 로직
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(portfolio_summary)}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # 더 일관된 신호를 위해 낮춤
                max_tokens=800
            )
            
            ai_signals = json.loads(response.choices[0].message.content)
            print("🤖 AI 포트폴리오 분석 완료")
            
            # AI 사용량 및 비용 계산 (GPT-4o-mini 요금)
            tokens_used = response.usage.total_tokens
            cost_usd = (response.usage.prompt_tokens * 0.00015 + response.usage.completion_tokens * 0.0006) / 1000
            cost_krw = cost_usd * 1300  # 대략적인 환율
            
            print(f"  토큰 사용량: {tokens_used:,}개")
            print(f"  비용: ${cost_usd:.4f} (약 {cost_krw:.0f}원)")
            
            # AI 신호별 상세 로깅
            cost_info = {
                'tokens_used': tokens_used,
                'cost_usd': cost_usd,
                'cost_krw': cost_krw,
                'model': 'gpt-4o-mini'
            }
            
            # 신호 요약 출력 및 개별 로깅 (리스크 관리 정보 포함)
            for coin, signal_data in ai_signals.items():
                signal = signal_data.get('signal', 'HOLD')
                confidence = signal_data.get('confidence', 0.5)
                reason = signal_data.get('reason', 'No reason provided')
                stop_loss = signal_data.get('stop_loss', 0)
                take_profit = signal_data.get('take_profit', 0)
                recommended_size = signal_data.get('recommended_size', 0)
                
                print(f"  {coin}: {signal} ({confidence:.1%})")
                if stop_loss or take_profit or recommended_size:
                    risk_info = []
                    if stop_loss: risk_info.append(f"SL: {stop_loss:+.1%}")
                    if take_profit: risk_info.append(f"TP: {take_profit:+.1%}")
                    if recommended_size: risk_info.append(f"Size: {recommended_size:.1%}")
                    print(f"    📊 {' | '.join(risk_info)}")
                
                # 개별 코인별 AI 신호 상세 로깅
                try:
                    market_context = portfolio_summary.get('coins', {}).get(coin, {})
                    log_ai_signal_detailed(coin, signal_data, market_context, cost_info)
                except Exception as e:
                    logging.error(f"AI 신호 로깅 실패 ({coin}): {e}")
                
                # 비용 정보를 신호 데이터에 추가
                signal_data['tokens_used'] = tokens_used
                signal_data['cost'] = cost_krw
            
            return ai_signals
            
        except Exception as e:
            print(f"❌ AI API 호출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"⏰ 5초 후 재시도...")
                time.sleep(5)
            else:
                print(f"❌ 모든 재시도 실패, 기본값 사용")
                # 오류 시 안전한 기본값 반환
                default_signals = {}
                for coin in portfolio_summary.get('coins', {}):
                    default_signals[coin] = {"signal": "HOLD", "confidence": 0.5, "reason": "AI error - default hold"}
                return default_signals



def check_cash_shortage_rebalance(upbit, min_cash_ratio=None):
    """현금 부족 시 자동 리밸런싱 - 수익 코인 우선 매도"""
    if min_cash_ratio is None:
        min_cash_ratio = MIN_CASH_RATIO
    
    try:
        krw_balance = upbit.get_balance("KRW")
        total_portfolio_value = krw_balance
        coin_data = []
        
        # 전체 포트폴리오 가치 및 수익률 계산
        for ticker in PORTFOLIO_COINS:
            coin = ticker.split('-')[1]
            balance = upbit.get_balance(ticker)
            if balance > 0:
                current_price = pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['bid_price']
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                coin_value = balance * current_price
                total_portfolio_value += coin_value
                
                # 수익률 계산
                profit_percent = 0
                if avg_buy_price > 0:
                    profit_percent = ((current_price - avg_buy_price) / avg_buy_price) * 100
                
                coin_data.append({
                    'coin': coin,
                    'ticker': ticker,
                    'balance': balance,
                    'current_price': current_price,
                    'value': coin_value,
                    'profit_percent': profit_percent,
                    'avg_buy_price': avg_buy_price
                })
        
        # 현금 비율 체크
        cash_ratio = krw_balance / total_portfolio_value if total_portfolio_value > 0 else 0
        
        if cash_ratio < min_cash_ratio:  # 현금이 15% 미만일 때
            print(f"🚨 현금 부족 감지! 현재 현금 비율: {cash_ratio:.1%}")
            print("💸 스마트 리밸런싱 실행...")
            
            # 수익 나는 코인부터 매도 (수익률 높은 순)
            profitable_coins = [c for c in coin_data if c['profit_percent'] > 3]  # 3% 이상 수익
            profitable_coins.sort(key=lambda x: x['profit_percent'], reverse=True)
            
            if profitable_coins:
                # 가장 수익률 높은 코인의 30% 매도
                target_coin = profitable_coins[0]
                sell_ratio = 0.3
                sell_amount = target_coin['balance'] * sell_ratio
                
                result = upbit.sell_market_order(target_coin['ticker'], sell_amount)
                if result:
                    sell_value = sell_amount * target_coin['current_price']
                    print(f"  ✅ {target_coin['coin']} 수익실현 매도: {sell_amount:.6f}개")
                    print(f"     수익률: {target_coin['profit_percent']:+.1f}% | 금액: {sell_value:,.0f}원")
                    return True
            else:
                # 수익 코인이 없으면 가장 작은 손실 코인 매도
                loss_coins = [c for c in coin_data if c['profit_percent'] <= 0]
                if loss_coins:
                    loss_coins.sort(key=lambda x: x['profit_percent'], reverse=True)  # 손실 적은 순
                    target_coin = loss_coins[0]
                    sell_ratio = 0.2  # 20%만 매도 (손실 최소화)
                    sell_amount = target_coin['balance'] * sell_ratio
                    
                    result = upbit.sell_market_order(target_coin['ticker'], sell_amount)
                    if result:
                        sell_value = sell_amount * target_coin['current_price']
                        print(f"  ⚠️ {target_coin['coin']} 현금확보 매도: {sell_amount:.6f}개")
                        print(f"     손실률: {target_coin['profit_percent']:+.1f}% | 금액: {sell_value:,.0f}원")
                        return True
                    
        return False
        
    except Exception as e:
        print(f"❌ 현금 부족 체크 오류: {e}")
        return False

def check_portfolio_concentration_limits(upbit, max_single_position=None):
    """포트폴리오 집중도 제한 체크 - 45% 초과 시 매도"""
    if max_single_position is None:
        max_single_position = MAX_PORTFOLIO_CONCENTRATION
    
    try:
        krw_balance = upbit.get_balance("KRW")
        total_portfolio_value = krw_balance
        coin_data = []
        
        # 포트폴리오 분석
        for ticker in PORTFOLIO_COINS:
            coin = ticker.split('-')[1]
            balance = upbit.get_balance(ticker)
            if balance > 0:
                current_price = pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['bid_price']
                coin_value = balance * current_price
                total_portfolio_value += coin_value
                coin_data.append({
                    'coin': coin,
                    'ticker': ticker,
                    'balance': balance,
                    'value': coin_value,
                    'current_price': current_price
                })
        
        # 비중 계산 및 초과 체크
        for coin_info in coin_data:
            coin_ratio = coin_info['value'] / total_portfolio_value if total_portfolio_value > 0 else 0
            
            if coin_ratio > max_single_position:
                print(f"⚖️ {coin_info['coin']} 비중 초과 감지: {coin_ratio:.1%}")
                
                # 목표 비중(40%)까지 매도
                target_ratio = 0.4
                excess_ratio = coin_ratio - target_ratio
                sell_ratio = excess_ratio / coin_ratio  # 초과분 비율
                
                if sell_ratio > 0.05:  # 5% 이상 초과시만 실행
                    sell_amount = coin_info['balance'] * sell_ratio
                    result = upbit.sell_market_order(coin_info['ticker'], sell_amount)
                    
                    if result:
                        sell_value = sell_amount * coin_info['current_price']
                        print(f"  ✅ {coin_info['coin']} 집중도 해소: {coin_ratio:.1%} → {target_ratio:.0%} 목표")
                        print(f"     매도량: {sell_amount:.6f}개 | 금액: {sell_value:,.0f}원")
                        return True
                        
        return False
        
    except Exception as e:
        print(f"❌ 포트폴리오 집중도 체크 오류: {e}")
        return False

def check_portfolio_rebalancing(upbit, deviation_threshold=0.15):
    """목표 비율 대비 편차가 클 때 리밸런싱 실행"""
    try:
        krw_balance = upbit.get_balance("KRW")
        total_portfolio_value = krw_balance
        current_allocation = {}
        
        # 현재 포트폴리오 비율 계산
        for ticker in PORTFOLIO_COINS:
            balance = upbit.get_balance(ticker)
            if balance > 0:
                current_price = pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['bid_price']
                coin_value = balance * current_price
                total_portfolio_value += coin_value
                current_allocation[ticker] = coin_value
            else:
                current_allocation[ticker] = 0
        
        if total_portfolio_value <= 0:
            return False
        
        # 현재 비율을 백분율로 변환
        for ticker in current_allocation:
            current_allocation[ticker] = current_allocation[ticker] / total_portfolio_value
        
        # 목표 비율과 현재 비율 비교
        rebalance_needed = False
        rebalance_actions = []
        
        for ticker in PORTFOLIO_COINS:
            current_ratio = current_allocation[ticker]
            target_ratio = TARGET_ALLOCATION[ticker]
            deviation = abs(current_ratio - target_ratio)
            
            if deviation > deviation_threshold:
                rebalance_needed = True
                coin = ticker.split('-')[1]
                
                if current_ratio > target_ratio:
                    # 목표보다 많이 보유 -> 매도 필요
                    excess_ratio = current_ratio - target_ratio
                    rebalance_actions.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'coin': coin,
                        'current': f"{current_ratio:.1%}",
                        'target': f"{target_ratio:.1%}",
                        'excess': f"{excess_ratio:.1%}"
                    })
                else:
                    # 목표보다 적게 보유 -> 매수 필요
                    shortage_ratio = target_ratio - current_ratio
                    rebalance_actions.append({
                        'action': 'BUY',
                        'ticker': ticker,
                        'coin': coin,
                        'current': f"{current_ratio:.1%}",
                        'target': f"{target_ratio:.1%}",
                        'shortage': f"{shortage_ratio:.1%}"
                    })
        
        if rebalance_needed:
            print(f"\n🔄 포트폴리오 리밸런싱 필요 (편차 {deviation_threshold:.0%} 초과)")
            print("=" * 60)
            
            for action in rebalance_actions:
                if action['action'] == 'SELL':
                    print(f"📉 {action['coin']}: {action['current']} → {action['target']} (과보유 {action['excess']})")
                else:
                    print(f"📈 {action['coin']}: {action['current']} → {action['target']} (부족 {action['shortage']})")
            
            # 실제 리밸런싱 실행 (매도 먼저, 매수 나중)
            sell_proceeds = 0
            
            # 1단계: 과보유 코인 매도
            for action in rebalance_actions:
                if action['action'] == 'SELL':
                    ticker = action['ticker']
                    current_balance = upbit.get_balance(ticker)
                    
                    if current_balance > 0:
                        # 과보유 비율만큼 매도
                        current_ratio = current_allocation[ticker]
                        target_ratio = TARGET_ALLOCATION[ticker]
                        sell_ratio = (current_ratio - target_ratio) / current_ratio
                        sell_amount = current_balance * sell_ratio
                        
                        if sell_amount > 0:
                            result = upbit.sell_market_order(ticker, sell_amount)
                            if result:
                                print(f"✅ {action['coin']} 리밸런싱 매도: {sell_amount:.6f}")
                                sell_proceeds += sell_amount * pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['bid_price']
                            else:
                                print(f"❌ {action['coin']} 리밸런싱 매도 실패")
            
            # 잠깐 대기 (거래 처리 시간)
            time.sleep(2)
            
            # 2단계: 부족한 코인 매수
            if sell_proceeds > 0:
                updated_krw = upbit.get_balance("KRW")
                
                for action in rebalance_actions:
                    if action['action'] == 'BUY':
                        ticker = action['ticker']
                        current_ratio = current_allocation[ticker]
                        target_ratio = TARGET_ALLOCATION[ticker]
                        shortage_ratio = target_ratio - current_ratio
                        
                        # 부족한 비율만큼 매수 금액 계산
                        buy_amount = total_portfolio_value * shortage_ratio
                        
                        if buy_amount >= MIN_TRADE_AMOUNT and updated_krw >= buy_amount:
                            result = upbit.buy_market_order(ticker, buy_amount)
                            if result:
                                print(f"✅ {action['coin']} 리밸런싱 매수: {buy_amount:,.0f}원")
                                updated_krw -= buy_amount
                            else:
                                print(f"❌ {action['coin']} 리밸런싱 매수 실패")
            
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ 포트폴리오 리밸런싱 오류: {e}")
        return False

def check_stop_loss(upbit, stop_loss_percent=STOP_LOSS_PERCENT):
    """손절매 로직 - 15% 이상 손실 시 매도"""
    coins = [coin.split('-')[1] for coin in PORTFOLIO_COINS]
    stop_loss_executed = False
    
    for coin in coins:
        ticker = f"KRW-{coin}"
        try:
            current_balance = upbit.get_balance(ticker)
            if current_balance > 0:
                # 평균 매수가 조회
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                current_price = pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['bid_price']
                
                if avg_buy_price > 0:
                    loss_percent = ((avg_buy_price - current_price) / avg_buy_price) * 100
                    
                    if loss_percent >= stop_loss_percent:
                        print(f"🚨 {coin} 손절매 실행: {loss_percent:.1f}% 손실")
                        result = upbit.sell_market_order(ticker, current_balance)
                        if result:
                            print(f"  ✅ {coin} 손절매 완료")
                            stop_loss_executed = True
                        else:
                            print(f"  ❌ {coin} 손절매 실패")
        except Exception as e:
            print(f"  ❌ {coin} 손절매 확인 오류: {e}")
    
    return stop_loss_executed

def calculate_dynamic_position_size(market_condition, base_ratio=BASE_TRADE_RATIO):
    """시장 상황에 따른 동적 포지션 사이징 - 강세장 기회 포착 강화"""
    condition = market_condition.get("condition", "sideways")
    confidence = market_condition.get("confidence", 0.5)
    avg_change = market_condition.get("avg_change", 0)
    
    # 시장 상황별 리스크 조정 - 보수성 완화
    risk_multiplier = 1.0
    
    if condition == "bull_market":
        if abs(avg_change) > 15:  # 강한 상승 모멘텀
            risk_multiplier = 1.5  # 기존 1.2 → 1.5로 증가
            print("🚀 강력한 상승세 감지 - 공격적 포지션 증가")
        else:
            risk_multiplier = 1.3  # 기존 1.2 → 1.3으로 증가
    elif condition == "bull_market_overheated":
        risk_multiplier = 0.8  # 기존 0.7 → 0.8로 완화 (기회 상실 방지)
        print("🔥 과열 감지하지만 선별적 참여 유지")
    elif condition == "bear_market":
        risk_multiplier = 0.6  # 약세장 유지
    elif condition == "bear_market_oversold":
        risk_multiplier = 1.0  # 기존 0.9 → 1.0으로 기회 포착 강화
        print("💎 과매도 반등 기회 - 정상 포지션")
    elif condition == "high_volatility":
        # 방향성 있는 고변동성은 참여, 무방향은 보수적
        if abs(avg_change) > 10:
            risk_multiplier = 0.7  # 기존 0.5 → 0.7로 완화
            print("⚡ 방향성 있는 고변동성 - 제한적 참여")
        else:
            risk_multiplier = 0.5  # 무방향 고변동성은 여전히 보수적
    
    # 신뢰도에 따른 추가 조정 - 범위 확대
    confidence_multiplier = 0.6 + (confidence * 0.6)  # 기존 0.5~1.0 → 0.6~1.2로 확대
    
    adjusted_ratio = base_ratio * risk_multiplier * confidence_multiplier
    return min(adjusted_ratio, base_ratio * 2.0)  # 기존 1.5배 → 2.0배로 상한 확대

def calculate_performance_metrics(upbit, portfolio_summary):
    """포트폴리오 성과 지표 계산"""
    try:
        # 현재 보유 자산 조회
        krw_balance = upbit.get_balance("KRW")
        total_value = krw_balance
        coin_values = {}
        
        for coin in [c.split('-')[1] for c in PORTFOLIO_COINS]:
            ticker = f"KRW-{coin}"
            balance = upbit.get_balance(ticker)
            
            if balance > 0:
                current_price = portfolio_summary.get("coins", {}).get(coin, {}).get("current_price", 0)
                coin_value = balance * current_price
                total_value += coin_value
                coin_values[coin] = {
                    "balance": balance,
                    "value": coin_value,
                    "percentage": 0  # 나중에 계산
                }
        
        # 비중 계산
        for coin in coin_values:
            coin_values[coin]["percentage"] = coin_values[coin]["value"] / total_value * 100
        
        return {
            "total_value": total_value,
            "krw_balance": krw_balance,
            "coin_values": coin_values,
            "krw_percentage": krw_balance / total_value * 100 if total_value > 0 else 0
        }
        
    except Exception as e:
        logging.error(f"성과 계산 오류: {e}")
        return None

def print_performance_summary(performance):
    """성과 요약 출력"""
    if not performance:
        print("❌ 성과 데이터를 불러올 수 없습니다.")
        return
    
    print(f"\n💼 포트폴리오 현황:")
    print(f"총 자산: {performance['total_value']:,.0f}원")
    print(f"현금 비중: {performance['krw_percentage']:.1f}% ({performance['krw_balance']:,.0f}원)")
    
    print(f"\n🪙 코인별 보유 현황:")
    for coin, data in performance['coin_values'].items():
        print(f"  {coin}: {data['percentage']:.1f}% ({data['value']:,.0f}원)")
    
    # 간단한 알림 시스템
    check_performance_alerts(performance)

def check_performance_alerts(performance):
    """성과 기반 알림 시스템 - 강화된 버전"""
    alerts = []
    
    # 현금 비중 체크
    krw_pct = performance['krw_percentage']
    if krw_pct > 70:
        alerts.append("🔔 현금 비중이 70%를 초과했습니다. 투자 기회를 검토해보세요.")
    elif krw_pct < 10:
        alerts.append("🚨 현금 비중이 10% 미만입니다. 리밸런싱이 필요할 수 있습니다.")
    
    # 포트폴리오 집중도 체크
    for coin, data in performance['coin_values'].items():
        if data['percentage'] > 45:
            alerts.append(f"⚠️ {coin} 비중 위험: {data['percentage']:.1f}% (45% 초과)")
        elif data['percentage'] > 35:
            alerts.append(f"🔶 {coin} 비중 주의: {data['percentage']:.1f}% (35% 초과)")
    
    # 총 자산 체크
    total_value = performance['total_value']
    if total_value < 200000:  # 20만원 미만
        alerts.append(f"📉 총 자산 감소 주의: {total_value:,.0f}원 (초기 25만원 대비)")
    
    # 현금 절대액 체크
    krw_balance = performance['krw_balance']
    if krw_balance < 30000:  # 3만원 미만
        alerts.append(f"💸 현금 부족 경고: {krw_balance:,.0f}원 (추가 매수 어려움)")
    
    # 알림 출력
    if alerts:
        print(f"\n🚨 스마트 알림:")
        for alert in alerts:
            print(f"  {alert}")
            logging.warning(alert)
    else:
        print(f"\n✅ 포트폴리오 상태 양호")
        print(f"  현금: {krw_pct:.1f}% | 최대비중: {max([d['percentage'] for d in performance['coin_values'].values()], default=0):.1f}%")

def execute_portfolio_trades(ai_signals, upbit, portfolio_summary, cycle_count=0, base_trade_ratio=BASE_TRADE_RATIO):
    """포트폴리오 기반 스마트 매매 실행 - 시장 상황 고려 + 안전장치"""
    print(f"\n💰 포트폴리오 매매 실행 시작 (기본 비율: {base_trade_ratio:.1%})")
    
    # 1. 손절매 확인
    print("🛡️ 손절매 확인 중...")
    stop_loss_executed = check_stop_loss(upbit)
    
    # 2. 현금 부족 체크 (신규 추가)
    print("💰 현금 비율 체크 중...")
    cash_rebalance_executed = check_cash_shortage_rebalance(upbit)  # config에서 설정한 비율 미만 시 매도
    
    # 3. 포트폴리오 집중도 체크 (신규 추가) 
    print("📊 포트폴리오 집중도 체크 중...")
    concentration_rebalance_executed = check_portfolio_concentration_limits(upbit)  # config에서 설정한 비율 초과 시 매도
    
    # 4. 포트폴리오 리밸런싱 (매 20사이클마다)
    portfolio_rebalance_executed = False
    if cycle_count % 20 == 0:
        print("⚖️ 포트폴리오 리밸런싱 체크 중...")
        portfolio_rebalance_executed = check_portfolio_rebalancing(upbit, deviation_threshold=0.15)  # 15% 편차 시 리밸런싱
    
    if stop_loss_executed or cash_rebalance_executed or concentration_rebalance_executed or portfolio_rebalance_executed:
        print("⚠️ 안전장치 실행으로 인해 이번 사이클 신규 매매를 건너뜁니다.")
        return
    
    # 2. 시장 상황 분석
    market_condition = portfolio_summary.get("market_condition", {})
    dynamic_ratio = calculate_dynamic_position_size(market_condition, base_trade_ratio)
    
    print(f"📊 시장 상황: {market_condition.get('condition', 'unknown')}")
    print(f"🎯 조정된 거래 비율: {dynamic_ratio:.1%} (기본: {base_trade_ratio:.1%})")
    
    # 현재 보유 현금 확인
    available_krw = upbit.get_balance("KRW")
    print(f"사용 가능 현금: {available_krw:,.0f}원")
    
    # 각 코인별 매매 실행
    for coin, signal_data in ai_signals.items():
        signal = signal_data.get('signal', 'HOLD')
        confidence = signal_data.get('confidence', 0.5)
        reason = signal_data.get('reason', 'No reason provided')
        
        ticker = f"KRW-{coin}"
        print(f"\n🪙 {coin} 분석:")
        print(f"  신호: {signal} | 신뢰도: {confidence:.1%}")
        print(f"  근거: {reason}")
        
        try:
            if signal in ['STRONG_BUY', 'BUY']:
                # 신뢰도에 따른 매수 금액 조절 (리스크 감소)
                if signal == 'STRONG_BUY' and confidence > 0.9:
                    multiplier = 1.5  # 1.5배 매수 (기존 2배에서 감소)
                elif signal == 'BUY' and confidence > 0.7:
                    multiplier = 1.0  # 일반 매수
                elif confidence > 0.5:
                    multiplier = 0.5  # 신뢰도 낮을 때 절반
                else:
                    print(f"  ⚠️ 신뢰도 너무 낮음 ({confidence:.1%}) - 매수 건너뜀")
                    continue
                
                # 거래 전 포트폴리오 스냅샷
                portfolio_before = {}
                try:
                    portfolio_before = {
                        'krw_balance': upbit.get_balance("KRW"),
                        'coin_balance': upbit.get_balance(ticker),
                        'timestamp': datetime.now().isoformat()
                    }
                except Exception as e:
                    logging.debug(f"매수 전 포트폴리오 스냅샷 저장 실패: {e}")
                    pass
                
                # 매수 실행 전 추가 안전 체크
                current_krw = upbit.get_balance("KRW")
                
                # 현금 부족 시 매수 제한
                if current_krw < MIN_TRADE_AMOUNT * 2:  # 최소 거래금액의 2배 미만 시
                    print(f"  ⚠️ 현금 부족으로 매수 제한: {current_krw:,.0f}원")
                    continue
                
                # 🚨 NEW: 매수 전 포트폴리오 집중도 체크 (악순환 방지)
                current_total_value = current_krw
                current_coin_balance = upbit.get_balance(ticker)
                current_price = pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['ask_price']
                
                # 다른 코인들의 가치도 포함해서 전체 포트폴리오 계산
                for other_ticker in PORTFOLIO_COINS:
                    if other_ticker != ticker:
                        other_balance = upbit.get_balance(other_ticker)
                        if other_balance > 0:
                            other_price = pyupbit.get_orderbook(ticker=other_ticker)['orderbook_units'][0]['ask_price']
                            current_total_value += other_balance * other_price
                
                # 현재 해당 코인의 비중 계산
                current_coin_value = current_coin_balance * current_price if current_coin_balance > 0 else 0
                current_coin_ratio = current_coin_value / current_total_value if current_total_value > 0 else 0
                
                # 자유 투자 모드 설정 체크
                free_trading_mode = CONFIG.get("trading_mode", {}).get("free_investment", False)
                
                if not free_trading_mode:
                    # 기존 집중도 제한 (보수적 모드)
                    max_concentration = CONFIG.get("trading_constraints", {}).get("max_single_coin_ratio", 0.35)
                    
                    if current_coin_ratio >= max_concentration:
                        print(f"  ⚠️ {coin} 비중 한계 도달 ({current_coin_ratio:.1%} >= {max_concentration:.1%}) - 매수 제한")
                        continue
                else:
                    # 자유 투자 모드: 집중도 제한 완화 (최대 70%까지 허용)
                    max_concentration = CONFIG.get("trading_mode", {}).get("max_concentration_free", 0.70)
                    
                    if current_coin_ratio >= max_concentration:
                        print(f"  ⚠️ {coin} 극한 비중 도달 ({current_coin_ratio:.1%} >= {max_concentration:.1%}) - 매수 제한")
                        continue
                    else:
                        print(f"  🚀 자유투자모드: {coin} 현재비중 {current_coin_ratio:.1%} (한계: {max_concentration:.1%})")
                
                # 매수 실행 (동적 포지션 사이징 + AI 추천 사이즈 적용)
                ai_size_ratio = signal_data.get('recommended_size', dynamic_ratio)
                # AI 추천 사이즈와 동적 사이징 중 더 보수적인 값 선택
                final_ratio = min(ai_size_ratio, dynamic_ratio * multiplier)
                trade_amount = current_krw * final_ratio * 0.9995  # 수수료 고려
                
                # 최대 투자 한도 체크 (총 자산의 85%까지만)
                total_portfolio = get_current_portfolio_snapshot(upbit)
                total_value = total_portfolio.get('total_value', 0)
                krw_ratio = current_krw / total_value if total_value > 0 else 1
                
                if krw_ratio < MIN_CASH_RATIO:  # 현금이 설정 비율 미만이면 매수 제한
                    print(f"  ⚠️ 현금 비율 부족으로 매수 제한: {krw_ratio:.1%}")
                    continue
                
                current_price = pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['ask_price']
                
                if trade_amount > MIN_TRADE_AMOUNT:  # 최소 거래 금액
                    result = upbit.buy_market_order(ticker, trade_amount)
                    if result:
                        message = f"{coin} 매수 완료: {trade_amount:,.0f}원 (AI추천: {ai_size_ratio:.1%}) | 신뢰도: {confidence:.1%}"
                        print(f"  ✅ {message}")
                        logging.info(f"BUY - {message}")
                        
                        # 거래 후 포트폴리오 스냅샷
                        portfolio_after = {}
                        try:
                            portfolio_after = {
                                'krw_balance': upbit.get_balance("KRW"),
                                'coin_balance': upbit.get_balance(ticker),
                                'timestamp': datetime.now().isoformat()
                            }
                        except Exception as e:
                            logging.warning(f"매수 후 포트폴리오 스냅샷 실패: {e}")
                            portfolio_after = {}
                        
                        # 상세 거래 로깅
                        try:
                            market_data = portfolio_summary.get('coins', {}).get(coin, {})
                            ai_signal_data = {
                                'signal': signal,
                                'confidence': confidence,
                                'reasoning': reason,
                                'stop_loss': signal_data.get('stop_loss'),
                                'take_profit': signal_data.get('take_profit'),
                                'recommended_size': signal_data.get('recommended_size'),
                                'tokens_used': signal_data.get('tokens_used'),
                                'cost': signal_data.get('cost')
                            }
                            log_detailed_trade(coin, 'BUY', 
                                             trade_amount / current_price,  # 구매 수량
                                             current_price, trade_amount, -trade_amount,
                                             market_data, ai_signal_data, 
                                             portfolio_before, portfolio_after)
                        except Exception as e:
                            logging.error(f"매수 상세 로깅 실패: {e}")
                            
                    else:
                        message = f"{coin} 매수 실패"
                        print(f"  ❌ {message}")
                        logging.error(f"BUY_FAILED - {message}")
                else:
                    print(f"  ⏸️  매수 금액 부족 ({trade_amount:,.0f}원 < {MIN_TRADE_AMOUNT:,}원)")
                    
            elif signal == 'SELL':
                # 거래 전 포트폴리오 스냅샷
                portfolio_before = {}
                try:
                    portfolio_before = {
                        'krw_balance': upbit.get_balance("KRW"),
                        'coin_balance': upbit.get_balance(ticker),
                        'timestamp': datetime.now().isoformat()
                    }
                except Exception as e:
                    logging.debug(f"매도 전 포트폴리오 스냅샷 저장 실패: {e}")
                    pass
                
                # 매도 실행
                current_balance = upbit.get_balance(ticker)
                if current_balance > 0:
                    # 신뢰도에 따른 매도 비율
                    sell_ratio = confidence if confidence > 0.6 else 0.3
                    sell_amount = current_balance * sell_ratio
                    
                    # 최소 거래 금액 확인
                    current_price = pyupbit.get_orderbook(ticker=ticker)['orderbook_units'][0]['ask_price']
                    sell_value = sell_amount * current_price
                    
                    if sell_value > MIN_TRADE_AMOUNT:
                        result = upbit.sell_market_order(ticker, sell_amount)
                        if result:
                            message = f"{coin} 매도 완료: {sell_amount:.6f} ({sell_ratio:.1%}) | 신뢰도: {confidence:.1%}"
                            print(f"  ✅ {message}")
                            logging.info(f"SELL - {message}")
                            
                            # 거래 후 포트폴리오 스냅샷
                            portfolio_after = {}
                            try:
                                portfolio_after = {
                                    'krw_balance': upbit.get_balance("KRW"),
                                    'coin_balance': upbit.get_balance(ticker),
                                    'timestamp': datetime.now().isoformat()
                                }
                            except Exception as e:
                                logging.warning(f"매도 후 포트폴리오 스냅샷 실패: {e}")
                                portfolio_after = {}
                            
                            # 상세 거래 로깅
                            try:
                                market_data = portfolio_summary.get('coins', {}).get(coin, {})
                                ai_signal_data = {
                                    'signal': signal,
                                    'confidence': confidence,
                                    'reasoning': reason,
                                    'stop_loss': signal_data.get('stop_loss'),
                                    'take_profit': signal_data.get('take_profit'),
                                    'recommended_size': signal_data.get('recommended_size'),
                                    'tokens_used': signal_data.get('tokens_used'),
                                    'cost': signal_data.get('cost')
                                }
                                log_detailed_trade(coin, 'SELL', sell_amount, current_price, 
                                                 sell_value, sell_value,  # 매도는 현금 증가
                                                 market_data, ai_signal_data, 
                                                 portfolio_before, portfolio_after)
                            except Exception as e:
                                logging.error(f"매도 상세 로깅 실패: {e}")
                                
                        else:
                            message = f"{coin} 매도 실패"
                            print(f"  ❌ {message}")
                            logging.error(f"SELL_FAILED - {message}")
                    else:
                        print(f"  ⏸️  매도 금액 부족")
                else:
                    print(f"  ⏸️  보유량 없음")
                    
            else:  # HOLD
                print(f"  ⏸️  보유 (신뢰도: {confidence:.1%})")
                
        except Exception as e:
            print(f"  ❌ {coin} 거래 오류: {e}")
    
    print(f"\n✅ 포트폴리오 매매 실행 완료")

def log_detailed_trade(coin, action, amount, price, total_value, balance_change, 
                      market_data, ai_signal, portfolio_before, portfolio_after):
    """상세 거래 데이터 로깅 (JSON 형태)"""
    trade_data = {
        "timestamp": datetime.now().isoformat(),
        "coin": coin,
        "action": action,
        "amount": float(amount) if amount else 0,
        "price": float(price) if price else 0,
        "total_value": float(total_value) if total_value else 0,
        "balance_change": float(balance_change) if balance_change else 0,
        "market_data": {
            "rsi": market_data.get('rsi') if market_data else None,
            "ma_20": market_data.get('ma_20') if market_data else None,
            "bb_upper": market_data.get('bb_upper') if market_data else None,
            "bb_lower": market_data.get('bb_lower') if market_data else None,
            "volume_ratio": market_data.get('volume_ratio') if market_data else None,
            "price_change_24h": market_data.get('price_change_24h') if market_data else None
        },
        "ai_signal": {
            "signal": ai_signal.get('signal') if ai_signal else None,
            "confidence": ai_signal.get('confidence') if ai_signal else None,
            "reasoning": ai_signal.get('reasoning') if ai_signal else None,
            "tokens_used": ai_signal.get('tokens_used') if ai_signal else None,
            "cost": ai_signal.get('cost') if ai_signal else None
        },
        "portfolio_before": portfolio_before,
        "portfolio_after": portfolio_after
    }
    
    try:
        trade_logger = logging.getLogger('trade_logger')
        trade_logger.info(json.dumps(trade_data, ensure_ascii=False))
    except Exception as e:
        logging.error(f"거래 로깅 실패: {e}")

def log_ai_signal_detailed(coin, signal_data, market_context, cost_info):
    """AI 신호 상세 로깅"""
    signal_log = {
        "timestamp": datetime.now().isoformat(),
        "coin": coin,
        "signal": signal_data.get('signal') if signal_data else None,
        "confidence": signal_data.get('confidence') if signal_data else None,
        "reasoning": signal_data.get('reasoning') if signal_data else None,
        "market_context": market_context,
        "cost_info": cost_info,
        "model": "gpt-4o-mini"
    }
    
    try:
        signal_logger = logging.getLogger('signal_logger')
        signal_logger.info(json.dumps(signal_log, ensure_ascii=False))
    except Exception as e:
        logging.error(f"AI 신호 로깅 실패: {e}")

def log_performance_metrics(portfolio_value, daily_return, portfolio_allocation, market_summary):
    """성과 지표 로깅"""
    performance_data = {
        "timestamp": datetime.now().isoformat(),
        "portfolio_value": portfolio_value,
        "daily_return": daily_return,
        "portfolio_allocation": portfolio_allocation,
        "market_summary": market_summary,
        "ai_cost_today": calculate_daily_ai_cost()
    }
    
    try:
        performance_logger = logging.getLogger('performance_logger')
        performance_logger.info(json.dumps(performance_data, ensure_ascii=False))
    except Exception as e:
        logging.error(f"성과 로깅 실패: {e}")

def calculate_daily_ai_cost():
    """일일 AI 사용 비용 계산"""
    try:
        signal_file = f'ai_signals_{datetime.now().strftime("%Y%m%d")}.json'
        if not os.path.exists(signal_file):
            return 0
        
        total_cost = 0
        with open(signal_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    signal_data = json.loads(line.strip())
                    cost_info = signal_data.get('cost_info', {})
                    total_cost += cost_info.get('cost_krw', 0)
                except (json.JSONDecodeError, KeyError) as e:
                    logging.debug(f"AI 비용 계산 중 라인 스킵: {e}")
                    continue
        
        return total_cost
    except Exception as e:
        logging.warning(f"일일 AI 비용 계산 실패: {e}")
        return 0

def get_current_portfolio_snapshot(upbit):
    """현재 포트폴리오 스냅샷 생성"""
    try:
        balances = upbit.get_balances()
        if not balances:
            logging.warning("잔고 정보를 가져올 수 없습니다.")
            return {'total_value': 0}
        
        portfolio = {}
        total_value = 0
        
        for balance in balances:
            try:
                currency = balance.get('currency', '')
                balance_amount = float(balance.get('balance', 0))
                
                if balance_amount <= 0:
                    continue
                
                if currency == 'KRW':
                    portfolio['KRW'] = balance_amount
                    total_value += balance_amount
                else:
                    ticker = f"KRW-{currency}"
                    try:
                        orderbook = pyupbit.get_orderbook(ticker=ticker)
                        if orderbook and 'orderbook_units' in orderbook and orderbook['orderbook_units']:
                            current_price = orderbook['orderbook_units'][0]['ask_price']
                            value = balance_amount * current_price
                            portfolio[currency] = {
                                'amount': balance_amount,
                                'price': current_price,
                                'value': value
                            }
                            total_value += value
                    except Exception as ticker_error:
                        logging.warning(f"{ticker} 가격 조회 실패: {ticker_error}")
                        continue
                        
            except Exception as balance_error:
                logging.warning(f"잔고 처리 오류 ({currency}): {balance_error}")
                continue
        
        portfolio['total_value'] = total_value
        return portfolio
        
    except Exception as e:
        logging.error(f"포트폴리오 스냅샷 생성 실패: {e}")
        return {'total_value': 0}

def calculate_check_interval(portfolio_summary, news_analysis=None):
    """시장 변동성과 뉴스 긴급도에 따른 체크 주기 계산 - 기회 포착 강화"""
    total_volatility = 0
    coin_count = 0
    
    for coin, data in portfolio_summary.get('coins', {}).items():
        change_rate = abs(data.get('change_rate', 0))
        total_volatility += change_rate
        coin_count += 1
    
    if coin_count == 0:
        return CHECK_INTERVALS["default_interval"] * 60  # 컨트래리언 기본 간격 30분 (분 → 초)
    
    avg_volatility = total_volatility / coin_count
    
    # 뉴스 긴급도 우선 체크 (컨트래리언 극초고속 반응)
    if news_analysis and news_analysis.get('emergency', False):
        interval_min = CHECK_INTERVALS.get("news_emergency_interval", 3)  # 컨트래리언 3분
        print(f"🚨 긴급 뉴스 감지 → {interval_min}분 후 재체크")
        return interval_min * 60
    
    # config에서 설정한 변동성 기준과 간격 사용 (컨트래리언 공격적 설정)
    if avg_volatility > CHECK_INTERVALS["extreme_volatility_threshold"]:      # 극고변동성
        interval_min = CHECK_INTERVALS["extreme_volatility_interval"]  # 5분 (컨트래리언)
        print(f"🔥 극고변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60           # 분 → 초
    elif avg_volatility > CHECK_INTERVALS["high_volatility_threshold"]:       # 고변동성
        interval_min = CHECK_INTERVALS["high_volatility_interval"]  # 10분 (컨트래리언)
        print(f"📈 고변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60              # 분 → 초
    elif avg_volatility > CHECK_INTERVALS["medium_volatility_threshold"]:     # 중변동성  
        interval_min = CHECK_INTERVALS["medium_volatility_interval"]  # 20분 (컨트래리언)
        print(f"📊 중변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60            # 분 → 초
    else:                                                                    # 저변동성
        interval_min = CHECK_INTERVALS["low_volatility_interval"]  # 40분 (컨트래리언)
        print(f"😴 저변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60               # 분 → 초

def load_config():
    """설정 파일 로드"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✅ 설정 파일 로드 완료")
        return config
    except FileNotFoundError:
        print("⚠️ config.json 파일이 없습니다. 기본 설정값을 사용합니다.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ 설정 파일 파싱 오류: {e}")
        return None

def setup_logging():
    """로깅 시스템 설정"""
    log_filename = f"trading_bot_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def setup_detailed_logging():
    """실제 투자 데이터 수집용 상세 로깅 시스템 설정"""
    # 상세 거래 로그
    trade_logger = logging.getLogger('trade_logger')
    trade_logger.setLevel(logging.INFO)
    trade_handler = logging.FileHandler(f'trades_{datetime.now().strftime("%Y%m%d")}.json', encoding='utf-8')
    trade_handler.setFormatter(logging.Formatter('%(message)s'))
    trade_logger.addHandler(trade_handler)
    
    # AI 신호 로그
    signal_logger = logging.getLogger('signal_logger')
    signal_logger.setLevel(logging.INFO)
    signal_handler = logging.FileHandler(f'ai_signals_{datetime.now().strftime("%Y%m%d")}.json', encoding='utf-8')
    signal_handler.setFormatter(logging.Formatter('%(message)s'))
    signal_logger.addHandler(signal_handler)
    
    # 성과 로그
    performance_logger = logging.getLogger('performance_logger')
    performance_logger.setLevel(logging.INFO)
    performance_handler = logging.FileHandler(f'performance_{datetime.now().strftime("%Y%m%d")}.json', encoding='utf-8')
    performance_handler.setFormatter(logging.Formatter('%(message)s'))
    performance_logger.addHandler(performance_handler)
    
    return trade_logger, signal_logger, performance_logger

def run_trading_bot():
    """24시간 자동화 트레이딩 봇 실행"""
    # 설정 파일 로드
    config = load_config()
    
    # 로깅 설정
    logger = setup_logging()
    logger.info("🚀 AI 포트폴리오 트레이딩 봇 시작! (개선 v2.0 - 뉴스 통합 + 기회 포착 강화)")
    print("🚀 AI 포트폴리오 트레이딩 봇 시작!")
    print("🔧 v2.0 개선사항: 뉴스 감정 분석, 기회 포착 강화, 동적 체크 주기")
    print("=" * 60)
    
    # 설정 값 적용
    if config:
        global BASE_TRADE_RATIO, STOP_LOSS_PERCENT, MIN_TRADE_AMOUNT
        BASE_TRADE_RATIO = config.get("trading", {}).get("base_trade_ratio", BASE_TRADE_RATIO)
        STOP_LOSS_PERCENT = config.get("trading", {}).get("stop_loss_percent", STOP_LOSS_PERCENT)
        MIN_TRADE_AMOUNT = config.get("trading", {}).get("min_trade_amount", MIN_TRADE_AMOUNT)
        print(f"⚙️ 설정 적용: 거래비율={BASE_TRADE_RATIO:.1%}, 손절매={STOP_LOSS_PERCENT}%, 최소거래={MIN_TRADE_AMOUNT:,}원")
    
    # API 키 로드
    load_dotenv()
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    
    if not access or not secret:
        print("❌ API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return
    
    upbit = pyupbit.Upbit(access, secret)
    print("✅ 업비트 API 연결 완료")
    
    cycle_count = 0
    
    while True:
        try:
            cycle_count += 1
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n🔄 사이클 #{cycle_count} | {current_time}")
            print("-" * 60)
            
            # 매 10사이클마다 설정 재로드
            if cycle_count % 10 == 0:
                print("🔄 설정 파일 재로드 중...")
                reload_config()
            
            # 1. 포트폴리오 데이터 수집
            print("📊 포트폴리오 데이터 수집 중...")
            portfolio_data = get_portfolio_data()
            
            if not portfolio_data:
                print("❌ 데이터 수집 실패, 1시간 후 재시도")
                time.sleep(60 * 60)
                continue
            
            # 2. 시장 지표 수집 (뉴스 감정 분석 추가)
            print("📈 시장 지표 수집 중...")
            fng = get_fear_greed_index()
            news = get_news_headlines()
            news_analysis = analyze_news_sentiment(news)
            
            print(f"공포탐욕지수: {fng.get('value', 'N/A')} ({fng.get('text', 'N/A')})")
            print(f"뉴스 헤드라인: {len(news)}개")
            print(f"뉴스 감정: {news_analysis['sentiment']} (점수: {news_analysis['score']})")
            
            # 긴급 이벤트 알림
            if news_analysis['emergency']:
                print(f"🚨 긴급 이벤트 감지: {', '.join(news_analysis['events'])}")
                logging.warning(f"긴급 뉴스 이벤트: {news_analysis['events']}")
            elif news_analysis['events']:
                print(f"📢 주요 이벤트: {', '.join(news_analysis['events'])}")
            
            # 3. 포트폴리오 요약 생성
            portfolio_summary = make_portfolio_summary(portfolio_data, fng, news)
            
            # 4. AI 분석 실행
            print("\n🤖 AI 포트폴리오 분석 중...")
            ai_signals = get_portfolio_ai_signals(portfolio_summary)
            
            # 5. 포트폴리오 현황 출력
            print(f"\n💼 현재 포트폴리오 상황:")
            for coin, data in portfolio_summary.get('coins', {}).items():
                price = data.get('current_price', 0)
                change = data.get('change_rate', 0)
                rsi = data.get('rsi', 0)
                print(f"  {coin}: {price:,.0f}원 ({change:+.2f}%) RSI:{rsi:.1f}")
            
            # 6. 성과 모니터링
            performance_summary = calculate_performance_metrics(upbit, portfolio_summary)
            print_performance_summary(performance_summary)
            
            # 성과 데이터 상세 로깅
            try:
                current_portfolio = get_current_portfolio_snapshot(upbit)
                portfolio_value = current_portfolio.get('total_value', 0)
                
                # 포트폴리오 배분 계산
                portfolio_allocation = {}
                if portfolio_value > 0:
                    for coin, data in current_portfolio.items():
                        if coin != 'total_value' and isinstance(data, dict):
                            allocation_pct = (data['value'] / portfolio_value) * 100
                            portfolio_allocation[coin] = allocation_pct
                        elif coin == 'KRW':
                            allocation_pct = (data / portfolio_value) * 100
                            portfolio_allocation['KRW'] = allocation_pct
                
                # 일일 수익률 계산 (임시로 0으로 설정, 추후 개선 가능)
                daily_return = performance_summary.get('total_change_percent', 0)
                
                # 시장 요약
                market_summary = {
                    'market_condition': portfolio_summary.get('market_condition', {}),
                    'fear_greed_index': portfolio_summary.get('fear_greed_index', 0),
                    'total_portfolio_change': portfolio_summary.get('total_change_percent', 0)
                }
                
                log_performance_metrics(portfolio_value, daily_return, 
                                      portfolio_allocation, market_summary)
                
            except Exception as e:
                logging.error(f"성과 로깅 실패: {e}")
            
            # 7. 매매 실행
            print(f"\n💰 스마트 매매 실행:")
            execute_portfolio_trades(ai_signals, upbit, portfolio_summary, cycle_count)
            
            # 8. 다음 체크 주기 계산 (뉴스 분석 결과 반영)
            check_interval = calculate_check_interval(portfolio_summary, news_analysis)
            next_check = time.strftime('%H:%M:%S', time.localtime(time.time() + check_interval))
            
            print(f"\n⏰ 다음 체크: {check_interval//60}분 후 ({next_check})")
            print("=" * 60)
            
            # 대기
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("🛑 사용자에 의해 봇이 중단되었습니다.")
            print(f"\n\n🛑 사용자에 의해 봇이 중단되었습니다.")
            break
            
        except requests.exceptions.RequestException as e:
            logger.error(f"네트워크 오류: {e}")
            print(f"\n🌐 네트워크 오류: {e}")
            print("⏰ 5분 후 재시도합니다...")
            time.sleep(5 * 60)  # 네트워크 오류는 5분만 대기
            
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            print(f"\n❌ 예상치 못한 오류: {e}")
            print("⏰ 30분 후 재시도합니다...")
            time.sleep(30 * 60)  # 기타 오류는 30분 대기

def run_backtest(days_back=30, initial_balance=1000000):
    """백테스팅 시스템 - 과거 데이터로 전략 검증"""
    print("📊 백테스팅 시작!")
    print("=" * 60)
    
    # 백테스트 결과 저장
    backtest_results = {
        'initial_balance': initial_balance,
        'trades': [],
        'daily_balance': [],
        'max_drawdown': 0,
        'win_rate': 0,
        'total_trades': 0
    }
    
    # 과거 데이터 수집 (더 긴 기간)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back + DATA_PERIOD)
    
    print(f"📅 백테스트 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    
    # 시뮬레이션 포트폴리오
    portfolio_balance = initial_balance
    coin_holdings = {coin.split('-')[1]: 0 for coin in PORTFOLIO_COINS}
    max_balance = initial_balance
    
    try:
        # 일별 백테스트 실행
        for day in range(days_back):
            current_date = end_date - timedelta(days=days_back - day)
            print(f"\n📊 {current_date.strftime('%Y-%m-%d')} 백테스트 중...")
            
            # 해당 날짜의 데이터로 시뮬레이션
            portfolio_data = get_historical_data_for_date(current_date)
            
            if not portfolio_data or len(portfolio_data) == 0:
                print(f"  ❌ {current_date.strftime('%Y-%m-%d')} 데이터 없음")
                continue
            
            # 최소 2개 이상의 코인 데이터가 있을 때만 거래 진행
            valid_coins = []
            for coin, data in portfolio_data.items():
                if data and 'day' in data:
                    day_data = data['day']
                    if day_data is not None and hasattr(day_data, 'empty') and not day_data.empty:
                        valid_coins.append(coin)
            
            if len(valid_coins) < 2:
                print(f"  ⚠️ {current_date.strftime('%Y-%m-%d')} 유효한 코인 데이터 부족 ({len(valid_coins)}개)")
                continue
            
            # 시뮬레이션 거래 실행 (portfolio_data 직접 전달)
            portfolio_balance, coin_holdings = simulate_trading(
                portfolio_data, portfolio_balance, coin_holdings, backtest_results
            )
            
            # 일일 잔고 기록
            backtest_results['daily_balance'].append({
                'date': current_date.strftime('%Y-%m-%d'),
                'balance': portfolio_balance
            })
            
            # 최대 손실 계산
            if portfolio_balance > max_balance:
                max_balance = portfolio_balance
            
            drawdown = (max_balance - portfolio_balance) / max_balance * 100
            if drawdown > backtest_results['max_drawdown']:
                backtest_results['max_drawdown'] = drawdown
        
        # 백테스트 결과 분석
        analyze_backtest_results(backtest_results)
        
    except Exception as e:
        print(f"❌ 백테스트 오류: {e}")
        return None
    
    return backtest_results

def get_historical_data_for_date(target_date):
    """특정 날짜 기준 과거 데이터 수집 - 더 현실적인 백테스팅을 위해 날짜별 다른 데이터 시뮬레이션"""
    import random  # 백테스트용 랜덤 시뮬레이션
    
    portfolio_data = {}
    
    # 날짜 기반 시드로 랜덤 가격 변동 시뮬레이션
    date_seed = int(target_date.strftime('%Y%m%d'))
    random.seed(date_seed)
    
    for ticker in PORTFOLIO_COINS:
        try:
            # 기본 데이터 가져오기
            df = pyupbit.get_ohlcv(ticker, interval="day", count=DATA_PERIOD)
            if df is not None and not df.empty:
                coin_name = ticker.split('-')[1]
                
                # 날짜별 가격 변동 시뮬레이션 (±10% 범위)
                base_price = df['close'].iloc[-1]
                price_change = random.uniform(-0.1, 0.1)  # -10% ~ +10%
                simulated_price = base_price * (1 + price_change)
                
                # 마지막 가격을 시뮬레이션 가격으로 변경
                df_copy = df.copy()
                df_copy['close'].iloc[-1] = simulated_price
                df_copy['high'].iloc[-1] = max(df_copy['high'].iloc[-1], simulated_price)
                df_copy['low'].iloc[-1] = min(df_copy['low'].iloc[-1], simulated_price)
                
                # RSI 계산을 위해 몇 개 더 가격 조정 (트렌드 생성)
                trend = random.choice([-1, 0, 1])  # 하락, 횡보, 상승
                for i in range(-5, 0):  # 마지막 5일 트렌드 생성
                    if abs(i) < len(df_copy):
                        trend_change = trend * random.uniform(0.01, 0.03)  # 1-3% 변동
                        df_copy['close'].iloc[i] *= (1 + trend_change)
                
                portfolio_data[coin_name] = {'day': df_copy}
                
                # 변동률 계산
                original_price = base_price
                change_pct = (simulated_price - original_price) / original_price * 100
                
                print(f"  ✅ {coin_name} 데이터 수집: {len(df_copy)}행 (가격변동: {change_pct:+.1f}%)")
            else:
                print(f"  ❌ {ticker} 데이터 없음")
        except Exception as e:
            print(f"  ❌ {ticker} 히스토리 데이터 오류: {e}")
    
    return portfolio_data

def simulate_trading(portfolio_data, balance, holdings, backtest_results):
    """시뮬레이션 거래 실행"""
    # AI 신호 생성 (실제 API 호출하지 않고 로컬 로직 사용)
    ai_signals = generate_backtest_signals(portfolio_data)
    
    # 현재 포트폴리오 가치 계산
    total_portfolio_value = balance
    for coin, amount in holdings.items():
        if coin in portfolio_data and amount > 0:
            coin_price = portfolio_data[coin]['day']['close'].iloc[-1]
            total_portfolio_value += amount * coin_price
    
    for coin, signal_data in ai_signals.items():
        signal = signal_data.get('signal', 'HOLD')
        confidence = signal_data.get('confidence', 0.5)
        
        if signal in ['STRONG_BUY', 'BUY'] and confidence > 0.6:  # 임계값 유지 (신뢰도가 이미 0.65로 상향됨)
            # 매수 시뮬레이션
            if signal == 'STRONG_BUY' and confidence > 0.8:  # 조건 완화 (기존 0.9 → 0.8)
                multiplier = 1.5
            else:
                multiplier = 1.0
            
            # 잔고 부족 방지를 위한 안전 장치
            max_trade_amount = balance * 0.8  # 잔고의 80%까지만 사용
            trade_amount = min(balance * BASE_TRADE_RATIO * multiplier, max_trade_amount)
            
            if trade_amount > MIN_TRADE_AMOUNT and balance > trade_amount:
                # 현재 가격을 DataFrame에서 직접 추출
                coin_price = portfolio_data[coin]['day']['close'].iloc[-1]
                
                # 포트폴리오 밸런싱 체크: 특정 코인이 전체 포트폴리오의 50% 초과하지 않도록
                current_coin_value = holdings[coin] * coin_price if holdings[coin] > 0 else 0
                coin_ratio = current_coin_value / total_portfolio_value if total_portfolio_value > 0 else 0
                
                if coin_ratio > 0.5:  # 이미 50% 초과 시 매수 제한
                    print(f"    ⚠️ {coin} 포트폴리오 비중 초과 ({coin_ratio:.1%}), 매수 제한")
                    continue
                
                coin_amount = trade_amount / coin_price
                holdings[coin] += coin_amount
                balance -= trade_amount
                
                print(f"    💰 {coin} 매수: {coin_amount:.6f}개 (가격: {coin_price:,.0f}원, 총투자: {trade_amount:,.0f}원)")
                print(f"    📊 잔고: {balance:,.0f}원, {coin} 보유: {holdings[coin]:.6f}개")
                
                # 거래 기록
                backtest_results['trades'].append({
                    'type': 'BUY',
                    'coin': coin,
                    'amount': coin_amount,
                    'price': coin_price,
                    'value': trade_amount,
                    'confidence': confidence
                })
                backtest_results['total_trades'] += 1
        
        elif signal == 'SELL':
            if holdings[coin] > 0:
                # 매도 시뮬레이션
                sell_ratio = confidence if confidence > 0.6 else 0.3
                sell_amount = holdings[coin] * sell_ratio
                # 현재 가격을 DataFrame에서 직접 추출
                coin_price = portfolio_data[coin]['day']['close'].iloc[-1]
                sell_value = sell_amount * coin_price
                
                if sell_value > MIN_TRADE_AMOUNT:
                    holdings[coin] -= sell_amount
                    balance += sell_value
                    
                    print(f"    💸 {coin} 매도: {sell_amount:.6f}개 (가격: {coin_price:,.0f}원, 수익: {sell_value:,.0f}원)")
                    print(f"    📊 잔고: {balance:,.0f}원, {coin} 보유: {holdings[coin]:.6f}개")
                    
                    # 거래 기록
                    backtest_results['trades'].append({
                        'type': 'SELL',
                        'coin': coin,
                        'amount': sell_amount,
                        'price': coin_price,
                        'value': sell_value,
                        'confidence': confidence
                    })
                    backtest_results['total_trades'] += 1
                else:
                    print(f"    ⚠️ {coin} 매도 금액이 최소 거래금액({MIN_TRADE_AMOUNT:,}원) 미만: {sell_value:,.0f}원")
            else:
                print(f"    ⚠️ {coin} 매도 신호이지만 보유량 없음 (현재: {holdings[coin]:.6f}개)")
    
    return balance, holdings

def calculate_technical_indicators(df):
    """DataFrame에서 기술적 지표 계산"""
    if df is None or df.empty:
        return None
    
    try:
        # RSI 계산 (14일 기준)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # 이동평균 계산
        ma5 = df['close'].rolling(window=5).mean().iloc[-1]
        ma20 = df['close'].rolling(window=20).mean().iloc[-1]
        
        # 현재 가격
        current_price = df['close'].iloc[-1]
        
        # 볼린저 밴드 계산
        bb_period = 20
        bb_std = 2
        bb_ma = df['close'].rolling(window=bb_period).mean().iloc[-1]
        bb_std_val = df['close'].rolling(window=bb_period).std().iloc[-1]
        bb_upper = bb_ma + (bb_std_val * bb_std)
        bb_lower = bb_ma - (bb_std_val * bb_std)
        
        return {
            'rsi': float(rsi) if not pd.isna(rsi) else 50.0,
            'ma5': float(ma5) if not pd.isna(ma5) else current_price,
            'ma20': float(ma20) if not pd.isna(ma20) else current_price,
            'current_price': float(current_price),
            'bb_upper': float(bb_upper) if not pd.isna(bb_upper) else current_price * 1.02,
            'bb_lower': float(bb_lower) if not pd.isna(bb_lower) else current_price * 0.98,
            'volume': float(df['volume'].iloc[-1]) if 'volume' in df.columns else 0
        }
    except Exception as e:
        print(f"    ⚠️ 기술적 지표 계산 오류: {e}")
        return None

def convert_portfolio_data_to_summary(portfolio_data):
    """포트폴리오 데이터를 AI 신호 생성용 summary 형태로 변환"""
    portfolio_summary = {'coins': {}}
    
    for coin, timeframes in portfolio_data.items():
        if 'day' in timeframes:
            indicators = calculate_technical_indicators(timeframes['day'])
            if indicators:
                portfolio_summary['coins'][coin] = indicators
                print(f"    📊 {coin} 지표: RSI={indicators['rsi']:.1f}, MA5={indicators['ma5']:.0f}, MA20={indicators['ma20']:.0f}")
    
    return portfolio_summary

def generate_backtest_signals(portfolio_data):
    """백테스트용 AI 신호 생성 (API 호출 없이 로컬 로직)"""
    # 포트폴리오 데이터를 summary 형태로 변환
    portfolio_summary = convert_portfolio_data_to_summary(portfolio_data)
    signals = {}
    
    for coin, data in portfolio_summary.get('coins', {}).items():
        rsi = data.get('rsi', 50)
        ma5 = data.get('ma5', 0)
        ma20 = data.get('ma20', 0)
        current_price = data.get('current_price', 0)
        bb_upper = data.get('bb_upper', current_price * 1.02)
        bb_lower = data.get('bb_lower', current_price * 0.98)
        
        # 더 균형잡힌 매수/매도 신호 생성 (코인별 다양성 고려)
        buy_signals = 0
        sell_signals = 0
        
        # RSI 신호 (더 보수적으로 조정하여 품질 높은 신호만 생성)
        if rsi < 25:  # 강한 과매도
            buy_signals += 3
        elif rsi < 35:  # 과매도
            buy_signals += 2
        elif rsi < 40:  # 약한 매수
            buy_signals += 1
        elif rsi > 75:  # 강한 과매수
            sell_signals += 3  
        elif rsi > 65:  # 과매수
            sell_signals += 2
        elif rsi > 60:  # 약한 매도
            sell_signals += 1
        
        # 이동평균 신호 (트렌드 기반)
        if current_price > ma5:  # 단기 상승
            buy_signals += 1
        elif current_price < ma5:  # 단기 하락
            sell_signals += 1
            
        if ma5 > ma20:  # 중기 상승 트렌드
            buy_signals += 1
        elif ma5 < ma20:  # 중기 하락 트렌드
            sell_signals += 1
        
        # 볼린저 밴드 신호 (변동성 기반)
        if current_price <= bb_lower * 1.02:  # 하단 근처
            buy_signals += 1
        elif current_price >= bb_upper * 0.98:  # 상단 근처
            sell_signals += 1
        
        # 가격 모멘텀 기반 신호 (완화)
        price_change = (current_price - ma20) / ma20 * 100
        if price_change < -3:  # 3% 이상 하락
            buy_signals += 1
        elif price_change > 3:  # 3% 이상 상승
            sell_signals += 1
        
        # 코인별 특성 고려 (다양화를 위해)
        coin_factor = hash(coin) % 3  # 코인별 고유 factor
        if coin_factor == 0:  # BTC류 - 보수적
            threshold_buy = 3
            threshold_sell = 2
        elif coin_factor == 1:  # ETH류 - 중간
            threshold_buy = 2
            threshold_sell = 2
        else:  # ALT류 - 적극적
            threshold_buy = 2
            threshold_sell = 2
        
        # 신호 결정 (더 다양한 신호 생성)
        if buy_signals >= threshold_buy:
            signal = 'BUY'
            confidence = min(0.85, 0.65 + buy_signals * 0.05)
        elif sell_signals >= threshold_sell:
            signal = 'SELL'
            confidence = min(0.85, 0.65 + sell_signals * 0.05)
        else:
            signal = 'HOLD'
            confidence = 0.5
        
        signals[coin] = {
            'signal': signal,
            'confidence': confidence,
            'reason': f'RSI: {rsi:.1f}, MA추세: {ma5 > ma20}, 매수신호: {buy_signals}, 매도신호: {sell_signals}'
        }
        
        print(f"    🤖 {coin} AI신호: {signal} (신뢰도: {confidence:.1f}) - {signals[coin]['reason']}")
    
    return signals

def analyze_backtest_results(results):
    """백테스트 결과 분석 및 출력"""
    initial = results['initial_balance']
    final = results['daily_balance'][-1]['balance'] if results['daily_balance'] else initial
    
    total_return = (final - initial) / initial * 100
    total_trades = results['total_trades']
    max_drawdown = results['max_drawdown']
    
    # 승률 계산 (간단한 버전)
    winning_trades = len([t for t in results['trades'] if t['type'] == 'SELL'])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    print(f"\n📊 백테스트 결과 분석")
    print("=" * 40)
    print(f"초기 자본: {initial:,.0f}원")
    print(f"최종 자본: {final:,.0f}원")
    print(f"총 수익률: {total_return:+.2f}%")
    print(f"최대 손실률: {max_drawdown:.2f}%")
    print(f"총 거래 횟수: {total_trades}회")
    print(f"대략적 승률: {win_rate:.1f}%")
    
    # 일별 수익률 그래프 (텍스트 버전)
    print(f"\n📈 일별 수익률 추이:")
    for record in results['daily_balance'][-10:]:  # 마지막 10일만 출력
        daily_return = (record['balance'] - initial) / initial * 100
        bar_length = max(0, min(20, int(abs(daily_return))))
        bar = "█" * bar_length
        print(f"{record['date']}: {daily_return:+6.2f}% {bar}")

def reload_config():
    """설정을 다시 로드합니다."""
    global CONFIG, PORTFOLIO_COINS, BASE_TRADE_RATIO, STOP_LOSS_PERCENT, MIN_TRADE_AMOUNT
    global RSI_OVERSOLD, RSI_OVERBOUGHT, FEAR_GREED_EXTREME_FEAR, FEAR_GREED_EXTREME_GREED
    global DATA_PERIOD, CACHE_FILE, CACHE_DURATION, BULL_MARKET_THRESHOLD, BEAR_MARKET_THRESHOLD
    global MIN_CASH_RATIO, MAX_PORTFOLIO_CONCENTRATION
    
    CONFIG = load_config()
    
    # 상수들 업데이트
    PORTFOLIO_COINS = CONFIG["coins"]["list"]
    TARGET_ALLOCATION = CONFIG["coins"]["target_allocation"]
    BASE_TRADE_RATIO = CONFIG["trading"]["base_trade_ratio"]
    STOP_LOSS_PERCENT = CONFIG["trading"]["stop_loss_percent"]
    MIN_TRADE_AMOUNT = CONFIG["trading"]["min_trade_amount"]
    RSI_OVERSOLD = CONFIG["technical_analysis"]["rsi_oversold"]
    RSI_OVERBOUGHT = CONFIG["technical_analysis"]["rsi_overbought"]
    FEAR_GREED_EXTREME_FEAR = CONFIG["market_conditions"]["fear_greed_extreme_fear"]
    FEAR_GREED_EXTREME_GREED = CONFIG["market_conditions"]["fear_greed_extreme_greed"]
    DATA_PERIOD = CONFIG["technical_analysis"]["data_period_days"]
    CACHE_FILE = CONFIG["cache"]["cache_file"]
    CACHE_DURATION = CONFIG["cache"]["cache_duration_hours"] * 60 * 60
    BULL_MARKET_THRESHOLD = CONFIG["market_conditions"]["bull_market_threshold"]
    BEAR_MARKET_THRESHOLD = CONFIG["market_conditions"]["bear_market_threshold"]
    MIN_CASH_RATIO = CONFIG["safety"]["min_cash_ratio"]
    MAX_PORTFOLIO_CONCENTRATION = CONFIG["safety"]["max_portfolio_concentration"]
    CHECK_INTERVALS = CONFIG["check_intervals"]
    
    logging.info("설정이 다시 로드되었습니다.")

if __name__ == "__main__":
    import sys
    
    # 설정 파일 로드
    config = load_config()
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == "backtest":
            # 백테스트 모드
            days = config.get("backtest", {}).get("default_days", 30) if config else 30
            initial = config.get("backtest", {}).get("initial_balance", 1000000) if config else 1000000
            print(f"🧪 백테스트 모드: {days}일간, 초기자본 {initial:,}원")
            run_backtest(days_back=days, initial_balance=initial)
            
        elif mode == "config":
            # 설정 확인 모드
            if config:
                print("📋 현재 설정:")
                print(json.dumps(config, indent=2, ensure_ascii=False))
            else:
                print("❌ 설정 파일을 로드할 수 없습니다.")
                
        elif mode == "dry-run":
            # 모의 실행 모드 (실제 거래 없이 신호만 확인)
            print("🧪 모의 실행 모드 (실제 거래 없음)")
            # TODO: dry-run 모드 구현
            
        else:
            print("❌ 알 수 없는 모드입니다.")
            print("사용법: python mvp.py [backtest|config|dry-run]")
    else:
        # 실제 거래 모드
        print("🚀 실제 거래 모드 - 상세 데이터 수집 활성화")
        # 상세 로깅 시스템 초기화
        setup_detailed_logging()
        print("📊 실제 투자 데이터 수집 시작:")
        print(f"  - 거래 로그: trades_{datetime.now().strftime('%Y%m%d')}.json")
        print(f"  - AI 신호 로그: ai_signals_{datetime.now().strftime('%Y%m%d')}.json") 
        print(f"  - 성과 로그: performance_{datetime.now().strftime('%Y%m%d')}.json")
        run_trading_bot()
