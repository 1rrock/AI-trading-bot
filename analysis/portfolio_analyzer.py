"""
시장 분석 모듈
다중 타임프레임 분석, 시장 상황 판단, AI 신호 생성
"""

import time
import json
import logging
from openai import OpenAI


def analyze_multi_timeframe(coin_data, calculate_rsi_func):
    """
    다중 타임프레임 종합 분석
    
    Args:
        coin_data: 코인 타임프레임별 데이터
        calculate_rsi_func: RSI 계산 함수
    
    Returns:
        dict: 타임프레임별 분석 결과
    """
    analysis = {}
    
    for timeframe, df in coin_data.items():
        if df is not None and len(df) >= 20:
            rsi = calculate_rsi_func(df['close']).iloc[-1]
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


def calculate_trend_alignment(multi_tf_analysis):
    """
    다중 타임프레임 트렌드 일치도 계산
    
    Args:
        multi_tf_analysis: 타임프레임별 분석 결과
    
    Returns:
        str: 트렌드 일치도
    """
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


def make_portfolio_summary(portfolio_data, fng, news, calculate_rsi_func):
    """
    포트폴리오 전체 요약 생성 - 다중 타임프레임 지원
    
    Args:
        portfolio_data: 포트폴리오 데이터
        fng: 공포탐욕지수
        news: 뉴스 헤드라인
        calculate_rsi_func: RSI 계산 함수
    
    Returns:
        dict: 포트폴리오 요약
    """
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
            multi_tf_analysis = analyze_multi_timeframe(timeframe_data, calculate_rsi_func)
            
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
    
    # 전체 시장 상황 분석 추가 (순환 참조 방지를 위해 여기서 직접 호출)
    from analysis.market_condition import analyze_market_condition
    portfolio_summary["market_condition"] = analyze_market_condition(portfolio_summary)
    
    return portfolio_summary
