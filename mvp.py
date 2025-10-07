"""
AI 포트폴리오 트레이딩 봇 v2.0
- 다중 타임프레임 분석
- 뉴스 감정 분석 통합
- 동적 리스크 관리
- 모듈화 구조
"""

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
import threading

# ============================================================================
# 모듈 임포트
# ============================================================================

# === 유틸리티 모듈 ===
from utils.api_helpers import get_safe_orderbook, get_total_portfolio_value
from utils.logger import log_decision

# === 데이터 수집 모듈 ===
from data.market_data import get_portfolio_data, calculate_rsi, get_fear_greed_index
from data.news_collector import get_news_headlines, get_free_crypto_news, analyze_news_sentiment

# === 분석 모듈 ===
from analysis.portfolio_analyzer import analyze_multi_timeframe, calculate_trend_alignment, make_portfolio_summary
from analysis.market_condition import analyze_market_condition, detect_bear_market
from trading.trendcoin_trader import execute_new_coin_trades

# ============================================================================
# 전역 변수 및 상태 관리
# ============================================================================

# === 거래 쿨다운 추적 ===
last_partial_sell_time = {}  # 부분매도 쿨다운
daily_sell_count = {}  # 일별 매도 횟수
last_reset_date = None  # 마지막 리셋 날짜

# === 신규/트렌드 코인 투자 관련 설정 ===
TREND_CHECK_INTERVAL_MIN = 20  # 신규코인만 20분마다 별도 모니터링
daily_sell_count = {}  # 일별 매도 횟수
last_reset_date = None  # 마지막 리셋 날짜
last_rebalance_time = {}  # 리밸런싱 쿨다운 (악순환 방지)

# ============================================================================
# 설정 로드
# ============================================================================


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

# 설정 로드 후 신규/트렌드 코인 투자 비율 할당
CONFIG = load_config()
TREND_INVEST_RATIO = CONFIG["coins"].get("trend_coin_ratio", 0.15)  # config에서 읽음

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
MAX_POSITION_MULTIPLIER = CONFIG["trading"]["max_position_multiplier"]
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
BEAR_MARKET_CASH_RATIO = CONFIG["safety"].get("bear_market_cash_ratio", 0.50)  # 약세장 현금 비율

# 리스크 관리 승수 (config에서 추출)
BULL_MARKET_MULTIPLIER = CONFIG["risk_management"]["bull_market_multiplier"]
BULL_OVERHEATED_MULTIPLIER = CONFIG["risk_management"]["bull_overheated_multiplier"]
BEAR_MARKET_MULTIPLIER = CONFIG["risk_management"]["bear_market_multiplier"]
BEAR_OVERSOLD_MULTIPLIER = CONFIG["risk_management"]["bear_oversold_multiplier"]
HIGH_VOLATILITY_MULTIPLIER = CONFIG["risk_management"]["high_volatility_multiplier"]

# 거래 제약 조건 (config에서 추출)
MAX_SINGLE_COIN_RATIO = CONFIG["trading_constraints"]["max_single_coin_ratio"]
AI_CONFIDENCE_MINIMUM = CONFIG["trading_constraints"]["ai_confidence_minimum"]
PRICE_CHANGE_THRESHOLD = CONFIG["trading_constraints"]["price_change_threshold"]
REBALANCING_DEVIATION_THRESHOLD = CONFIG["safety"]["rebalancing_deviation_threshold"]

# 체크 주기 설정
CHECK_INTERVALS = CONFIG["check_intervals"]
HIGH_VOLATILITY_THRESHOLD = CONFIG["market_conditions"]["high_volatility_threshold"]


# ============================================================================
# AI 신호 생성 함수
# ============================================================================

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
        f"📊 Technical Analysis - TREND FIRST STRATEGY: "
        f"- RSI < {RSI_OVERSOLD}: Strong oversold (BUY if no negative news) "
        f"- RSI 70~85 + strong_bullish_alignment: HOLD or BUY (trend > RSI indicator, ride the wave!) "
        f"- RSI > 85 + weak trend: SELL (extreme overbought, take profits) "
        f"- RSI > {RSI_OVERBOUGHT} + bearish trend: SELL (momentum reversal) "
        f"- Multi-timeframe alignment: Confirm day/4hr/1hr trend direction "
        f"- Volume validation: >150% average confirms breakouts/breakdowns "
        f"� Trend Priority Rules (CRITICAL): "
        f"- strong_bullish_alignment + RSI 70-85: Ignore RSI, recommend HOLD or BUY (강한 상승 추세는 RSI 무시) "
        f"- strong_bullish_alignment + price surge >5%: Consider BUY even at high RSI (추세 지속 포착) "
        f"- BTC/ETH major coins: Prefer HOLD during uptrends (주요 코인은 상승장에서 보유 우선) "
        f"- weak/mixed signals + RSI >70: SELL cautiously (약한 추세만 RSI 우선) "
        f"�📰 News Sentiment Integration: "
        f"- Positive regulatory/institutional news: Increase BUY confidence +0.2 "
        f"- Negative regulatory/security news: Increase SELL confidence +0.3 "
        f"- Major partnerships/upgrades: Boost STRONG_BUY signals "
        f"📈 Market Psychology: "
        f"- Fear & Greed < {FEAR_GREED_EXTREME_FEAR}: Contrarian opportunity (if no bad news) "
        f"- Fear & Greed > {FEAR_GREED_EXTREME_GREED}: Distribution zone (take profits only if trend weakens) "
        f"- High market correlation (>0.8): Reduce diversification assumptions "
        f"⚡ Enhanced Signals: "
        f"- EMERGENCY_SELL: Major hacks, severe regulatory crackdowns, 15%+ drops with bad news "
        f"- STRONG_BUY: ETF approvals + oversold + volume surge + positive news confluence "
        f"- BUY: Strong uptrend + RSI 70-85 + volume surge (상승 추세 지속) "
        f"- HOLD: Strong uptrend + RSI >70 but <85 (추세 지속 중 보유) "
        f"- Adapt to volatility: High vol = smaller positions but faster reactions "
        f"- If any coin allocation exceeds {MAX_SINGLE_COIN_RATIO:.0%}, recommend SELL or HOLD to rebalance portfolio "
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


# ============================================================================
# 리스크 관리 함수
# ============================================================================

def check_cash_shortage_rebalance(upbit, min_cash_ratio=None):
    """현금 부족 시 자동 리밸런싱 - 15% 미만 시 수익 코인 우선 매도"""
    if min_cash_ratio is None:
        min_cash_ratio = 0.15  # 최소 15% 현금 유지 (위험 구간)
    
    try:
        krw_balance = upbit.get_balance("KRW")
        total_portfolio_value = krw_balance
        coin_data = []
        
        # 전체 포트폴리오 가치 및 수익률 계산
        for ticker in PORTFOLIO_COINS:
            coin = ticker.split('-')[1]
            balance = upbit.get_balance(ticker)
            if balance > 0:
                # ✨ 헬퍼 함수 사용: 안전한 호가 조회
                orderbook = get_safe_orderbook(ticker)
                if not orderbook:
                    continue
                current_price = orderbook['orderbook_units'][0]['bid_price']
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
        
        if cash_ratio < min_cash_ratio:  # 현금이 15% 미만일 때 (위험 구간)
            target_cash_ratio = 0.20  # 20% 목표로 복구
            print(f"🚨 현금 위험 수준 감지! 현재 {cash_ratio:.1%} → 목표 {target_cash_ratio:.0%}")
            print("💸 긴급 리밸런싱 실행...")
            
            # 필요한 현금 금액 계산
            needed_cash = (total_portfolio_value * target_cash_ratio) - krw_balance
            
            # 수익 나는 코인부터 매도 (수익률 높은 순)
            profitable_coins = [c for c in coin_data if c['profit_percent'] > 2]  # 2% 이상 수익
            profitable_coins.sort(key=lambda x: x['profit_percent'], reverse=True)
            
            if profitable_coins:
                # 가장 수익률 높은 코인 매도
                target_coin = profitable_coins[0]
                sell_amount = min(needed_cash / target_coin['current_price'], target_coin['balance'] * 0.5)
                
                if sell_amount * target_coin['current_price'] >= MIN_TRADE_AMOUNT:
                    result = upbit.sell_market_order(target_coin['ticker'], sell_amount)
                    if result:
                        sell_value = sell_amount * target_coin['current_price']
                        print(f"  ✅ {target_coin['coin']} 수익실현 매도")
                        print(f"     수익률: {target_coin['profit_percent']:+.1f}% | 금액: {sell_value:,.0f}원")
                        print(f"     예상 현금 비중: {cash_ratio:.1%} → {target_cash_ratio:.0%}")
                        logging.info(f"CASH_REBALANCE - {target_coin['coin']}: {cash_ratio:.1%} → {target_cash_ratio:.0%} (수익실현: {sell_value:,.0f}원)")
                        return True
            else:
                # 수익 코인이 없으면 가장 비중 높은 코인 일부 매도
                coin_data.sort(key=lambda x: x['value'], reverse=True)
                if coin_data:
                    target_coin = coin_data[0]
                    sell_amount = min(needed_cash / target_coin['current_price'], target_coin['balance'] * 0.3)
                    
                    if sell_amount * target_coin['current_price'] >= MIN_TRADE_AMOUNT:
                        result = upbit.sell_market_order(target_coin['ticker'], sell_amount)
                        if result:
                            sell_value = sell_amount * target_coin['current_price']
                            print(f"  ⚠️ {target_coin['coin']} 현금확보 매도")
                            print(f"     수익률: {target_coin['profit_percent']:+.1f}% | 금액: {sell_value:,.0f}원")
                            print(f"     예상 현금 비중: {cash_ratio:.1%} → {target_cash_ratio:.0%}")
                            logging.info(f"CASH_REBALANCE - {target_coin['coin']}: {cash_ratio:.1%} → {target_cash_ratio:.0%} (현금확보: {sell_value:,.0f}원)")
                            return True
                    
        return False
        
    except Exception as e:
        print(f"❌ 현금 부족 체크 오류: {e}")
        return False

