"""
시장 데이터 수집 모듈
코인 가격, 지표, 공포탐욕지수 등 수집
"""

import pyupbit
import requests
import pandas as pd


def get_portfolio_data(portfolio_coins, data_period):
    """
    4개 코인 포트폴리오 데이터 수집 - 다중 타임프레임
    
    Args:
        portfolio_coins: 포트폴리오 코인 리스트
        data_period: 데이터 기간 (일)
    
    Returns:
        dict: 코인별 타임프레임 데이터
    """
    portfolio_data = {}
    
    timeframes = {
        'day': data_period,      # 일봉
        'hour4': 168,           # 4시간봉 1주일 (168시간)
        'hour1': 168            # 1시간봉 1주일
    }
    
    for ticker in portfolio_coins:
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
    """
    RSI (Relative Strength Index) 계산
    
    Args:
        series: 가격 시리즈
        period: RSI 기간 (기본 14)
    
    Returns:
        Series: RSI 값
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def get_fear_greed_index():
    """
    공포탐욕지수 조회
    
    Returns:
        dict: {"value": 값, "text": 텍스트}
    """
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1")
        data = resp.json()
        return {
            "value": data['data'][0]['value'],
            "text": data['data'][0]['value_classification']
        }
    except Exception as e:
        return {"value": None, "text": None}
