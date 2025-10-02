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

# === 컨트래리언 봇 전용 설정 로드 ===
def load_contrarian_config():
    """컨트래리언 봇 설정 파일에서 설정을 로드합니다."""
    try:
        with open('config_contrarian.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("config_contrarian.json 파일을 찾을 수 없습니다. 기본값 사용")
        return get_contrarian_default_config()
    except json.JSONDecodeError as e:
        logging.error(f"config_contrarian.json 파일 파싱 오류: {e}. 기본값 사용")
        return get_contrarian_default_config()

def get_contrarian_default_config():
    """컨트래리언 봇 기본 설정값을 반환합니다."""
    return {
        "trading": {"base_trade_ratio": 0.30, "stop_loss_percent": 20, "min_trade_amount": 3000},
        "technical_analysis": {"rsi_oversold": 25, "rsi_overbought": 75, "data_period_days": 20},
        "market_conditions": {"bull_market_threshold": 8, "bear_market_threshold": -8, 
                            "fear_greed_extreme_fear": 30, "fear_greed_extreme_greed": 70},
        "coins": {
            "list": ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"],
            "target_allocation": {"KRW-BTC": 0.20, "KRW-ETH": 0.20, "KRW-SOL": 0.40, "KRW-XRP": 0.20}
        },
        "cache": {"cache_file": "contrarian_news_cache.json", "cache_duration_hours": 2},
        "safety": {"min_cash_ratio": 0.05, "max_portfolio_concentration": 0.70},
        "trading_constraints": {"max_single_coin_ratio": 0.70, "ai_confidence_minimum": 0.40},
        "check_intervals": {
            "extreme_volatility_threshold": 6.0, "extreme_volatility_interval": 5,
            "high_volatility_threshold": 4.0, "high_volatility_interval": 10,
            "medium_volatility_threshold": 2.5, "medium_volatility_interval": 20,
            "low_volatility_interval": 40, "default_interval": 30
        },
        "contrarian_strategy": {
            "signal_inversion": True,
            "momentum_threshold": 0.60,
            "contrarian_multiplier": 1.5,
            "fear_greed_inversion": True
        }
    }

# 컨트래리언 설정 로드
CONFIG = load_contrarian_config()

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

# 컨트래리언 전략 설정
SIGNAL_INVERSION = CONFIG["contrarian_strategy"]["signal_inversion"]
MOMENTUM_THRESHOLD = CONFIG["contrarian_strategy"]["momentum_threshold"]
CONTRARIAN_MULTIPLIER = CONFIG["contrarian_strategy"]["contrarian_multiplier"]
FEAR_GREED_INVERSION = CONFIG["contrarian_strategy"]["fear_greed_inversion"]

# 체크 주기 설정
CHECK_INTERVALS = CONFIG["check_intervals"]
HIGH_VOLATILITY_THRESHOLD = CONFIG["check_intervals"]["high_volatility_threshold"]

# === 컨트래리언 전략 핵심 함수 ===
def invert_ai_signals(ai_signals):
    """AI 신호를 컨트래리언 전략에 따라 반전시킵니다."""
    if not SIGNAL_INVERSION:
        return ai_signals
    
    inverted_signals = {}
    
    for coin, signal_data in ai_signals.items():
        original_signal = signal_data.get('signal', 'HOLD')
        confidence = signal_data.get('confidence', 0.5)
        reason = signal_data.get('reason', 'No reason provided')
        
        # 신뢰도가 MOMENTUM_THRESHOLD 이상일 때만 반전 적용
        if confidence >= MOMENTUM_THRESHOLD:
            # 신호 반전 로직
            if original_signal == 'STRONG_BUY':
                new_signal = 'SELL'
                inversion_reason = f"🔄 컨트래리언: STRONG_BUY→SELL (과도한 낙관 경계)"
            elif original_signal == 'BUY':
                new_signal = 'SELL'
                inversion_reason = f"🔄 컨트래리언: BUY→SELL (상승 모멘텀 역매매)"
            elif original_signal == 'SELL':
                new_signal = 'BUY'
                inversion_reason = f"🔄 컨트래리언: SELL→BUY (하락 시 기회 포착)"
            elif original_signal == 'EMERGENCY_SELL':
                new_signal = 'STRONG_BUY'
                inversion_reason = f"🔄 컨트래리언: EMERGENCY_SELL→STRONG_BUY (공황 매수)"
            else:  # HOLD
                new_signal = 'HOLD'
                inversion_reason = f"🔄 컨트래리언: HOLD 유지"
        else:
            # 신뢰도가 낮으면 원본 신호 유지
            new_signal = original_signal
            inversion_reason = f"📊 신뢰도 부족 ({confidence:.1%}) - 원본 신호 유지"
        
        inverted_signals[coin] = {
            'signal': new_signal,
            'confidence': confidence,
            'reason': f"{inversion_reason} | 원본: {reason}",
            'original_signal': original_signal,
            'inverted': confidence >= MOMENTUM_THRESHOLD,
            'stop_loss': signal_data.get('stop_loss', 0),
            'take_profit': signal_data.get('take_profit', 0),
            'recommended_size': signal_data.get('recommended_size', 0)
        }
    
    return inverted_signals

def apply_contrarian_position_sizing(base_ratio, signal_data, market_context):
    """컨트래리언 전략에 따른 포지션 사이징 적용"""
    signal = signal_data.get('signal', 'HOLD')
    confidence = signal_data.get('confidence', 0.5)
    was_inverted = signal_data.get('inverted', False)
    
    # 기본 배수
    multiplier = 1.0
    
    # 컨트래리언 신호인 경우 더 공격적
    if was_inverted and signal in ['BUY', 'STRONG_BUY']:
        multiplier *= CONTRARIAN_MULTIPLIER  # 1.5배
        print(f"  🚀 컨트래리언 포지션 강화: {multiplier:.1f}배")
    
    # 신뢰도에 따른 추가 조정
    if signal == 'STRONG_BUY' and confidence > 0.8:
        multiplier *= 2.0  # 매우 공격적
    elif signal == 'BUY' and confidence > 0.6:
        multiplier *= 1.5
    elif confidence < 0.5:
        multiplier *= 0.7  # 신뢰도 낮으면 축소
    
    # 공포-탐욕 지수 역해석 (컨트래리언 전략)
    if FEAR_GREED_INVERSION:
        fng_value = market_context.get('fear_greed_index', {}).get('value', '50')
        try:
            fng_numeric = int(fng_value)
            if fng_numeric <= FEAR_GREED_EXTREME_FEAR:  # 극도의 공포
                multiplier *= 1.3  # 공포 시 더 매수
                print(f"  😱 극도의 공포 활용: {multiplier:.1f}배")
            elif fng_numeric >= FEAR_GREED_EXTREME_GREED:  # 극도의 탐욕
                multiplier *= 0.8  # 탐욕 시 축소
                print(f"  🤑 극도의 탐욕 경계: {multiplier:.1f}배")
        except:
            pass
    
    final_ratio = min(base_ratio * multiplier, 0.50)  # 최대 50% 제한
    return final_ratio, multiplier

def setup_contrarian_logging():
    """컨트래리언 봇 전용 로거 설정"""
    # 거래 로거 설정
    trade_logger = logging.getLogger('contrarian_trade_logger')
    trade_logger.setLevel(logging.INFO)
    
    # 핸들러 중복 방지
    if not trade_logger.hasHandlers():
        trade_handler = logging.FileHandler(f'contrarian_trades_{datetime.now().strftime("%Y%m%d")}.json', encoding='utf-8')
        trade_handler.setFormatter(logging.Formatter('%(message)s'))
        trade_logger.addHandler(trade_handler)
    
    # AI 신호 로거 설정
    signal_logger = logging.getLogger('contrarian_signal_logger')
    signal_logger.setLevel(logging.INFO)
    if not signal_logger.hasHandlers():
        signal_handler = logging.FileHandler(f'contrarian_ai_signals_{datetime.now().strftime("%Y%m%d")}.json', encoding='utf-8')
        signal_handler.setFormatter(logging.Formatter('%(message)s'))
        signal_logger.addHandler(signal_handler)
    
    # 성과 로거 설정
    performance_logger = logging.getLogger('contrarian_performance_logger')
    performance_logger.setLevel(logging.INFO)
    if not performance_logger.hasHandlers():
        performance_handler = logging.FileHandler(f'contrarian_performance_{datetime.now().strftime("%Y%m%d")}.json', encoding='utf-8')
        performance_handler.setFormatter(logging.Formatter('%(message)s'))
        performance_logger.addHandler(performance_handler)
    
    print(f"📁 컨트래리언 봇 로그 설정 완료:")
    print(f"  📈 거래 로그: contrarian_trades_{datetime.now().strftime('%Y%m%d')}.json")
    print(f"  🧠 AI 신호: contrarian_ai_signals_{datetime.now().strftime('%Y%m%d')}.json") 
    print(f"  📊 성과: contrarian_performance_{datetime.now().strftime('%Y%m%d')}.json")

# === 기존 함수들을 컨트래리언 전략에 맞게 수정 ===

def get_portfolio_data():
    """4개 코인 포트폴리오 데이터 수집 - 다중 타임프레임 (컨트래리언 최적화)"""
    portfolio_data = {}
    
    timeframes = {
        'day': DATA_PERIOD,      # 일봉 20일 (더 짧은 기간)
        'hour4': 120,           # 4시간봉 5일 (120시간)
        'hour1': 120            # 1시간봉 5일
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
                    
                    # 컨트래리언 지표 추가 계산
                    if tf == 'day':
                        # 역추세 확인을 위한 추가 지표
                        df['sma_short'] = df['close'].rolling(window=5).mean()
                        df['sma_long'] = df['close'].rolling(window=15).mean()
                        df['contrarian_signal'] = (df['sma_short'] < df['sma_long']).astype(int)  # 하락 추세 시 1
                        portfolio_data[coin_name][tf] = df
            
            print(f"  ✅ {coin_name} 컨트래리언 데이터 수집: {timeframes['day']}일")
        except Exception as e:
            print(f"  ❌ {ticker} 데이터 수집 실패: {e}")
            
    return portfolio_data

def get_fear_greed_index():
    """공포탐욕지수 조회 (컨트래리언 해석용)"""
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            fng_value = data['data'][0]['value']
            fng_text = data['data'][0]['value_classification']
            
            # 컨트래리언 해석 추가
            fng_numeric = int(fng_value)
            if FEAR_GREED_INVERSION:
                if fng_numeric <= FEAR_GREED_EXTREME_FEAR:
                    contrarian_view = "🔥 컨트래리언 기회: 극도의 공포 → 매수 기회"
                elif fng_numeric >= FEAR_GREED_EXTREME_GREED:
                    contrarian_view = "⚠️ 컨트래리언 경고: 극도의 탐욕 → 매도 기회"
                else:
                    contrarian_view = "📊 중립적 심리 상태"
            else:
                contrarian_view = ""
                
            return {
                'value': fng_value,
                'text': fng_text,
                'contrarian_view': contrarian_view
            }
    except Exception as e:
        print(f"공포탐욕지수 조회 실패: {e}")
        return {'value': '50', 'text': 'Neutral', 'contrarian_view': ''}

def calculate_rsi(prices, period=14):
    """RSI 계산 (컨트래리언 해석용)"""
    if len(prices) < period:
        return 50  # 기본값
    
    prices = pd.Series(prices)
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

def get_contrarian_ai_signals(portfolio_summary):
    """컨트래리언 전략을 위한 AI 신호 생성 시스템"""
    client = OpenAI()
    
    # 컨트래리언 전용 프롬프트
    prompt = (
        "You're a CONTRARIAN cryptocurrency trading AI expert specializing in counter-trend strategies. "
        "Your philosophy: 'Be fearful when others are greedy, and greedy when others are fearful.' "
        "Key contrarian principles: "
        "1. INVERSE MOMENTUM: Buy on weakness, sell on strength "
        "2. CROWD PSYCHOLOGY: Act opposite to market sentiment when extreme "
        "3. VALUE HUNTING: Find opportunities in oversold/panic conditions "
        "4. RISK-ON APPROACH: Higher position sizes when conditions align "
        "\n"
        "🔄 CONTRARIAN SIGNAL GUIDELINES: "
        "- When RSI > 70 AND strong uptrend: Consider contrarian SELL (momentum exhaustion) "
        "- When RSI < 30 AND strong downtrend: Consider contrarian BUY (oversold bounce) "
        "- High Fear & Greed (>70): Look for distribution opportunities "
        "- Low Fear & Greed (<30): Look for accumulation opportunities "
        "- Volume spikes + extreme moves: Potential reversal points "
        "\n"
        "⚡ AGGRESSIVE POSITION SIZING: "
        "- Base allocation: 30% per trade (vs conservative 15%) "
        "- High conviction contrarian plays: up to 50% allocation "
        "- Stop losses: Wider (20% vs 15%) to avoid whipsaws "
        "- Take profits: More ambitious targets "
        "\n"
        f"Current market conditions for contrarian analysis: "
        f"- RSI thresholds: Oversold < {RSI_OVERSOLD}, Overbought > {RSI_OVERBOUGHT} "
        f"- Fear threshold: < {FEAR_GREED_EXTREME_FEAR} (extreme fear = buy opportunity) "
        f"- Greed threshold: > {FEAR_GREED_EXTREME_GREED} (extreme greed = sell opportunity) "
        "\n"
        "Provide contrarian analysis in JSON format: "
        "{"
        "  \"BTC\": {\"signal\": \"BUY\", \"confidence\": 0.8, \"reason\": \"Contrarian: Market panic + oversold RSI(25) + institutional fear creates opportunity\", \"stop_loss\": -0.20, \"take_profit\": 0.15, \"recommended_size\": 0.40}, "
        "  \"ETH\": {\"signal\": \"SELL\", \"confidence\": 0.75, \"reason\": \"Contrarian: Euphoric sentiment + overbought RSI(78) + FOMO peak suggests distribution\", \"stop_loss\": -0.15, \"take_profit\": 0.10, \"recommended_size\": 0.35}, "
        "  \"SOL\": {\"signal\": \"STRONG_BUY\", \"confidence\": 0.9, \"reason\": \"Contrarian: Extreme pessimism + oversold bounce setup + volume climax\", \"stop_loss\": -0.25, \"take_profit\": 0.20, \"recommended_size\": 0.50}, "
        "  \"XRP\": {\"signal\": \"HOLD\", \"confidence\": 0.5, \"reason\": \"Contrarian: Neutral sentiment, waiting for extreme conditions\", \"stop_loss\": -0.10, \"take_profit\": 0.10, \"recommended_size\": 0.20}"
        "}"
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(portfolio_summary)}
            ],
            response_format={"type": "json_object"},
            temperature=0.4,  # 약간 더 창의적
            max_tokens=1000
        )
        
        ai_signals = json.loads(response.choices[0].message.content)
        
        # AI 사용량 및 비용 계산
        tokens_used = response.usage.total_tokens
        cost_usd = (response.usage.prompt_tokens * 0.00015 + response.usage.completion_tokens * 0.0006) / 1000
        cost_krw = cost_usd * 1300
        
        print(f"🤖 컨트래리언 AI 분석 완료")
        print(f"  토큰: {tokens_used:,}개, 비용: ${cost_usd:.4f} (약 {cost_krw:.0f}원)")
        
        # 원본 신호를 컨트래리언 전략으로 변환
        inverted_signals = invert_ai_signals(ai_signals)
        
        return inverted_signals, {
            'tokens_used': tokens_used,
            'cost_usd': cost_usd,
            'cost_krw': cost_krw,
            'model': 'gpt-4o-mini'
        }
        
    except Exception as e:
        print(f"❌ 컨트래리언 AI 신호 생성 실패: {e}")
        return {}, {}