def check_portfolio_concentration_limits(upbit, max_single_position=None):
    """포트폴리오 집중도 제한 체크 - 35% 초과 시 자동 매도로 33% 수준 조정"""
    if max_single_position is None:
        max_single_position = MAX_SINGLE_COIN_RATIO  # 35% 사용
    
    global last_rebalance_time  # 쿨다운 시간 기록
    
    try:
        krw_balance = upbit.get_balance("KRW")
        total_portfolio_value = krw_balance
        coin_data = []
        
        # 포트폴리오 분석
        for ticker in PORTFOLIO_COINS:
            coin = ticker.split('-')[1]
            balance = upbit.get_balance(ticker)
            if balance > 0:
                # ✨ 헬퍼 함수 사용: 안전한 호가 조회
                orderbook = get_safe_orderbook(ticker)
                if not orderbook:
                    continue
                current_price = orderbook['orderbook_units'][0]['bid_price']
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
            
            # 35% 초과 시 33%로 조정
            if coin_ratio > max_single_position:
                target_ratio = 0.33  # 33% 목표 (안전 마진 2%)
                print(f"⚖️ {coin_info['coin']} 비중 초과 감지: {coin_ratio:.1%} → {target_ratio:.0%} 목표")
                
                # 초과분 계산 (현재 - 목표)
                excess_value = coin_info['value'] - (total_portfolio_value * target_ratio)
                sell_amount = excess_value / coin_info['current_price']
                
                # 최소 거래량 체크 (5,000원 이상)
                if excess_value >= MIN_TRADE_AMOUNT:
                    result = upbit.sell_market_order(coin_info['ticker'], sell_amount)
                    if result:
                        print(f"  ✅ {coin_info['coin']} 집중도 리밸런싱 완료")
                        print(f"     매도량: {sell_amount:.6f}개 | 금액: {excess_value:,.0f}원")
                        print(f"     예상 비중: {coin_ratio:.1%} → {target_ratio:.0%}")
                        logging.info(f"CONCENTRATION_REBALANCE - {coin_info['coin']}: {coin_ratio:.1%} → {target_ratio:.0%} (매도: {excess_value:,.0f}원)")
                        
                        # 🔴 리밸런싱 쿨다운 시간 기록 (악순환 방지)
                        last_rebalance_time[coin_info['coin']] = time.time()
                        print(f"  ⏰ {coin_info['coin']} 리밸런싱 쿨다운 시작 (2시간)")
                        
                        return True
                else:
                    print(f"  ⏸️ {coin_info['coin']} 초과분 {excess_value:,.0f}원 - 최소 거래금액 미만")
        
        return False
        
    except Exception as e:
        print(f"❌ 포트폴리오 집중도 체크 오류: {e}")
        logging.error(f"CONCENTRATION_CHECK_ERROR: {e}")
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
                # ✨ 헬퍼 함수 사용: 안전한 호가 조회
                orderbook = get_safe_orderbook(ticker)
                if not orderbook:
                    current_allocation[ticker] = 0
                    continue
                current_price = orderbook['orderbook_units'][0]['bid_price']
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

def calculate_dynamic_position_size(market_condition, base_ratio=BASE_TRADE_RATIO, upbit=None):
    """시장 상황에 따른 동적 포지션 사이징 - config.json 승수 사용"""
    condition = market_condition.get("condition", "sideways")
    confidence = market_condition.get("confidence", 0.5)
    avg_change = market_condition.get("avg_change", 0)
    fng_value = market_condition.get("fng_value", "50")
    
    # 시장 상황별 리스크 조정 - config.json의 risk_management 섹션 사용
    risk_multiplier = 1.0
    
    if condition == "bull_market":
        if abs(avg_change) > 15:  # 강한 상승 모멘텀
            risk_multiplier = BULL_MARKET_MULTIPLIER * 1.25  # 1.2 × 1.25 = 1.5
            print("🚀 강력한 상승세 감지 - 공격적 포지션 증가")
        else:
            risk_multiplier = BULL_MARKET_MULTIPLIER  # config: 1.2
    elif condition == "bull_market_overheated":
        risk_multiplier = BULL_OVERHEATED_MULTIPLIER  # config: 0.7
        print("🔥 과열 감지하지만 선별적 참여 유지")
    elif condition == "bear_market":
        risk_multiplier = BEAR_MARKET_MULTIPLIER  # config: 0.6
    elif condition == "bear_market_oversold":
        risk_multiplier = BEAR_OVERSOLD_MULTIPLIER  # config: 0.9
        print("💎 과매도 반등 기회 - 정상 포지션")
    elif condition == "high_volatility":
        # 방향성 있는 고변동성은 참여, 무방향은 보수적
        if abs(avg_change) > 10:
            risk_multiplier = HIGH_VOLATILITY_MULTIPLIER * 1.4  # 0.5 × 1.4 = 0.7
            print("⚡ 방향성 있는 고변동성 - 제한적 참여")
        else:
            risk_multiplier = HIGH_VOLATILITY_MULTIPLIER  # config: 0.5
    elif condition == "sideways":
        # 🔴 현금 비중 과다 시 강제 매수 활성화
        current_krw = upbit.get_balance("KRW") if upbit else 0
        total_value = current_krw
        
        # 총 자산 계산
        if upbit:
            for coin in [c.split('-')[1] for c in PORTFOLIO_COINS]:
                ticker = f"KRW-{coin}"
                balance = upbit.get_balance(ticker)
                if balance > 0:
                    try:
                        current_price = pyupbit.get_current_price(ticker)
                        if current_price:
                            total_value += balance * current_price
                    except:
                        pass
        
        cash_ratio = current_krw / total_value if total_value > 0 else 0
        
        # 횡보장 + 탐욕 구간 = 추가 감소
        try:
            fng_int = int(fng_value)
            if cash_ratio > 0.40:
                # 🔴 현금 40% 초과 시 강제 매수 (횡보 페널티 무시)
                risk_multiplier = 1.0
                print(f"💰 현금 비중 과다 ({cash_ratio*100:.1f}%) - 강제 매수 활성화 (횡보 페널티 무시)")
            elif fng_int > 70:
                risk_multiplier = 0.85  # 15% 감소 (기존 0.75에서 완화)
                print(f"⏸️ 횡보장 + 탐욕 구간 - 거래 보수적 (0.85배) | 현금: {cash_ratio*100:.1f}%")
            else:
                risk_multiplier = 0.9  # 10% 감소
        except:
            risk_multiplier = 0.9
    
    # 신뢰도에 따른 추가 조정 - 범위 확대
    confidence_multiplier = 0.6 + (confidence * 0.6)  # 0.6~1.2
    
    adjusted_ratio = base_ratio * risk_multiplier * confidence_multiplier
    return min(adjusted_ratio, base_ratio * MAX_POSITION_MULTIPLIER)  # config: 1.5배 상한


# ============================================================================
# 성과 분석 함수
# ============================================================================

