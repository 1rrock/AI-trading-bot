import os
from dotenv import load_dotenv
import pyupbit
import requests
import pandas as pd
from openai import OpenAI
import json
import time

def get_upbit_data():
    df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=30)
    return df

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

CACHE_FILE = "news_cache.json"
CACHE_DURATION = 4 * 60 * 60  # 4시간(초)

# AI 결정 캐시 관리
AI_DECISION_CACHE_FILE = "ai_decision_cache.json"
AI_CACHE_DURATION = 45 * 60  # 45분 캐시 (3번의 15분 주기)

# MD 거래 로그 파일
TRADING_LOG_MD = "trading_log.md"

def get_news_headlines():
    try:
        # 캐시 파일이 있으면, 4시간 이내면 캐시 데이터 반환
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
            if time.time() - cache["timestamp"] < CACHE_DURATION:
                return cache["data"]
        # API 호출 및 캐시 저장
        resp = requests.get("https://newsdata.io/api/1/latest?apikey=pub_ce231ca37821478fa603c0bbc16ca2d8&q=bitcoin")
        data = resp.json()
        headlines = [item['title'] for item in data.get('results', [])]
        with open(CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "data": headlines}, f)
        return headlines
    except Exception as e:
        return []

def make_summary(df, rsi, ma5, ma20, fng, news):
    return {
        "recent_close": df['close'][-5:].tolist(),
        "avg_volume": df['volume'][-5:].mean(),
        "change_rate": (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100,
        "rsi": rsi,
        "ma5": ma5,
        "ma20": ma20,
        "fear_greed_index": fng,
        "news_headlines": news
    }

def should_call_ai(summary, last_summary=None, threshold=0.05):
    """중요한 변화가 있을 때만 AI 호출"""
    if last_summary is None:
        return True
    
    # 가격 변화율이 임계값을 초과하면 AI 호출
    price_change = abs(summary['change_rate'] - last_summary.get('change_rate', 0))
    rsi_change = abs(summary['rsi'] - last_summary.get('rsi', 0))
    
    # 중요한 변화 조건들
    significant_change = (
        price_change > threshold * 100 or  # 5% 이상 가격 변화
        rsi_change > 10 or                 # RSI 10 이상 변화
        summary['fear_greed_index']['value'] != last_summary.get('fear_greed_index', {}).get('value')
    )
    
    return significant_change

def simple_rule_filter(summary):
    """간단한 규칙으로 먼저 필터링"""
    rsi = summary['rsi']
    change_rate = summary['change_rate']
    ma5 = summary['ma5']
    ma20 = summary['ma20']
    
    # 명확한 상황에서는 AI 호출 없이 결정
    if rsi > 80 and change_rate > 5:  # 과매수 + 급등
        return {"decision": "sell", "reason": "Rule-based: Overbought condition (RSI>80) with high price increase"}
    elif rsi < 20 and change_rate < -5:  # 과매도 + 급락
        return {"decision": "buy", "reason": "Rule-based: Oversold condition (RSI<20) with significant price drop"}
    elif abs(change_rate) < 1 and 30 < rsi < 70:  # 횡보장
        return {"decision": "hold", "reason": "Rule-based: Sideways market with neutral RSI"}
    elif ma5 < ma20 * 0.95 and rsi < 30:  # 강한 하락 트렌드 + 과매도
        return {"decision": "buy", "reason": "Rule-based: Strong downtrend with oversold condition"}
    elif ma5 > ma20 * 1.05 and rsi > 70:  # 강한 상승 트렌드 + 과매수
        return {"decision": "sell", "reason": "Rule-based: Strong uptrend with overbought condition"}
    
    return None  # AI 결정 필요

def get_cached_ai_decision(summary):
    """캐시된 AI 결정 반환 또는 새로운 결정 요청"""
    try:
        if os.path.exists(AI_DECISION_CACHE_FILE):
            with open(AI_DECISION_CACHE_FILE, "r") as f:
                cache = json.load(f)
            
            # 캐시가 유효하고 중요한 변화가 없으면 캐시 사용
            if (time.time() - cache["timestamp"] < AI_CACHE_DURATION and
                not should_call_ai(summary, cache.get("last_summary"))):
                print("Using cached AI decision")
                return cache["decision"]
        
        # 새로운 AI 결정 요청
        print("Requesting new AI decision")
        decision = get_ai_decision(summary)
        
        # 캐시 저장
        with open(AI_DECISION_CACHE_FILE, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "decision": decision,
                "last_summary": summary
            }, f)
        
        return decision
        
    except Exception as e:
        print(f"AI decision error: {e}")
        return {"decision": "hold", "reason": "AI service unavailable"}