if __name__ == "__main__":
    print("🔄 컨트래리언 AI 트레이딩 봇 v1.0")
    print("=" * 50)
    print("전략: 역추세/반대매매/컨트래리언")
    print("특징: 공격적 포지션 사이징, 집중투자 허용")
    print("=" * 50)
    
    setup_contrarian_logging()
    
    # 환경변수 로드
    load_dotenv()
    
    # 업비트 객체 생성
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    
    if not access or not secret:
        print("❌ 업비트 API 키가 설정되지 않았습니다.")
        print("   .env 파일에 UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY를 설정하세요.")
        exit(1)
    
    upbit = pyupbit.Upbit(access, secret)
    
    print(f"✅ 컨트래리언 봇 초기화 완료")
    print(f"📊 포트폴리오: {', '.join([coin.split('-')[1] for coin in PORTFOLIO_COINS])}")
    print(f"🎯 컨트래리언 전략 활성화: {SIGNAL_INVERSION}")
    print(f"💰 기본 거래 비율: {BASE_TRADE_RATIO:.0%}")
    print(f"🔥 최대 집중도: {MAX_PORTFOLIO_CONCENTRATION:.0%}")
    print(f"⏰ 기본 체크 주기: {CHECK_INTERVALS['default_interval']}분")
    print(f"\n🚀 컨트래리언 봇 가동 시작!")
    
    # 여기에 실제 거래 루프 로직을 추가하면 됩니다
    # (mvp.py의 main 로직을 참조하여 구현)