def calculate_performance_metrics(upbit, portfolio_summary):
    """포트폴리오 성과 지표 계산 (현금 포함 총자산 기준)"""
    try:
        # 현재 보유 자산 조회
        krw_balance = upbit.get_balance("KRW")
        total_value = krw_balance  # 현금부터 시작
        coin_values = {}
        
        for coin in [c.split('-')[1] for c in PORTFOLIO_COINS]:
            ticker = f"KRW-{coin}"
            balance = upbit.get_balance(ticker)
            
            if balance > 0:
                current_price = portfolio_summary.get("coins", {}).get(coin, {}).get("current_price", 0)
                coin_value = balance * current_price
                total_value += coin_value  # 총자산에 코인 가치 추가
                coin_values[coin] = {
                    "balance": balance,
                    "value": coin_value,
                    "percentage": 0  # 나중에 계산
                }
        
        # 비중 계산 (전체 자산 = 현금 + 코인)
        for coin in coin_values:
            coin_values[coin]["percentage"] = coin_values[coin]["value"] / total_value * 100
        
        return {
            "total_value": total_value,  # 현금 + 코인 합계
            "krw_balance": krw_balance,
            "coin_values": coin_values,
            "krw_percentage": krw_balance / total_value * 100 if total_value > 0 else 0
        }
        
    except Exception as e:
        logging.error(f"성과 계산 오류: {e}")
        return None

def print_performance_summary(performance):
    """성과 요약 출력 (현금 포함 전체 자산 기준)"""
    if not performance:
        print("❌ 성과 데이터를 불러올 수 없습니다.")
        return
    
    print(f"\n💼 포트폴리오 현황:")
    print(f"총 자산: {performance['total_value']:,.0f}원 (현금 + 코인)")
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


# ============================================================================
# 거래 실행 함수
# ============================================================================