def get_smart_decision(summary):
    """규칙 기반 필터 + AI 결정 조합"""
    # 1단계: 간단한 규칙으로 필터링
    simple_decision = simple_rule_filter(summary)
    if simple_decision:
        print("Using rule-based decision")
        return simple_decision
    
    # 2단계: AI 결정 (캐시 활용)
    return get_cached_ai_decision(summary)

def log_to_markdown(decision, reason, price, rsi, ma5, ma20, fng, decision_type="rule"):
    """거래 결정을 MD 파일에 로깅"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    date_only = time.strftime('%Y-%m-%d')
    
    # 결정에 따른 이모지 설정
    decision_emoji = {
        'buy': '🟢 📈',
        'sell': '🔴 📉', 
        'hold': '🟡 ⏸️'
    }
    
    # 결정 타입에 따른 배지
    type_badge = {
        'rule': '`🤖 RULE`',
        'ai': '`🧠 AI`',
        'cached': '`💾 CACHED`'
    }
    
    log_entry = f"""
## {decision_emoji.get(decision, '⚪')} {decision.upper()} Decision

**Time:** {timestamp}  
**Type:** {type_badge.get(decision_type, '`UNKNOWN`')}  
**Price:** {price:,.0f} KRW  

### 📊 Market Data
- **RSI:** {rsi:.1f}
- **MA5:** {ma5:,.0f} KRW
- **MA20:** {ma20:,.0f} KRW  
- **Fear & Greed:** {fng['value']} ({fng['text']})

### 💭 Decision Reason
> {reason}

---

"""
    
    # MD 파일이 없으면 헤더 생성
    if not os.path.exists(TRADING_LOG_MD):
        header = f"""# 🤖 Bitcoin Trading Bot Log

📅 **Started:** {timestamp}  
🎯 **Strategy:** Smart Decision System (Rule-based + AI Caching)  
⏰ **Frequency:** Every 15 minutes  

---

