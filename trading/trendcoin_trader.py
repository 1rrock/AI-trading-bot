"""
신규/트렌드 코인 자동 탐지 및 투자 모듈 (하이브리드 전략)
- 거래대금 상위 TOP5 코인 탐지
- 실제 뉴스 API (CryptoCompare) + OpenAI 분석 (1차 전략)
- 뉴스 없을 시 기술적 분석 (RSI, 거래량, 추세) 대체 (2차 전략)
- 위험 신호 감지 시 투자 제한
- 소액 분산 투자 및 별도 모니터링 주기
"""

from openai import OpenAI
import pyupbit
import requests
from datetime import datetime
from utils.api_helpers import get_safe_orderbook, get_safe_price
from utils.logger import log_decision

# CryptoCompare API 설정 (무료, API 키 불필요)
CRYPTOCOMPARE_NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"

def get_top_trend_coins(n=5, min_trade_value=1_000_000_000, min_orderbook_depth=5_000_000):
    """
    트렌드 코인 탐지 (거래대금 + 변동률 + 유동성 하이브리드)
    1. 거래대금(가격×거래량) 상위 30개 추출 → 실제 시장 관심도
    2. 그 중 24시간 변동률 높은 순으로 정렬 → 모멘텀
    3. 과도한 급등/급락 제외 (-30% ~ +50%) → 펌핑 회피
    4. 🔥 유동성 필터링 (거래대금 10억+, 호가깊이 500만원+) → 체결 리스크 감소
    5. 상위 n개 반환
    
    Args:
        n: 반환할 코인 개수
        min_trade_value: 최소 거래대금 (기본 10억원)
        min_orderbook_depth: 최소 호가 깊이 (기본 500만원)
    """
    tickers = pyupbit.get_tickers(fiat="KRW")
    coin_data = []
    
    for ticker in tickers:
        try:
            # 24시간 OHLCV 데이터
            ohlcv = pyupbit.get_ohlcv(ticker, interval="day", count=2)
            if ohlcv is None or len(ohlcv) < 2:
                continue
            
            # 거래대금 = 종가 × 거래량
            current_close = ohlcv['close'].iloc[-1]
            current_volume = ohlcv['volume'].iloc[-1]
            trade_value = current_close * current_volume
            
            # 🔥 유동성 필터 1: 거래대금 체크
            if trade_value < min_trade_value:
                continue
            
            # 🔥 유동성 필터 2: 호가 깊이 체크
            try:
                orderbook = pyupbit.get_orderbook(ticker)
                if orderbook and 'orderbook_units' in orderbook:
                    # 매도 1~5호가 총 수량 × 가격
                    ask_depth = sum([
                        unit['ask_size'] * unit['ask_price'] 
                        for unit in orderbook['orderbook_units'][:5]
                    ])
                    
                    if ask_depth < min_orderbook_depth:
                        print(f"⚠️ {ticker} 호가깊이 부족: {ask_depth:,.0f}원 (최소 {min_orderbook_depth:,.0f}원)")
                        continue
            except Exception as e:
                print(f"⚠️ {ticker} 호가 조회 실패: {e}")
                continue
            
            # 24시간 변동률 계산
            prev_close = ohlcv['close'].iloc[-2]
            change_rate = ((current_close - prev_close) / prev_close) * 100
            
            # 과도한 급등/급락 제외 (-30% ~ +50%)
            if -30 <= change_rate <= 50:
                coin_data.append({
                    'ticker': ticker,
                    'trade_value': trade_value,
                    'change_rate': change_rate
                })
        except Exception:
            continue
    
    # 1단계: 거래대금 상위 30개
    top_by_value = sorted(coin_data, key=lambda x: x['trade_value'], reverse=True)[:30]
    
    # 2단계: 그 중 변동률 높은 순 n개 (상승 우선)
    top_trend = sorted(top_by_value, key=lambda x: x['change_rate'], reverse=True)[:n]
    
    print(f"✅ 유동성 필터 통과: {len(top_trend)}개 코인 (거래대금 {min_trade_value/1e8:.0f}억+ / 호가깊이 {min_orderbook_depth/1e6:.0f}백만+)")
    
    return [coin['ticker'] for coin in top_trend]