def execute_portfolio_trades(ai_signals, upbit, portfolio_summary, cycle_count=0, base_trade_ratio=BASE_TRADE_RATIO):
    """포트폴리오 기반 스마트 매매 실행 - 시장 상황 고려 + 안전장치"""
    print(f"\n💰 포트폴리오 매매 실행 시작 (기본 비율: {base_trade_ratio:.1%})")
    
    # 거래 실행 이력 저장용
    executed_trades = []
    
    # 🔴 약세장 감지 및 현금 방어 모드 (최우선 체크)
    print("🐻 약세장 감지 중...")
    bear_market_check = detect_bear_market(portfolio_summary)
    
    if bear_market_check['is_bear_market']:
        print(f"🚨 약세장 감지! (신뢰도: {bear_market_check['confidence']:.1%})")
        print(f"   근거: {bear_market_check.get('reason', '복합 약세 신호')}")
        print(f"   지표: {bear_market_check['indicators']}")
        print(f"   🛡️ 현금 방어 모드 활성화")
        
        # 현금 비중 50% 이상으로 강제 조정
        current_krw = upbit.get_balance("KRW")
        total_value = get_total_portfolio_value(upbit)
        cash_ratio = current_krw / total_value if total_value > 0 else 0
        
        if cash_ratio < BEAR_MARKET_CASH_RATIO:
            needed_cash = (total_value * BEAR_MARKET_CASH_RATIO) - current_krw
            print(f"   💸 현금 비중 부족: {cash_ratio:.1%} → {BEAR_MARKET_CASH_RATIO:.0%} 목표")
            print(f"   필요 현금: {needed_cash:,.0f}원")
            
            # 수익 나는 코인 우선 매도
            profitable_coins = []
            for ticker in PORTFOLIO_COINS:
                coin = ticker.split('-')[1]
                balance = upbit.get_balance(ticker)
                if balance > 0:
                    try:
                        avg_buy_price = upbit.get_avg_buy_price(ticker)
                        orderbook = get_safe_orderbook(ticker)
                        if not orderbook:
                            continue
                        current_price = orderbook['orderbook_units'][0]['bid_price']
                        
                        if avg_buy_price and avg_buy_price > 0:
                            profit_rate = (current_price - avg_buy_price) / avg_buy_price
                            if profit_rate > -0.05:  # -5% 이상 (손실 적거나 수익)
                                coin_value = balance * current_price
                                profitable_coins.append({
                                    'ticker': ticker,
                                    'coin': coin,
                                    'profit_rate': profit_rate,
                                    'balance': balance,
                                    'price': current_price,
                                    'value': coin_value
                                })
                    except Exception as e:
                        logging.debug(f"방어 매도 정보 조회 실패 ({coin}): {e}")
                        continue
            
            if profitable_coins:
                # 수익률 높은 순 정렬
                profitable_coins.sort(key=lambda x: x['profit_rate'], reverse=True)
                
                # 상위 코인부터 매도하여 현금 확보
                cash_secured = 0
                for coin_info in profitable_coins:
                    if current_krw + cash_secured >= total_value * BEAR_MARKET_CASH_RATIO:
                        break
                    
                    # 50%만 매도 (전량 아님 - 반등 대비)
                    sell_ratio = 0.5
                    sell_amount = coin_info['balance'] * sell_ratio
                    sell_value = sell_amount * coin_info['price']
                    
                    if sell_value >= MIN_TRADE_AMOUNT:
                        try:
                            result = upbit.sell_market_order(coin_info['ticker'], sell_amount)
                            if result:
                                cash_secured += sell_value * 0.9995  # 수수료 고려
                                print(f"   ✅ {coin_info['coin']} 방어 매도: {sell_value:,.0f}원 (수익률: {coin_info['profit_rate']:+.1%})")
                                logging.info(f"BEAR_DEFENSE_SELL - {coin_info['coin']}: {sell_value:,.0f}원, 수익률 {coin_info['profit_rate']:+.1%}")
                        except Exception as e:
                            print(f"   ❌ {coin_info['coin']} 방어 매도 실패: {e}")
                            logging.error(f"BEAR_DEFENSE_SELL_ERROR - {coin_info['coin']}: {e}")
                
                final_cash_ratio = (current_krw + cash_secured) / total_value if total_value > 0 else 0
                print(f"   ✅ 방어 매도 완료: 현금 {cash_ratio:.1%} → {final_cash_ratio:.1%}")
            else:
                print(f"   ⚠️ 매도 가능한 코인 없음 (모두 손실 중)")
        
        # 약세장에서는 신규 매수 중단
        print(f"   ⛔ 약세장으로 신규 매수 중단 (현금 보존 모드)")
        print(f"   💡 현금 {cash_ratio:.1%} 보유 - 반등 대기")
        return  # 매매 실행하지 않고 종료
    
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
        portfolio_rebalance_executed = check_portfolio_rebalancing(upbit, deviation_threshold=REBALANCING_DEVIATION_THRESHOLD)
    
    if stop_loss_executed or cash_rebalance_executed or concentration_rebalance_executed or portfolio_rebalance_executed:
        print("⚠️ 안전장치 실행으로 인해 이번 사이클 신규 매매를 건너뜁니다.")
        return
    
    # 2. 시장 상황 분석
    market_condition = portfolio_summary.get("market_condition", {})
    dynamic_ratio = calculate_dynamic_position_size(market_condition, base_trade_ratio, upbit=upbit)
    
    print(f"📊 시장 상황: {market_condition.get('condition', 'unknown')}")
    print(f"🎯 조정된 거래 비율: {dynamic_ratio:.1%} (기본: {base_trade_ratio:.1%})")
    
    # 현재 보유 현금 확인
    available_krw = upbit.get_balance("KRW")
    print(f"사용 가능 현금: {available_krw:,.0f}원")
    
    # 최근 신호 이력 저장용 (최대 5회)
    if not hasattr(execute_portfolio_trades, "recent_signals"):
        execute_portfolio_trades.recent_signals = {}
    recent_signals = execute_portfolio_trades.recent_signals

    # 각 코인별 매매 실행
    for coin, signal_data in ai_signals.items():
        signal = signal_data.get('signal', 'HOLD')
        confidence = signal_data.get('confidence', 0.5)
        reason = signal_data.get('reason', 'No reason provided')
        ticker = f"KRW-{coin}"
        print(f"\n🪙 {coin} 분석:")
        print(f"  신호: {signal} | 신뢰도: {confidence:.1%}")
        print(f"  근거: {reason}")

        # 최근 신호 이력 관리
        if coin not in recent_signals:
            recent_signals[coin] = []
        recent_signals[coin].append(signal)
        if len(recent_signals[coin]) > 5:
            recent_signals[coin] = recent_signals[coin][-5:]

        try:
            # ✨ 헬퍼 함수 사용: 총 자산 계산
            current_total_value = get_total_portfolio_value(upbit)
            current_coin_balance = upbit.get_balance(ticker)
            
            # ✨ 헬퍼 함수 사용: 안전한 호가 조회
            orderbook = get_safe_orderbook(ticker)
            if not orderbook:
                logging.warning(f"{coin} 호가 정보 조회 실패 - 건너뜀")
                print(f"  ⚠️ {coin} 호가 정보 없음")
                continue
            
            current_price = orderbook['orderbook_units'][0]['ask_price']
            current_coin_value = current_coin_balance * current_price if current_coin_balance > 0 else 0
            
            current_coin_ratio = current_coin_value / current_total_value if current_total_value > 0 else 0
            max_concentration = MAX_SINGLE_COIN_RATIO  # config.json의 trading_constraints 사용

            # 과매매 방지: AI 호출/거래 횟수 많으면 체크 주기 자동 연장
            if cycle_count > 0 and cycle_count % 100 == 0:
                print("⏰ 과매매 방지: 체크 주기 자동 연장 (AI 호출/거래 많음)")
                CHECK_INTERVALS["default_interval"] = min(CHECK_INTERVALS["default_interval"] + 15, 120)

            # 연속 매수/매도 제한
            if signal in ['STRONG_BUY', 'BUY']:
                # 집중도 초과 시 분산 매수 시도 (AI 신호 확인)
                if current_coin_ratio >= max_concentration:
                    print(f"  ⚠️ {coin} 집중도 초과({current_coin_ratio:.1%} >= {max_concentration:.1%}) - 매수 제한, 분산 매수 시도")
                    
                    # BUY/HOLD 신호이고 집중도 낮은 코인 찾기
                    low_conc_coins = []
                    for other in PORTFOLIO_COINS:
                        if other == ticker:
                            continue
                        
                        # AI 신호 확인 (중요!)
                        other_coin_name = other.replace("KRW-", "")
                        other_signal_data = ai_signals.get(other_coin_name, {})
                        other_signal = other_signal_data.get('signal', 'HOLD')
                        other_confidence = other_signal_data.get('confidence', 0)
                        
                        # SELL 신호이거나 신뢰도 낮으면 분산 매수 제외
                        if other_signal in ['SELL', 'STRONG_SELL']:
                            logging.info(f"분산매수 제외 - {other_coin_name}: {other_signal} 신호 (신뢰도: {other_confidence:.1%})")
                            print(f"     ❌ {other_coin_name}: {other_signal} 신호로 제외")
                            continue
                        
                        # 신뢰도 기준 상향: 60% 미만 제외
                        if other_confidence < 0.6:
                            logging.info(f"분산매수 제외 - {other_coin_name}: 신뢰도 낮음 ({other_confidence:.1%})")
                            print(f"     ❌ {other_coin_name}: 신뢰도 {other_confidence:.1%} 낮아 제외 (60% 미만)")
                            continue
                        
                        # 집중도 및 호가 확인
                        try:
                            other_balance = upbit.get_balance(other)
                            # ✨ 헬퍼 함수 사용: 안전한 호가 조회
                            other_orderbook = get_safe_orderbook(other)
                            if not other_orderbook:
                                logging.debug(f"{other} 호가 정보 없음 (분산매수 제외)")
                                continue
                            other_price = other_orderbook['orderbook_units'][0]['ask_price']
                            other_value = other_balance * other_price if other_balance > 0 else 0
                            other_ratio = other_value / current_total_value if current_total_value > 0 else 0
                            
                            if other_ratio < max_concentration:
                                low_conc_coins.append((other, other_ratio, other_signal, other_confidence))
                                print(f"     ✅ {other_coin_name}: {other_signal} {other_confidence:.0%} | 비중 {other_ratio:.1%}")
                        except Exception as e:
                            logging.debug(f"{other} 분산매수 집중도 조회 실패 (무시): {e}")
                            continue
                    
                    if low_conc_coins:
                        # 집중도 가장 낮은 코인에 분산 매수 실행
                        target_ticker, target_ratio, target_signal, target_confidence = min(low_conc_coins, key=lambda x: x[1])
                        target_coin_name = target_ticker.replace("KRW-", "")
                        print(f"  ➡️ {target_coin_name} 분산 매수 실행 (신호: {target_signal} {target_confidence:.0%}, 비중: {target_ratio:.1%})")
                        
                        # 분산 매수 금액 계산 (원래 매수하려던 금액의 50%)
                        current_krw = upbit.get_balance("KRW")
                        diversify_amount = current_krw * dynamic_ratio * 0.5 * 0.9995
                        
                        if diversify_amount >= MIN_TRADE_AMOUNT and current_krw >= MIN_TRADE_AMOUNT * 2:
                            try:
                                result = upbit.buy_market_order(target_ticker, diversify_amount)
                                if result:
                                    print(f"  ✅ {target_coin_name} 분산 매수 완료: {diversify_amount:,.0f}원")
                                    logging.info(f"DIVERSIFY_BUY - {target_coin_name}: {diversify_amount:,.0f}원 (신호: {target_signal} {target_confidence:.0%}, 원래: {coin} 집중도 초과)")
                                    executed_trades.append({'coin': target_coin_name, 'action': 'DIVERSIFY_BUY', 'amount': diversify_amount})
                                else:
                                    print(f"  ❌ {target_coin_name} 분산 매수 실패")
                            except Exception as e:
                                print(f"  ❌ {target_coin_name} 분산 매수 오류: {e}")
                                logging.error(f"DIVERSIFY_BUY_ERROR - {target_coin_name}: {e}")
                        else:
                            print(f"  ⏸️ 분산 매수 금액 부족 ({diversify_amount:,.0f}원)")
                        continue
                    else:
                        # BUY/HOLD 신호 코인이 없거나 모두 집중도 높음 → 현금 유지
                        print(f"  ⚠️ 분산 매수 가능한 코인 없음 (BUY/HOLD 신호 없음 또는 집중도 초과)")
                        print(f"  💰 현금 유지 - 다음 기회 대기")
                        logging.info(f"BUY_SKIP - {coin}: 집중도 초과, 분산 매수 불가 (현금 유지)")
                        continue
                
                # ✨ 헬퍼 함수 사용: 총 자산 계산 (연속 매수 제한 체크용)
                total_value = get_total_portfolio_value(upbit)
                current_krw = upbit.get_balance("KRW")
                
                # 🔴 비중 기반 매수 제한 (악순환 방지)
                current_allocation = portfolio_summary.get('portfolio_allocation', {}).get(coin, 0)
                if current_allocation > MAX_SINGLE_COIN_RATIO * 0.8:  # 35%의 80% = 28%
                    log_decision('BUY', coin, False, '비중 초과 (리밸런싱 악순환 방지)', {
                        'current_allocation': f"{current_allocation:.1%}",
                        'threshold': '28%',
                        'confidence': f"{confidence:.1%}",
                        'signal': signal
                    })
                    continue
                
                # 🔴 리밸런싱 직후 쿨다운 체크 (2시간)
                global last_rebalance_time
                if coin in last_rebalance_time:
                    time_since_rebalance = time.time() - last_rebalance_time[coin]
                    if time_since_rebalance < 2 * 60 * 60:  # 2시간
                        hours_remaining = (2 * 60 * 60 - time_since_rebalance) / 3600
                        log_decision('BUY', coin, False, '리밸런싱 쿨다운', {
                            'time_since_rebalance': f"{time_since_rebalance/3600:.1f}시간",
                            'cooldown_remaining': f"{hours_remaining:.1f}시간",
                            'confidence': f"{confidence:.1%}",
                            'signal': signal
                        })
                        continue
                
                # 연속 매수 제한: 최근 5회 중 3회 이상 매수면 건너뜀
                # 🔴 강제 매수 모드에서는 완화 (3회 → 6회)
                cash_ratio = current_krw / total_value if total_value > 0 else 0
                consecutive_buy_limit = 6 if cash_ratio > 0.40 else 3
                buy_count = recent_signals[coin].count('BUY') + recent_signals[coin].count('STRONG_BUY')
                if buy_count >= consecutive_buy_limit:
                    log_decision('BUY', coin, False, f'연속 매수 제한 ({buy_count}/{consecutive_buy_limit})', {
                        'recent_signals': recent_signals[coin],
                        'cash_ratio': f"{cash_ratio:.1%}",
                        'force_buy_mode': cash_ratio > 0.40,
                        'confidence': f"{confidence:.1%}",
                        'signal': signal
                    })
                    continue
                
                # AI 신뢰도 최소 기준 체크 (config.json 사용)
                if confidence < AI_CONFIDENCE_MINIMUM:
                    print(f"  ⚠️ 신뢰도 너무 낮음 ({confidence:.1%} < {AI_CONFIDENCE_MINIMUM:.1%}) - 매수 건너뜀")
                    continue
                
                # 신뢰도별 배수 적용
                if confidence >= 0.8:
                    multiplier = 1.5
                elif confidence >= 0.7:
                    multiplier = 1.0
                else:  # 0.78 ~ 0.7
                    multiplier = 0.5
                
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
                
                # 현금 비중 30% 미만 시 매수 중단
                current_portfolio_value = current_krw
                for temp_ticker in PORTFOLIO_COINS:
                    try:
                        temp_balance = upbit.get_balance(temp_ticker)
                        if temp_balance > 0:
                            temp_orderbook = pyupbit.get_orderbook(ticker=temp_ticker)
                            if temp_orderbook and 'orderbook_units' in temp_orderbook and temp_orderbook['orderbook_units']:
                                temp_price = temp_orderbook['orderbook_units'][0]['ask_price']
                                current_portfolio_value += temp_balance * temp_price
                    except:
                        continue
                
                cash_ratio = current_krw / current_portfolio_value if current_portfolio_value > 0 else 0
                
                # 매수 가능 여부를 현금 비중이 아닌 절대 금액으로 판단
                # 현금 20% 권장이지만, 충분한 금액 있으면 매수 허용
                min_required_cash = MIN_TRADE_AMOUNT * 3  # 최소 거래금액의 3배 (15,000원)
                
                if current_krw < min_required_cash:
                    print(f"  🚨 현금 절대 부족 ({current_krw:,.0f}원 < {min_required_cash:,.0f}원) - 매수 중단")
                    print(f"     💡 현재 현금 비중: {cash_ratio:.1%} (권장: 20% 이상)")
                    logging.info(f"BUY_SKIP - {coin}: 현금 절대 부족 ({current_krw:,.0f}원)")
                    continue
                
                # 현금 비중 15% 미만일 때만 경고 (차단하지 않음)
                if cash_ratio < 0.15:
                    print(f"  ⚠️ 주의: 현금 비중 낮음 ({cash_ratio:.1%}) - 다음 사이클 리밸런싱 예정")
                elif cash_ratio < 0.20:
                    print(f"  📊 현금 비중: {cash_ratio:.1%} (권장: 20% 이상)")
                
                # 현금 부족 시 매수 제한
                if current_krw < MIN_TRADE_AMOUNT * 2:  # 최소 거래금액의 2배 미만 시
                    print(f"  ⚠️ 현금 부족으로 매수 제한: {current_krw:,.0f}원")
                    continue
                
                # 매수 실행 (동적 포지션 사이징 + AI 추천 사이즈 적용)
                ai_size_ratio = signal_data.get('recommended_size', dynamic_ratio)
                # AI 추천 사이즈와 동적 사이징 중 더 보수적인 값 선택
                final_ratio = min(ai_size_ratio, dynamic_ratio * multiplier)
                trade_amount = current_krw * final_ratio * 0.9995  # 수수료 고려
                
                # 최대 투자 한도 체크 (총 자산의 85%까지만) - 예외 처리 강화
                try:
                    total_portfolio = get_current_portfolio_snapshot(upbit)
                    total_value = total_portfolio.get('total_value', 0)
                except Exception as e:
                    logging.warning(f"포트폴리오 스냅샷 조회 실패 (간단 추정 사용): {e}")
                    # 현금 기반 간단 추정: 현금 / 최소현금비율 = 전체 포트폴리오 추정
                    total_value = current_krw / MIN_CASH_RATIO if current_krw > 0 else current_total_value
                
                # 🔴 매수 전 예상 비중 체크 (초과 방지)
                expected_coin_value = current_coin_value + trade_amount
                expected_coin_ratio = expected_coin_value / total_value if total_value > 0 else 0
                
                if expected_coin_ratio > MAX_SINGLE_COIN_RATIO:
                    # 비중 초과 시 매수 금액 조정 (목표 비중까지만)
                    max_allowed_value = total_value * MAX_SINGLE_COIN_RATIO
                    adjusted_trade_amount = max(0, max_allowed_value - current_coin_value) * 0.9995
                    
                    if adjusted_trade_amount >= MIN_TRADE_AMOUNT:
                        trade_amount = adjusted_trade_amount
                        print(f"  ⚠️ 비중 초과 방지: 매수 금액 조정")
                        print(f"     원래: {current_krw * final_ratio:,.0f}원 → 조정: {trade_amount:,.0f}원")
                        print(f"     예상 비중: {expected_coin_ratio:.1%} → {MAX_SINGLE_COIN_RATIO:.1%}")
                        logging.info(f"BUY_ADJUSTED - {coin}: 비중 초과 방지 ({expected_coin_ratio:.1%} → {MAX_SINGLE_COIN_RATIO:.1%}), {trade_amount:,.0f}원")
                    else:
                        print(f"  ❌ 비중 초과로 매수 불가 (현재: {current_coin_ratio:.1%}, 예상: {expected_coin_ratio:.1%})")
                        logging.info(f"BUY_SKIP - {coin}: 비중 초과 ({current_coin_ratio:.1%} → {expected_coin_ratio:.1%} > {MAX_SINGLE_COIN_RATIO:.1%})")
                        continue
                
                krw_ratio = current_krw / total_value if total_value > 0 else 1
                cash_ratio_for_check = current_krw / total_value if total_value > 0 else 0
                
                # 🔴 강제 매수 모드에서는 현금 비율 체크 건너뛰기
                if cash_ratio_for_check <= 0.40 and krw_ratio < MIN_CASH_RATIO:  # 강제 매수 아닐 때만 체크
                    print(f"  ⚠️ 현금 비율 부족으로 매수 제한: {krw_ratio:.1%}")
                    continue
                
                # 안전한 매수 가격 조회 (재시도 로직 추가)
                buy_orderbook = None
                for retry in range(3):
                    try:
                        buy_orderbook = pyupbit.get_orderbook(ticker=ticker)
                        if buy_orderbook and isinstance(buy_orderbook, dict) and 'orderbook_units' in buy_orderbook and buy_orderbook['orderbook_units']:
                            break
                    except (KeyError, TypeError, Exception) as e:
                        print(f"  ⚠️ {coin} 호가 조회 실패 (시도 {retry+1}/3): {e}")
                        time.sleep(1)
                
                if not buy_orderbook or not isinstance(buy_orderbook, dict) or 'orderbook_units' not in buy_orderbook or not buy_orderbook['orderbook_units']:
                    print(f"  ⚠️ {coin} 호가 정보 없음 - 매수 건너뜀")
                    logging.warning(f"BUY_SKIP - {coin}: 호가 정보 없음")
                    continue
                    
                current_price = buy_orderbook['orderbook_units'][0]['ask_price']
                
                if trade_amount > MIN_TRADE_AMOUNT:  # 최소 거래 금액
                    result = upbit.buy_market_order(ticker, trade_amount)
                    if result:
                        log_decision('BUY', coin, True, '매수 완료', {
                            'trade_amount': f"{trade_amount:,.0f}원",
                            'ai_size_ratio': f"{ai_size_ratio:.1%}",
                            'confidence': f"{confidence:.1%}",
                            'signal': signal,
                            'current_allocation': f"{current_allocation:.1%}",
                            'cash_ratio': f"{cash_ratio:.1%}"
                        })
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
                # 🔴 매일 자정에 SELL 카운트 리셋
                global last_reset_date, daily_sell_count
                today = datetime.now().date()
                if last_reset_date != today:
                    daily_sell_count = {}
                    last_reset_date = today
                
                # 🔴 같은 코인 하루 1회 SELL 제한 (손절매/고신뢰도 예외)
                if daily_sell_count.get(coin, 0) >= 1:
                    # 현재 손실률 계산
                    try:
                        avg_buy_price = upbit.get_avg_buy_price(ticker)
                        current_price_data = pyupbit.get_orderbook(ticker=ticker)
                        if current_price_data and 'orderbook_units' in current_price_data and current_price_data['orderbook_units']:
                            current_price = current_price_data['orderbook_units'][0]['bid_price']
                            loss_rate = ((avg_buy_price - current_price) / avg_buy_price) if avg_buy_price > 0 else 0
                        else:
                            loss_rate = 0
                    except Exception as e:
                        logging.warning(f"손실률 계산 실패: {e}")
                        loss_rate = 0
                    
                    is_stop_loss = loss_rate >= 0.15  # -15% 이상 손실
                    is_high_confidence = confidence >= 0.8  # 80% 이상 고신뢰도
                    
                    if is_stop_loss:
                        log_decision('SELL', coin, True, '손절매 예외 (일별 제한 무시)', {
                            'loss_rate': f"{loss_rate*100:.1f}%",
                            'daily_sell_count': daily_sell_count[coin],
                            'avg_buy_price': avg_buy_price,
                            'current_price': current_price,
                            'confidence': f"{confidence:.1%}",
                            'signal': signal
                        })
                    elif is_high_confidence:
                        log_decision('SELL', coin, True, '고신뢰도 예외 (일별 제한 무시)', {
                            'confidence': f"{confidence:.1%}",
                            'daily_sell_count': daily_sell_count[coin],
                            'signal': signal
                        })
                    else:
                        log_decision('SELL', coin, False, '일별 매도 제한', {
                            'daily_sell_count': f"{daily_sell_count[coin]}/1",
                            'confidence': f"{confidence:.1%}",
                            'loss_rate': f"{loss_rate*100:.1f}%",
                            'signal': signal
                        })
                        continue
                
                # 🔴 보유 중인 코인만 매도 제한 체크 (보유하지 않은 코인은 SELL 신호를 받아도 거래 안 되므로 제한 불필요)
                current_coin_balance = upbit.get_balance(ticker)
                if current_coin_balance > 0:
                    # 연속 매도 제한: 최근 5회 중 4회 이상 매도면 건너뜀
                    if recent_signals[coin].count('SELL') >= 4:
                        log_decision('SELL', coin, False, '연속 매도 제한 (최근 5회 중 4회 이상)', {
                            'recent_signals': recent_signals[coin],
                            'current_balance': f"{current_coin_balance:.8f}",
                            'confidence': f"{confidence:.1%}",
                            'signal': signal
                        })
                        continue
                else:
                    # 보유하지 않은 코인 - SELL 신호 무시
                    log_decision('SELL', coin, False, '보유량 없음 (매도 불가)', {
                        'current_balance': '0',
                        'confidence': f"{confidence:.1%}",
                        'signal': signal
                    })
                    continue
                
                # �️ 보수적 강화: RSI 구간별 차등 적용 + 거래량 검증
                market_data = portfolio_summary.get('coins', {}).get(coin, {})
                rsi = market_data.get('rsi', 50)
                trend = market_data.get('trend_alignment', '')
                change_rate = market_data.get('change_rate', 0)
                volume = market_data.get('volume', 0)
                
                # 거래량 비율 계산
                volume_avg = market_data.get('multi_timeframe', {}).get('day', {}).get('volume_avg', volume)
                volume_ratio = volume / volume_avg if volume_avg > 0 else 1.0
                
                # RSI 낮고 추세 강하면 매도 제한 (기존 로직 - 가장 먼저 체크)
                if rsi < 40 and 'bull' in trend:
                    print(f"  ⏸️ {coin} RSI {rsi:.1f} 낮고 추세 강함 - 매도 제한")
                    continue
                
                # 🔒 RSI 구간별 차등 적용
                sell_executed = False
                
                # 1️⃣ RSI 70-75: 추세 OR (거래량 + 상승률) 확인 (완화된 조건)
                if 70 < rsi <= 75:
                    # 강한 추세만 있어도 매도 제한 OR 거래량+상승률 조건 만족
                    strong_trend = 'strong_bullish' in trend
                    volume_condition = volume_ratio > 1.5 and change_rate > 5
                    
                    if strong_trend or volume_condition:
                        reason = []
                        if strong_trend:
                            reason.append(f"강한 추세({trend})")
                        if volume_condition:
                            reason.append(f"거래량 {volume_ratio:.1f}배 + 상승률 +{change_rate:.1f}%")
                        print(f"  🟢 {coin} RSI {rsi:.1f} 과열이지만 매도 제한")
                        print(f"     이유: {' + '.join(reason)}")
                        continue
                    else:
                        print(f"  🟡 {coin} RSI {rsi:.1f} 과열 - 조건 미달 (추세: {trend}, 거래량: {volume_ratio:.1f}배, 상승률: +{change_rate:.1f}%), 매도 진행")
                        # 정상 매도 진행 (아래 매도 로직으로)
                
                # 2️⃣ RSI 75-80: 추세 OR 높은 상승률 확인 (완화)
                elif 75 < rsi <= 80:
                    # 강한 추세 OR 높은 상승률 중 하나만 만족하면 대기
                    if 'strong_bullish' in trend or change_rate > 7:
                        reason = "강한 추세" if 'strong_bullish' in trend else f"높은 상승률 +{change_rate:.1f}%"
                        print(f"  🟠 {coin} RSI {rsi:.1f} 높음 - {reason}로 신중 대기")
                        print(f"     (추세: {trend}, 상승률: +{change_rate:.1f}%, 거래량: {volume_ratio:.1f}배)")
                        continue
                    elif volume_ratio < 1.0:
                        print(f"  🔴 {coin} RSI {rsi:.1f} + 거래량 감소({volume_ratio:.1f}배) - 즉시 매도 (가짜 돌파 가능성)")
                        # 정상 매도 진행
                    else:
                        print(f"  🟡 {coin} RSI {rsi:.1f} 높음 - 조건 미달 (추세: {trend}, 상승률: +{change_rate:.1f}%), 매도 진행")
                        # 정상 매도 진행
                
                # 3️⃣ RSI 80-85: 극도 주의 - 부분 매도 (3단계 세분화)
                elif 80 < rsi < 85:
                    # 80-82: 30% 매도 (가장 보수적)
                    if rsi <= 82:
                        if 'strong_bullish' in trend and change_rate > 8:
                            print(f"  ⚠️ {coin} RSI {rsi:.1f} 과열 초기 - 강한 추세로 30% 부분 매도")
                            print(f"     (추세: {trend}, 상승률: +{change_rate:.1f}%, 거래량: {volume_ratio:.1f}배)")
                            sell_ratio = 0.3
                        else:
                            print(f"  🚨 {coin} RSI {rsi:.1f} 과열 초기 - 50% 매도")
                            print(f"     (추세: {trend}, 상승률: +{change_rate:.1f}%)")
                            sell_ratio = 0.5
                    # 82-84: 50% 매도
                    elif rsi <= 84:
                        if 'strong_bullish' in trend and change_rate > 10 and volume_ratio > 2.0:
                            print(f"  ⚠️ {coin} 극단적 상승 - RSI {rsi:.1f}, 50% 부분 매도")
                            print(f"     (거래량 {volume_ratio:.1f}배, 상승률 +{change_rate:.1f}%)")
                            sell_ratio = 0.5
                        else:
                            print(f"  🚨 {coin} RSI {rsi:.1f} 위험 - 70% 매도")
                            sell_ratio = 0.7
                    # 84-85: 80% 매도 (거의 전량)
                    else:
                        print(f"  🔥 {coin} RSI {rsi:.1f} 극도 위험 - 80% 매도")
                        sell_ratio = 0.8
                    sell_executed = True  # 부분 매도 실행 플래그
                
                # 4️⃣ RSI 85+: 무조건 전량 매도 (기존 안전장치)
                elif rsi >= 85:
                    print(f"  🔥 {coin} RSI {rsi:.1f} 극도 과열 - 무조건 전량 매도")
                    sell_ratio = 1.0  # 전량 매도
                    sell_executed = True
                
                # 부분 매도 실행 (RSI 80+ 구간) - 상세 로깅 추가
                if sell_executed:
                    # 🔴 부분매도 쿨다운 체크 (6시간)
                    PARTIAL_SELL_COOLDOWN = 6 * 60 * 60  # 6시간
                    current_time = time.time()
                    
                    if coin in last_partial_sell_time:
                        time_since_last = current_time - last_partial_sell_time[coin]
                        if time_since_last < PARTIAL_SELL_COOLDOWN:
                            hours_remaining = (PARTIAL_SELL_COOLDOWN - time_since_last) / 3600
                            log_decision('PARTIAL_SELL', coin, False, '부분매도 쿨다운', {
                                'time_since_last': f"{time_since_last/3600:.1f}시간",
                                'cooldown_remaining': f"{hours_remaining:.1f}시간",
                                'rsi': f"{rsi:.1f}",
                                'planned_sell_ratio': f"{sell_ratio:.0%}",
                                'trend': trend,
                                'change_rate': f"{change_rate:.1f}%",
                                'volume_ratio': f"{volume_ratio:.1f}배"
                            })
                            continue
                    
                    current_balance = upbit.get_balance(ticker)
                    if current_balance > 0:
                        sell_amount = current_balance * sell_ratio
                        
                        # 안전한 부분 매도 가격 조회 (재시도 로직 추가)
                        partial_sell_orderbook = None
                        for retry in range(3):
                            try:
                                partial_sell_orderbook = pyupbit.get_orderbook(ticker=ticker)
                                if partial_sell_orderbook and isinstance(partial_sell_orderbook, dict) and 'orderbook_units' in partial_sell_orderbook and partial_sell_orderbook['orderbook_units']:
                                    break
                            except (KeyError, TypeError, Exception) as e:
                                print(f"  ⚠️ {coin} 부분매도 호가 조회 실패 (시도 {retry+1}/3): {e}")
                                time.sleep(1)
                        
                        if not partial_sell_orderbook or not isinstance(partial_sell_orderbook, dict) or 'orderbook_units' not in partial_sell_orderbook or not partial_sell_orderbook['orderbook_units']:
                            print(f"  ⚠️ {coin} 호가 정보 없음 - 부분 매도 건너뜀")
                            logging.warning(f"PARTIAL_SELL_SKIP - {coin}: 호가 정보 없음")
                            continue
                            
                        current_price = partial_sell_orderbook['orderbook_units'][0]['bid_price']
                        sell_value = sell_amount * current_price
                        
                        if sell_value > MIN_TRADE_AMOUNT:
                            # 부분 매도 전 상세 정보 로깅
                            logging.info(f"PARTIAL_SELL_ATTEMPT - {coin} | RSI: {rsi:.1f} | 매도율: {sell_ratio:.0%} | "
                                       f"추세: {trend} | 상승률: +{change_rate:.1f}% | 거래량: {volume_ratio:.1f}배 | "
                                       f"보유량: {current_balance:.6f} | 매도량: {sell_amount:.6f}")
                            
                            result = upbit.sell_market_order(ticker, sell_amount)
                            if result:
                                remaining = current_balance - sell_amount
                                log_decision('PARTIAL_SELL', coin, True, '부분매도 완료', {
                                    'rsi': f"{rsi:.1f}",
                                    'sell_amount': f"{sell_amount:.6f}",
                                    'sell_ratio': f"{sell_ratio:.0%}",
                                    'remaining': f"{remaining:.6f}",
                                    'trend': trend,
                                    'change_rate': f"{change_rate:.1f}%",
                                    'volume_ratio': f"{volume_ratio:.1f}배",
                                    'current_price': current_price
                                })
                                message = f"{coin} 부분 매도 완료: {sell_amount:.6f} ({sell_ratio:.0%}) | RSI: {rsi:.1f} | 잔여: {remaining:.6f}"
                                print(f"  ✅ {message}")
                                logging.info(f"PARTIAL_SELL_SUCCESS - {message}")
                                
                                # 🔴 부분매도 쿨다운 시간 기록
                                last_partial_sell_time[coin] = time.time()
                            else:
                                print(f"  ❌ {coin} 부분 매도 실패")
                                logging.error(f"PARTIAL_SELL_FAILED - {coin} | RSI: {rsi:.1f}")
                        else:
                            print(f"  ⏸️ 매도 금액 부족 ({sell_value:,.0f}원 < {MIN_TRADE_AMOUNT:,.0f}원)")
                            logging.warning(f"PARTIAL_SELL_SKIP - {coin} | 금액 부족: {sell_value:,.0f}원")
                    else:
                        print(f"  ⏸️ 보유량 없음")
                        logging.warning(f"PARTIAL_SELL_SKIP - {coin} | 보유량 없음")
                    continue  # 부분 매도 후 다음 코인으로
                
                # 거래 전 포트폴리오 스냅샷 (정상 매도)
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
                    
                    # 안전한 매도 가격 조회 (재시도 로직 추가)
                    sell_orderbook = None
                    for retry in range(3):
                        try:
                            sell_orderbook = pyupbit.get_orderbook(ticker=ticker)
                            if sell_orderbook and isinstance(sell_orderbook, dict) and 'orderbook_units' in sell_orderbook and sell_orderbook['orderbook_units']:
                                break
                        except (KeyError, TypeError, Exception) as e:
                            print(f"  ⚠️ {coin} 매도 호가 조회 실패 (시도 {retry+1}/3): {e}")
                            time.sleep(1)
                    
                    if not sell_orderbook or not isinstance(sell_orderbook, dict) or 'orderbook_units' not in sell_orderbook or not sell_orderbook['orderbook_units']:
                        print(f"  ⚠️ {coin} 호가 정보 없음 - 매도 건너뜀")
                        logging.warning(f"SELL_SKIP - {coin}: 호가 정보 없음")
                        continue
                        
                    current_price = sell_orderbook['orderbook_units'][0]['bid_price']
                    sell_value = sell_amount * current_price
                    
                    if sell_value > MIN_TRADE_AMOUNT:
                        result = upbit.sell_market_order(ticker, sell_amount)
                        if result:
                            log_decision('SELL', coin, True, '매도 완료', {
                                'sell_amount': f"{sell_amount:.6f}",
                                'sell_ratio': f"{sell_ratio:.1%}",
                                'confidence': f"{confidence:.1%}",
                                'daily_sell_count': daily_sell_count.get(coin, 0) + 1,
                                'current_price': current_price
                            })
                            message = f"{coin} 매도 완료: {sell_amount:.6f} ({sell_ratio:.1%}) | 신뢰도: {confidence:.1%}"
                            print(f"  ✅ {message}")
                            logging.info(f"SELL - {message}")
                            
                            # 🔴 일일 SELL 카운트 증가
                            daily_sell_count[coin] = daily_sell_count.get(coin, 0) + 1
                            
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
                # 🚀 HOLD 신호에서도 상승 추세 매수 기회 포착
                market_data = portfolio_summary.get('coins', {}).get(coin, {})
                trend = market_data.get('trend_alignment', '')
                change_rate = market_data.get('change_rate', 0)
                rsi = market_data.get('rsi', 50)
                
                # 강한 상승 추세 + HOLD 신호 + 낮은 보유 비중 → 매수 고려
                current_coin_balance = upbit.get_balance(ticker)
                
                # 안전한 가격 조회 (재시도 로직 추가)
                hold_orderbook = None
                for retry in range(3):
                    try:
                        hold_orderbook = pyupbit.get_orderbook(ticker=ticker)
                        if hold_orderbook and isinstance(hold_orderbook, dict) and 'orderbook_units' in hold_orderbook and hold_orderbook['orderbook_units']:
                            break
                    except (KeyError, TypeError, Exception) as e:
                        print(f"  ⚠️ {coin} HOLD 호가 조회 실패 (시도 {retry+1}/3): {e}")
                        time.sleep(1)
                
                if not hold_orderbook or not isinstance(hold_orderbook, dict) or 'orderbook_units' not in hold_orderbook or not hold_orderbook['orderbook_units']:
                    print(f"  ⏸️  보유 (호가 정보 없음)")
                    continue
                    
                current_price = hold_orderbook['orderbook_units'][0]['ask_price']
                current_coin_value = current_coin_balance * current_price if current_coin_balance > 0 else 0
                
                # 전체 포트폴리오 가치 계산 (KRW + 모든 코인) - 정확한 비중 계산, 개별 예외 처리
                total_value = upbit.get_balance("KRW")
                for other_ticker in PORTFOLIO_COINS:
                    try:
                        other_balance = upbit.get_balance(other_ticker)
                        if other_balance > 0:
                            other_orderbook = pyupbit.get_orderbook(ticker=other_ticker)
                            if other_orderbook and 'orderbook_units' in other_orderbook and other_orderbook['orderbook_units']:
                                other_price = other_orderbook['orderbook_units'][0]['ask_price']
                                total_value += other_balance * other_price
                    except Exception as e:
                        logging.debug(f"{other_ticker} HOLD 비중 조회 실패 (무시): {e}")
                        continue
                
                current_coin_ratio = current_coin_value / total_value if total_value > 0 else 0
                
                # 상승 추세 + 낮은 비중 + HOLD → 소량 매수
                if 'strong_bullish' in trend and change_rate > 3 and current_coin_ratio < 0.10 and confidence >= 0.6:
                    print(f"  🎯 {coin} HOLD이지만 강한 상승 추세 감지 - 소량 매수 기회 포착")
                    print(f"     추세: {trend}, 변화율: +{change_rate:.1f}%, 현재비중: {current_coin_ratio:.1%}")
                    
                    # 소량 매수 실행 (기본 비율의 50%)
                    krw_balance = upbit.get_balance("KRW")
                    small_buy_amount = krw_balance * BASE_TRADE_RATIO * 0.5  # 기본 비율의 50%만 매수
                    
                    if small_buy_amount >= MIN_TRADE_AMOUNT:
                        buy_result = upbit.buy_market_order(ticker, small_buy_amount)
                        if buy_result:
                            print(f"  ✅ {coin} HOLD 소량 매수 실행 완료: {small_buy_amount:,.0f} KRW")
                            executed_trades.append({'coin': coin, 'action': 'HOLD_BUY', 'amount': small_buy_amount})
                        else:
                            print(f"  ❌ {coin} HOLD 소량 매수 실패")
                    else:
                        print(f"  ⚠️ {coin} 매수 금액 부족 ({small_buy_amount:,.0f} KRW < {MIN_TRADE_AMOUNT:,.0f} KRW)")
                else:
                    print(f"  ⏸️  보유 (신뢰도: {confidence:.1%})")
                
        except Exception as e:
            print(f"  ❌ {coin} 거래 오류: {e}")
            logging.error(f"TRADE_ERROR - {coin}: {type(e).__name__} - {str(e)}")
            import traceback
            logging.error(f"상세 오류:\n{traceback.format_exc()}")  # DEBUG → ERROR로 변경
    
    print(f"\n✅ 포트폴리오 매매 실행 완료")


