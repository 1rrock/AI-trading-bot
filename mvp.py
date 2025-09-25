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

def get_ai_decision(summary):
    client = OpenAI()
    prompt = (
        "You're a Bitcoin investment expert and a value investor. "
        "I focus on intrinsic value and long-term growth potential rather than short-term price movements or market sentiment. "
        "I always secure a margin of safety before making decisions, avoid speculative approaches, and rely on rational, data-driven analysis. "
        "I do not get swayed by market bubbles or fear, and I follow principles of steady diversification and risk management. "
        "In Bitcoin investment, I apply these value investing principles, carefully considering long-term growth and intrinsic value before making buy, sell, or hold decisions. "
        "Based on the provided chart data, tell me which option to choose: buy, sell, or hold. "
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
def trade_by_decision(result, upbit, trade_ratio=0.2):
    if result['decision'] == 'buy':
        my_krw = upbit.get_balance("KRW")
        amount = my_krw * trade_ratio * 0.9995
        if amount > 5000:
            print(upbit.buy_market_order("KRW-BTC", amount))
            print("buy", result['reason'])
    elif result['decision'] == 'sell':
        my_btc = upbit.get_balance("KRW-BTC")
        amount = my_btc * trade_ratio
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")['orderbook_units'][0]['ask_price']
        if amount * current_price > 5000:
            print(upbit.sell_market_order("KRW-BTC", amount))
            print("sell", result['reason'])
    elif result['decision'] == 'hold':
        print("hold", result['reason'])

if __name__ == "__main__":
    load_dotenv()
    df = get_upbit_data()
    rsi = calculate_rsi(df['close']).iloc[-1]
    ma5 = df['close'].rolling(window=5).mean().iloc[-1]
    ma20 = df['close'].rolling(window=20).mean().iloc[-1]
    fng = get_fear_greed_index()
    print(fng)
    news = get_news_headlines()
    summary = make_summary(df, rsi, ma5, ma20, fng, news)
    result = get_ai_decision(summary)
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    upbit = pyupbit.Upbit(access, secret)
    trade_by_decision(result, upbit)