"""
        with open(TRADING_LOG_MD, "w", encoding='utf-8') as f:
            f.write(header)
    
    # 로그 엔트리를 파일 상단에 추가 (최신 기록을 위로)
    try:
        with open(TRADING_LOG_MD, "r", encoding='utf-8') as f:
            existing_content = f.read()
        
        # 헤더 부분과 로그 부분을 분리
        parts = existing_content.split("---\n", 2)
        if len(parts) >= 2:
            header_part = parts[0] + "---\n"
            log_part = parts[1] if len(parts) > 1 else ""
            
            # 새 로그를 기존 로그 위에 추가
            new_content = header_part + log_entry + log_part
        else:
            # 분리가 안되면 그냥 추가
            new_content = existing_content + log_entry
        
        with open(TRADING_LOG_MD, "w", encoding='utf-8') as f:
            f.write(new_content)
            
    except Exception as e:
        print(f"MD logging error: {e}")
        # 에러 발생시 파일 끝에 추가
        with open(TRADING_LOG_MD, "a", encoding='utf-8') as f:
            f.write(log_entry)

def get_ai_decision(summary):
    client = OpenAI()
    prompt = (
        "You're a Bitcoin investment expert and a value investor. "
        "I focus on intrinsic value and long-term growth potential rather than short-term price movements or market sentiment. "
        "I always secure a margin of safety before making decisions, avoid speculative approaches, and rely on rational, data-driven analysis. "
        "I do not get swayed by market bubbles or fear, and I follow principles of steady diversification and risk management. "
        "In Bitcoin investment, I apply these value investing principles, carefully considering long-term growth and intrinsic value before making buy, sell, or hold decisions. "
        "Based on the provided summary data including price, volume, RSI, moving averages, fear-greed index, and latest news headlines, apply the above investment philosophy and tell me which option to choose: buy, sell, or hold. "
        "Response in json format. "
        "Response Example: "
        "{\"decision\": \"buy\", \"reason\": \"some technical reason\"} "
        "{\"decision\": \"sell\", \"reason\": \"some technical reason\"} "
        "{\"decision\": \"hold\", \"reason\": \"some technical reason\"}"
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(summary)}
        ],
        response_format={"type": "json_object"},
        temperature=1,
        max_tokens=512
    )
    return json.loads(response.choices[0].message.content)

# 매수/매도 시 전체 자산의 20%만 거래
def trade_by_decision(result, upbit, current_price, rsi, ma5, ma20, fng, trade_ratio=0.2):
    # 결정 타입 판별 (reason에서 추출)
    if "Rule-based" in result['reason']:
        decision_type = "rule"
    elif "cached" in result['reason'].lower():
        decision_type = "cached" 
    else:
        decision_type = "ai"
    
    if result['decision'] == 'buy':
        my_krw = upbit.get_balance("KRW")
        amount = my_krw * trade_ratio * 0.9995
        if amount > 5000:
            print(upbit.buy_market_order("KRW-BTC", amount))
            print("buy", result['reason'])
        else:
            print(f"BUY SKIPPED: Insufficient balance ({amount:.0f} KRW < 5000 KRW)")
    elif result['decision'] == 'sell':
        my_btc = upbit.get_balance("KRW-BTC")
        amount = my_btc * trade_ratio
        if amount * current_price > 5000:
            print(upbit.sell_market_order("KRW-BTC", amount))
            print("sell", result['reason'])
        else:
            print(f"SELL SKIPPED: Insufficient BTC balance ({amount:.6f} BTC)")
    elif result['decision'] == 'hold':
        print("hold", result['reason'])
    
    # MD 파일에 로깅
    log_to_markdown(
        decision=result['decision'],
        reason=result['reason'], 
        price=current_price,
        rsi=rsi,
        ma5=ma5,
        ma20=ma20,
        fng=fng,
        decision_type=decision_type
    )

def main_trading_loop():
    """15분 간격으로 지속 실행되는 메인 트레이딩 루프"""
    load_dotenv()
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    upbit = pyupbit.Upbit(access, secret)
    
    print("Starting Bitcoin trading bot with smart decision system...")
    print("- Rule-based filtering for clear market conditions")
    print("- AI caching for 45 minutes (3 cycles of 15 minutes)")
    print("- Market change detection to minimize AI calls")
    print("=" * 60)
    
    while True:
        try:
            print(f"\n=== Trading cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
            
            # 데이터 수집
            df = get_upbit_data()
            rsi = calculate_rsi(df['close']).iloc[-1]
            ma5 = df['close'].rolling(window=5).mean().iloc[-1]
            ma20 = df['close'].rolling(window=20).mean().iloc[-1]
            fng = get_fear_greed_index()
            news = get_news_headlines()  # 이미 4시간 캐시 적용
            
            summary = make_summary(df, rsi, ma5, ma20, fng, news)
            
            # 현재 가격 정보 출력
            current_price = df['close'].iloc[-1]
            print(f"Current BTC Price: {current_price:,.0f} KRW")
            print(f"RSI: {rsi:.1f}, MA5: {ma5:,.0f}, MA20: {ma20:,.0f}")
            print(f"Change Rate: {summary['change_rate']:.2f}%")
            print(f"Fear & Greed Index: {fng['value']} ({fng['text']})")
            
            # 스마트 결정 (규칙 기반 + AI 캐싱)
            result = get_smart_decision(summary)
            
            # 거래 실행 (MD 로깅 포함)
            trade_by_decision(result, upbit, current_price, rsi, ma5, ma20, fng)
            
            print(f"Decision: {result['decision']}")
            print(f"Reason: {result['reason']}")
            print("Waiting 15 minutes for next cycle...")
            print("=" * 60)
            
            # 15분 대기
            time.sleep(15 * 60)
            
        except KeyboardInterrupt:
            print("\n\nTrading bot stopped by user.")
            break
        except Exception as e:
            print(f"Error in trading loop: {e}")
            print("Waiting 1 minute before retry...")
            time.sleep(60)  # 에러 시 1분 후 재시도

if __name__ == "__main__":
    main_trading_loop()