# ============================================================================
# 상세 로깅 함수 (투자 데이터 수집용)
# ============================================================================

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


# ============================================================================
# 체크 주기 계산 및 모니터링 함수
# ============================================================================

def calculate_check_interval(portfolio_summary, news_analysis=None):
    """시장 변동성과 뉴스 긴급도에 따른 체크 주기 계산 - 기회 포착 강화"""
    total_volatility = 0
    coin_count = 0
    
    for coin, data in portfolio_summary.get('coins', {}).items():
        change_rate = abs(data.get('change_rate', 0))
        total_volatility += change_rate
        coin_count += 1
    
    if coin_count == 0:
        return CHECK_INTERVALS["default_interval"] * 60  # 기본 간격 (분 → 초)
    
    avg_volatility = total_volatility / coin_count
    
    # 뉴스 긴급도 우선 체크
    if news_analysis and news_analysis.get('emergency', False):
        interval_min = CHECK_INTERVALS.get("news_emergency_interval", 5)
        print(f"🚨 긴급 뉴스 감지 → {interval_min}분 후 재체크")
        return interval_min * 60
    
    # config에서 설정한 변동성 기준과 간격 사용 (더 공격적으로 조정됨)
    if avg_volatility > CHECK_INTERVALS["extreme_volatility_threshold"]:      # 극고변동성
        interval_min = CHECK_INTERVALS["extreme_volatility_interval"]  # 10분
        print(f"🔥 극고변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60           # 분 → 초
    elif avg_volatility > CHECK_INTERVALS["high_volatility_threshold"]:       # 고변동성
        interval_min = CHECK_INTERVALS["high_volatility_interval"]  # 25분
        print(f"📈 고변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60              # 분 → 초
    elif avg_volatility > CHECK_INTERVALS["medium_volatility_threshold"]:     # 중변동성  
        interval_min = CHECK_INTERVALS["medium_volatility_interval"]  # 45분
        print(f"📊 중변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60            # 분 → 초
    else:                                                                    # 저변동성
        interval_min = CHECK_INTERVALS["low_volatility_interval"]  # 90분
        print(f"😴 저변동성 감지 ({avg_volatility:.1f}%) → {interval_min}분 후 재체크")
        return interval_min * 60               # 분 → 초

# load_config() 함수는 상단에 정의되어 있음 (중복 제거됨)

def setup_logging():
    """로깅 시스템 설정"""
    # log 폴더 생성
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    
    log_filename = os.path.join(log_dir, f"trading_bot_{datetime.now().strftime('%Y%m%d')}.log")
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
    # log 폴더 생성
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    
    # 상세 거래 로그
    trade_logger = logging.getLogger('trade_logger')
    trade_logger.setLevel(logging.INFO)
    trade_handler = logging.FileHandler(
        os.path.join(log_dir, f'trades_{datetime.now().strftime("%Y%m%d")}.json'), 
        encoding='utf-8'
    )
    trade_handler.setFormatter(logging.Formatter('%(message)s'))
    trade_logger.addHandler(trade_handler)
    
    # AI 신호 로그
    signal_logger = logging.getLogger('signal_logger')
    signal_logger.setLevel(logging.INFO)
    signal_handler = logging.FileHandler(
        os.path.join(log_dir, f'ai_signals_{datetime.now().strftime("%Y%m%d")}.json'), 
        encoding='utf-8'
    )
    signal_handler.setFormatter(logging.Formatter('%(message)s'))
    signal_logger.addHandler(signal_handler)
    
    # 성과 로그
    performance_logger = logging.getLogger('performance_logger')
    performance_logger.setLevel(logging.INFO)
    performance_handler = logging.FileHandler(
        os.path.join(log_dir, f'performance_{datetime.now().strftime("%Y%m%d")}.json'), 
        encoding='utf-8'
    )
    performance_handler.setFormatter(logging.Formatter('%(message)s'))
    performance_logger.addHandler(performance_handler)
    
    return trade_logger, signal_logger, performance_logger


# ============================================================================
# 신규/트렌드 코인 자동 투자 스레드 (적응형 체크 주기)
# ============================================================================

def trend_coin_trading_loop(upbit, stop_event):
    """
    신규/트렌드 코인 자동 투자 - 독립 스레드 (적응형 체크 주기)
    - 보유 중: 5분마다 빠른 모니터링 (손절/익절)
    - 미보유: 20분마다 기회 탐색
    - stop_event로 종료 제어
    """
    logger = logging.getLogger(__name__)
    
    # 관리 중인 신규코인 추적 (이 함수에서 매수한 코인만)
    managed_coins = set()
    
    while not stop_event.is_set():
        try:
            logger.info(f"🔄 [신규코인] 트렌드 코인 체크 시작")
            print(f"\n🔄 [신규코인] 트렌드 코인 체크 ({datetime.now().strftime('%H:%M:%S')})")
            
            # 신규코인 투자/관리 실행 (관리 중인 코인 전달 및 반환)
            current_holdings = execute_new_coin_trades(
                upbit,
                portfolio_coins=PORTFOLIO_COINS,
                min_trade_amount=MIN_TRADE_AMOUNT,
                invest_ratio=TREND_INVEST_RATIO,
                check_interval_min=5,  # 항상 5분 주기 전달 (관리 모드용)
                managed_coins=managed_coins
            )
            
            # 적응형 체크 주기 결정
            if current_holdings:
                check_interval = 5  # 보유 중: 5분 (빠른 모니터링)
                status = f"보유 중 {len(current_holdings)}개"
            else:
                check_interval = TREND_CHECK_INTERVAL_MIN  # 미보유: 20분
                status = "탐색 중"
            
            logger.info(f"✅ [신규코인] 체크 완료 - {check_interval}분 후 재체크 ({status})")
            print(f"⏰ [신규코인] {check_interval}분 후 재체크 ({status})")
            
            # 적응형 대기 (1초마다 stop_event 확인)
            for _ in range(check_interval * 60):
                if stop_event.is_set():
                    break
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ [신규코인] 투자 오류: {e}")
            print(f"❌ [신규코인] 투자 오류: {e}")
            # 오류 발생 시 5분 대기
            for _ in range(300):
                if stop_event.is_set():
                    break
                time.sleep(1)
    
    logger.info("🛑 [신규코인] 트렌드 코인 투자 스레드 종료")
    print("🛑 [신규코인] 트렌드 코인 투자 스레드 종료")


# ============================================================================
# 메인 트레이딩 봇 실행 함수
# ============================================================================

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
    
    # 신규코인 투자 스레드 시작 (20분마다 독립 실행)
    stop_event = threading.Event()
    trend_thread = threading.Thread(
        target=trend_coin_trading_loop, 
        args=(upbit, stop_event),
        daemon=True,
        name="TrendCoinThread"
    )
    trend_thread.start()
    logger.info("🚀 [신규코인] 트렌드 코인 투자 스레드 시작 (20분 주기)")
    print(f"🚀 [신규코인] 트렌드 코인 투자 스레드 시작 (20분 주기)")
    
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
            portfolio_data = get_portfolio_data(PORTFOLIO_COINS, DATA_PERIOD)
            
            if not portfolio_data:
                print("❌ 데이터 수집 실패, 1시간 후 재시도")
                time.sleep(60 * 60)
                continue
            
            # 2. 시장 지표 수집 (뉴스 감정 분석 추가)
            print("📈 시장 지표 수집 중...")
            fng = get_fear_greed_index()
            news = get_news_headlines(PORTFOLIO_COINS, CACHE_FILE, CACHE_DURATION)
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
            portfolio_summary = make_portfolio_summary(portfolio_data, fng, news, calculate_rsi)
            
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

            # 7-1. 신규/트렌드 코인 투자는 별도 스레드에서 20분마다 실행 중
            # (execute_new_coin_trades는 메인 루프에서 제거됨)
            
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
            stop_event.set()  # 신규코인 스레드 종료 신호
            trend_thread.join(timeout=5)  # 최대 5초 대기
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


# ============================================================================
# 프로그램 시작점
# ============================================================================
