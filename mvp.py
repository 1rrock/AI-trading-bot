import os
from dotenv import load_dotenv
load_dotenv()

# 1. 업비트 차트 데이터 가져오기 (30일 일봉)
import pyupbit
df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=30)

# 필요한 요약 정보만 추출 (최근 5일 종가, 평균 거래량, 변동률)
recent_close = df['close'][-5:].tolist()
avg_volume = df['volume'][-5:].mean()
change_rate = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
summary = {
    "recent_close": recent_close,
    "avg_volume": avg_volume,
    "change_rate": change_rate
}

# 2. AI에게 요약 데이터만 제공하고 판단 받기
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {
            "role": "system",
            "content": "You're a Bitcoin investment expert. Based on the provided summary data, tell me which option to choose: buy, sell, or hold. Respond in JSON format. Example: {\"decision\": \"buy\", \"reason\": \"some technical reason\"}"
        },
        {
            "role": "user",
            "content": str(summary)
        }
    ],
    response_format={"type": "json_object"},
    temperature=1,
    max_tokens=512
)
result = response.choices[0].message.content

# 3. AI의 판단에 따라 실제로 자동매매 진행하기
import json
result = json.loads(result)
access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")
upbit = pyupbit.Upbit(access, secret)

if result['decision'] == 'buy':
    my_krw = upbit.get_balance("KRW")
    if my_krw*0.9995 > 5000:  # 최소 주문금액 5000원 이상일 때 매수
        print(upbit.buy_market_order("KRW-BTC", my_krw*0.9995))
        print("buy", result['reason'])
elif result['decision'] == 'sell':
    my_btc = upbit.get_balance("KRW-BTC")
    current_price = pyupbit.get_orderbook(ticker="KRW-BTC")['orderbook_units'][0]['ask_price']
    if my_btc*current_price > 5000:
        print(upbit.sell_market_order("KRW-BTC", upbit.get_balance("KRW-BTC")))
        print("sell", result['reason'])
elif result['decision'] == 'hold':
    print("hold", result['reason'])