def get_real_coin_news(coin_name, max_news=5):
    """
    CryptoCompare API로 실제 최신 뉴스 수집
    - 무료 API, 실시간 암호화폐 뉴스 제공
    - 특정 코인 관련 뉴스 필터링
    """
    try:
        response = requests.get(CRYPTOCOMPARE_NEWS_URL, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ 뉴스 API 응답 오류: {response.status_code}")
            return []
        
        news_data = response.json()
        if 'Data' not in news_data:
            return []
        
        # 코인명 관련 뉴스 필터링
        coin_keywords = [coin_name.upper(), coin_name.lower(), coin_name.capitalize()]
        relevant_news = []
        
        for article in news_data['Data'][:30]:  # 최근 30개 뉴스 검색
            title = article.get('title', '')
            body = article.get('body', '')
            
            # 코인명이 제목이나 본문에 포함된 뉴스만 선택
            if any(keyword in title or keyword in body for keyword in coin_keywords):
                relevant_news.append({
                    'title': title,
                    'body': body[:200],  # 본문 200자까지만
                    'published': datetime.fromtimestamp(article.get('published_on', 0)).strftime('%Y-%m-%d %H:%M'),
                    'source': article.get('source', 'Unknown')
                })
                
                if len(relevant_news) >= max_news:
                    break
        
        return relevant_news
    
    except Exception as e:
        print(f"❌ 뉴스 수집 오류: {e}")
        return []


def ai_analyze_coin_news(coin_name, news_articles):
    """
    실제 뉴스를 OpenAI로 분석하여 투자 위험도 평가
    - AI는 뉴스 검색이 아닌, 주어진 뉴스의 감정/위험도 분석만 수행
    """
    if not news_articles:
        return "최신 뉴스 없음 - 중립"
    
    # 뉴스를 텍스트로 정리
    news_text = f"{coin_name} 최신 뉴스:\n\n"
    for i, article in enumerate(news_articles, 1):
        news_text += f"{i}. [{article['published']}] {article['title']}\n"
        news_text += f"   {article['body']}\n\n"
    
    client = OpenAI()
    prompt = f"""다음은 {coin_name} 코인의 실제 최신 뉴스입니다. 
투자 관점에서 위험도를 분석하고, 다음 키워드가 있는지 평가해주세요:
- 악재, 해킹, 규제, 펌핑, 청산, 상장폐지, 사기, 소송

{news_text}

다음 형식으로 답변:
1. 투자 위험도: [안전/주의/위험]
2. 주요 이슈: [한 줄 요약]
3. 위험 키워드: [발견된 키워드 나열 또는 '없음']
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        analysis = response.choices[0].message.content
        print(f"📰 {coin_name} 뉴스 분석:\n{analysis}")
        return analysis
    except Exception as e:
        print(f"❌ {coin_name} 뉴스 분석 오류: {e}")
        return "뉴스 분석 실패"


def analyze_technical_indicators(ticker):
    """
    뉴스가 없을 때 기술적 분석으로 투자 판단
    - RSI, 거래량 급증, 가격 추세 분석
    - 보수적 기준: 명확한 신호만 투자 허용
    """
    try:
        # 일봉 데이터 수집 (7일)
        df = pyupbit.get_ohlcv(ticker, interval="day", count=7)
        if df is None or len(df) < 7:
            return None
        
        # RSI 계산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        # 거래량 분석 (최근 vs 평균)
        avg_volume = df['volume'][:-1].mean()
        current_volume = df['volume'].iloc[-1]
        volume_spike = ((current_volume / avg_volume) - 1) * 100 if avg_volume > 0 else 0
        
        # 가격 추세 (3일 연속 상승 체크)
        price_trend = df['close'].diff().iloc[-3:].sum()
        
        return {
            'rsi': current_rsi,
            'volume_spike': volume_spike,
            'price_trend': price_trend,
            'current_price': df['close'].iloc[-1]
        }
    except Exception as e:
        print(f"❌ {ticker} 기술적 분석 오류: {e}")
        return None


def ai_search_coin_news(coin_name, ticker=None):
    """
    하이브리드 분석 전략:
    1. CryptoCompare에서 실제 최신 뉴스 수집
    2. 뉴스 있음 → OpenAI 분석
    3. 뉴스 없음 → 기술적 분석으로 대체 (보수적)
    """
    # 1. 실제 뉴스 수집
    news_articles = get_real_coin_news(coin_name, max_news=5)
    
    if news_articles:
        # 2. 뉴스 있을 경우 → AI 분석
        analysis = ai_analyze_coin_news(coin_name, news_articles)
        return analysis
    
    # 3. 뉴스 없을 경우 → 기술적 분석
    print(f"ℹ️ {coin_name} 관련 최신 뉴스를 찾을 수 없습니다.")
    
    if not ticker:
        return "뉴스 없음 - 기술적 분석 불가"
    
    tech = analyze_technical_indicators(ticker)
    if not tech:
        return "뉴스 없음 - 기술적 분석 실패"
    
    # 보수적 투자 조건 - 완화된 기준
    # RSI < 40 (과매도 영역) + 거래량 급증 50% 이상
    if tech['rsi'] < 40 and tech['volume_spike'] > 50:
        msg = f"✅ 기술적 매수 신호 감지 (RSI:{tech['rsi']:.1f}, 거래량:{tech['volume_spike']:.0f}% ↑)"
        print(msg)
        return f"안전 - {msg}"
    
    # RSI < 35 (과매도) + 거래량 급증 30% 이상
    elif tech['rsi'] < 35 and tech['volume_spike'] > 30:
        msg = f"⚠️ 과매도 + 거래량 증가 (RSI:{tech['rsi']:.1f}, 거래량:{tech['volume_spike']:.0f}% ↑)"
        print(msg)
        return f"주의 - {msg}"
    
    # RSI 80 이상 (과매수) - 위험
    elif tech['rsi'] > 80:
        msg = f"위험 - 과매수 (RSI:{tech['rsi']:.1f})"
        print(f"🔴 {msg}")
        return msg
    
    else:
        msg = f"기술적 신호 부족 (RSI:{tech['rsi']:.1f}, 거래량:{tech['volume_spike']:.0f}%)"
        print(f"⏸️ {msg}")
        return f"뉴스 없음 - {msg}"


def execute_new_coin_trades(upbit, portfolio_coins, min_trade_amount, invest_ratio=0.05, check_interval_min=20, managed_coins=None):
    """
    신규/트렌드 코인에 소액 투자 및 짧은 주기 모니터링
    - invest_ratio: 전체 자산의 몇 %를 신규코인에 분산 투자할지
    - check_interval_min: 신규 코인만 몇 분마다 재체크할지
    - managed_coins: 이 함수에서 관리 중인 신규코인 set (손절/익절 대상)
    - 보유 중인 코인: 손절/익절 자동 실행
    - 반환: 현재 관리 중인 신규코인 set
    """
    if managed_coins is None:
        managed_coins = set()
    
    currently_held = set()  # 현재 보유 중인 신규코인
    
    # 1. 보유 중인 신규코인 손절/익절 체크 (우선순위)
    balances = upbit.get_balances()
    for balance in balances:
        ticker = f"KRW-{balance['currency']}"
        coin_name = balance['currency']
        
        # 관리 중인 신규코인만 체크 (포트폴리오 코인 제외)
        if ticker not in managed_coins or ticker in portfolio_coins:
            continue
        
        # 보유량 확인
        if float(balance['balance']) <= 0:
            # 보유량 없으면 관리 목록에서 제거
            managed_coins.discard(ticker)
            continue
        
        currently_held.add(ticker)
        
        try:
            # 평균 매수가 조회
            avg_buy_price = float(balance['avg_buy_price'])
            if avg_buy_price <= 0:
                continue
            
            # 현재가 조회 (안전한 재시도 로직 사용)
            current_price = get_safe_price(ticker, max_retries=3)
            if not current_price or current_price <= 0:
                print(f"❌ {coin_name} 모니터링 오류: 가격 조회 실패")
                continue
            
            # 수익률 계산
            profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
            balance_amount = float(balance['balance'])
            current_value = balance_amount * current_price
            
            # 손절 조건: -8% 이하 (변동성 고려한 손절)
            if profit_rate <= -8:
                print(f"🚨 [신규코인 손절] {coin_name}: {profit_rate:.1f}% 손실 → 즉시 매도")
                result = upbit.sell_market_order(ticker, balance_amount)
                if result:
                    print(f"✅ {coin_name} 손절 완료: {current_value:,.0f}원")
                    managed_coins.discard(ticker)  # 관리 목록에서 제거
                    log_decision(
                        action="SELL",
                        coin=coin_name,
                        allowed=True,
                        reason=f"신규코인 손절: {profit_rate:.1f}%",
                        context={"ticker": ticker, "profit_rate": profit_rate, "value": current_value}
                    )
                continue
            
            # 3차 익절 조건: +20% 이상 (전량 매도)
            if profit_rate >= 20:
                print(f"💰💰 [신규코인 3차익절] {coin_name}: {profit_rate:.1f}% 수익 → 전량 매도")
                result = upbit.sell_market_order(ticker, balance_amount)
                if result:
                    print(f"✅ {coin_name} 3차익절 완료: {current_value:,.0f}원 (수익: +{profit_rate:.1f}%)")
                    managed_coins.discard(ticker)  # 관리 목록에서 제거
                    log_decision(
                        action="SELL",
                        coin=coin_name,
                        allowed=True,
                        reason=f"신규코인 3차익절: {profit_rate:.1f}%",
                        context={"ticker": ticker, "profit_rate": profit_rate, "value": current_value}
                    )
                continue
            
            # 2차 익절 조건: +15% 이상 (50% 추가 매도)
            if profit_rate >= 15 and current_value >= min_trade_amount:
                partial_amount = balance_amount * 0.5
                print(f"💰 [신규코인 2차익절] {coin_name}: {profit_rate:.1f}% → 50% 추가 매도")
                result = upbit.sell_market_order(ticker, partial_amount)
                if result:
                    sold_value = partial_amount * current_price
                    print(f"✅ {coin_name} 2차익절 완료: {sold_value:,.0f}원 (남은 50%는 +20% 목표)")
                    log_decision(
                        action="SELL",
                        coin=coin_name,
                        allowed=True,
                        reason=f"신규코인 2차익절: {profit_rate:.1f}% (50%)",
                        context={"ticker": ticker, "profit_rate": profit_rate, "sold_value": sold_value}
                    )
                continue
            
            # 1차 익절 조건: +10% 이상 (40% 원금 회수)
            if profit_rate >= 10 and current_value >= min_trade_amount * 2:
                partial_amount = balance_amount * 0.4
                print(f"💵 [신규코인 1차익절] {coin_name}: {profit_rate:.1f}% → 40% 원금 회수")
                result = upbit.sell_market_order(ticker, partial_amount)
                if result:
                    sold_value = partial_amount * current_price
                    print(f"✅ {coin_name} 1차익절 완료: {sold_value:,.0f}원 (남은 60%는 +15% 목표)")
                    log_decision(
                        action="SELL",
                        coin=coin_name,
                        allowed=True,
                        reason=f"신규코인 1차익절: {profit_rate:.1f}% (40%)",
                        context={"ticker": ticker, "profit_rate": profit_rate, "sold_value": sold_value}
                    )
                continue
            
            # 보유 중 (모니터링)
            if profit_rate > 0:
                if profit_rate >= 15:
                    print(f"📈 [신규코인 보유] {coin_name}: +{profit_rate:.1f}% (2차 목표 도달, 3차: +20%)")
                elif profit_rate >= 10:
                    print(f"📈 [신규코인 보유] {coin_name}: +{profit_rate:.1f}% (1차 목표 도달, 2차: +15%)")
                else:
                    print(f"📈 [신규코인 보유] {coin_name}: +{profit_rate:.1f}% (1차 목표: +10%, 2차: +15%, 3차: +20%)")
            else:
                print(f"📉 [신규코인 보유] {coin_name}: {profit_rate:.1f}% (손절: -8%)")
                
        except Exception as e:
            print(f"❌ {coin_name} 모니터링 오류: {e}")
            continue
    
    # 2. 새로운 투자 기회 탐색 (보유 중이 아닐 때만)
    top_coins = get_top_trend_coins()
    current_krw = upbit.get_balance("KRW")
    total_value = current_krw
    for coin in [c.split('-')[1] for c in portfolio_coins]:
        ticker = f"KRW-{coin}"
        balance = upbit.get_balance(ticker)
        if balance > 0:
            orderbook = get_safe_orderbook(ticker)
            if orderbook:
                price = orderbook['orderbook_units'][0]['ask_price']
                total_value += balance * price
    max_invest = total_value * invest_ratio / len(top_coins) if top_coins else 0

    for ticker in top_coins:
        coin_name = ticker.replace("KRW-", "")
        # 이미 보유 중이거나 포트폴리오 코인이면 건너뛰기 (중복 매수 방지)
        if ticker not in portfolio_coins and ticker not in currently_held:
            # 하이브리드 분석: 뉴스 우선, 없으면 기술적 분석
            news_summary = ai_search_coin_news(coin_name, ticker=ticker)
            
            # 위험 키워드 체크 (뉴스 분석 결과)
            if any(word in news_summary for word in ["악재", "해킹", "규제", "청산", "상장폐지", "사기", "소송"]):
                print(f"⚠️ {coin_name} 투자 위험 신호 감지 - 매수 건너뜀")
                log_decision(
                    action="BUY",
                    coin=coin_name,
                    allowed=False,
                    reason=f"뉴스 위험 키워드 감지: {news_summary}",
                    context={"ticker": ticker, "news": news_summary}
                )
                continue
            
            # 기술적 신호 부족 시에도 일부 허용 (RSI 기반)
            if "기술적 신호 부족" in news_summary:
                # 기술 지표 재확인
                tech = analyze_technical_indicators(ticker)
                if tech and (tech['rsi'] < 45 or tech['volume_spike'] > 40):
                    print(f"✅ {coin_name} 뉴스 없지만 기술적 지표 양호 - 매수 진행")
                else:
                    print(f"⏸️ {coin_name} 뉴스 없음 + 기술적 신호 부족 - 매수 건너뜀")
                    log_decision(
                        action="BUY",
                        coin=coin_name,
                        allowed=False,
                        reason=f"뉴스 없음 + 기술적 신호 부족",
                        context={"ticker": ticker, "analysis": news_summary}
                    )
                    continue
            orderbook = get_safe_orderbook(ticker)
            if not orderbook:
                log_decision(
                    action="BUY",
                    coin=coin_name,
                    allowed=False,
                    reason="호가 정보 없음 또는 비정상",
                    context={"ticker": ticker}
                )
                continue
            price = orderbook['orderbook_units'][0]['ask_price']
            amount = max_invest / price
            if amount * price >= min_trade_amount and current_krw >= amount * price:
                result = upbit.buy_market_order(ticker, amount * price)
                if result:
                    print(f"✅ 신규코인 매수: {ticker} {amount:.4f}개 ({amount*price:,.0f}원)")
                    print(f"📊 분할익절 전략: 손절 -8% | 1차익절 +10%(40%) | 2차익절 +15%(50%) | 3차익절 +20%(100%) | 모니터링 5분")
                    managed_coins.add(ticker)  # 관리 목록에 추가
                    currently_held.add(ticker)
                    log_decision(
                        action="BUY",
                        coin=coin_name,
                        allowed=True,
                        reason="신규/트렌드 코인 자동 매수",
                        context={"ticker": ticker, "amount": amount, "price": price, "news": news_summary}
                    )
    
    # 3. 현재 관리 중인 신규코인 반환
    return currently_held
