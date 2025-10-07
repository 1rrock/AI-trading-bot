"""
시장 상황 분석 모듈
"""


def analyze_market_condition(portfolio_summary, bull_threshold=10, bear_threshold=-10, 
                            high_vol_threshold=5, fng_extreme_fear=25, fng_extreme_greed=75):
    """
    전체 시장 상황 분석
    
    Args:
        portfolio_summary: 포트폴리오 요약 데이터
        bull_threshold: 상승장 판단 기준
        bear_threshold: 하락장 판단 기준
        high_vol_threshold: 고변동성 기준
        fng_extreme_fear: 극단적 공포 기준
        fng_extreme_greed: 극단적 탐욕 기준
    
    Returns:
        dict: 시장 상황 정보
    """
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
    try:
        fng_value = int(fng_value) if fng_value else 50
    except:
        fng_value = 50
    
    # 시장 상황 판단
    market_condition = "sideways"  # 기본값
    confidence = 0.5
    
    if avg_change > bull_threshold and bullish_coins > bearish_coins:
        if fng_value > fng_extreme_greed:
            market_condition = "bull_market_overheated"
            confidence = 0.8
        else:
            market_condition = "bull_market"
            confidence = 0.7
    elif avg_change < bear_threshold and bearish_coins > bullish_coins:
        if fng_value < fng_extreme_fear:
            market_condition = "bear_market_oversold"
            confidence = 0.8
        else:
            market_condition = "bear_market"
            confidence = 0.7
    elif avg_volatility > high_vol_threshold:
        market_condition = "high_volatility"
        confidence = 0.6
    
    return {
        "condition": market_condition,
        "confidence": confidence,
        "avg_change": avg_change,
        "avg_volatility": avg_volatility,
        "bullish_coins": bullish_coins,
        "bearish_coins": bearish_coins,
        "fng_value": str(fng_value)
    }


def detect_bear_market(portfolio_summary):
    """
    약세장 감지 로직 (하락장 방어 모드 활성화 기준)
    
    Args:
        portfolio_summary: 포트폴리오 요약 데이터
    
    Returns:
        dict: 약세장 여부 및 상세 정보
    """
    indicators = {
        'all_coins_down': 0,      # 모든 코인 하락 중
        'volume_decreasing': 0,   # 거래량 감소
        'rsi_bearish': 0,         # RSI 약세
        'news_negative': 0        # 악재 뉴스
    }
    
    coins = portfolio_summary.get('coins', {})
    if not coins or len(coins) == 0:
        return {'is_bear_market': False, 'confidence': 0, 'indicators': indicators}
    
    # 1. 모든 코인이 동시 하락 중인지 체크
    down_count = 0
    total_coins = len(coins)
    for coin, data in coins.items():
        change_rate = data.get('change_rate', 0)
        if change_rate < -3:  # -3% 이상 하락
            down_count += 1
    
    if down_count >= max(2, int(total_coins * 0.6)):  # 60% 이상 하락
        indicators['all_coins_down'] = 1
    
    # 2. 거래량 감소 체크
    low_volume_count = 0
    for coin, data in coins.items():
        # 다중 타임프레임에서 거래량 확인
        mtf = data.get('multi_timeframe', {})
        if mtf:
            day_volume = mtf.get('day', {}).get('volume_avg', 0)
            hour4_volume = mtf.get('hour4', {}).get('volume_avg', 0)
            
            # 4시간 거래량이 일봉 평균의 25% 미만 (거래 둔화)
            if day_volume > 0 and hour4_volume < day_volume * 0.25:
                low_volume_count += 1
    
    if low_volume_count >= max(2, int(total_coins * 0.5)):
        indicators['volume_decreasing'] = 1
    
    # 3. RSI 약세 체크
    bearish_rsi_count = 0
    for coin, data in coins.items():
        rsi = data.get('rsi', 50)
        trend = data.get('trend_alignment', '')
        # RSI 45 미만 + 약세 추세
        if rsi < 45 and ('bearish' in trend or 'weak' in trend):
            bearish_rsi_count += 1
    
    if bearish_rsi_count >= max(2, int(total_coins * 0.5)):
        indicators['rsi_bearish'] = 1
    
    # 4. 악재 뉴스 체크
    news_sentiment = portfolio_summary.get('news_sentiment', {})
    if news_sentiment.get('sentiment') == 'negative':
        indicators['news_negative'] = 1
    
    # 긴급 이벤트 체크 (추가)
    emergency_events = news_sentiment.get('emergency_events', [])
    if emergency_events:
        # 규제, 해킹 등 긴급 악재 있으면 강력한 약세 신호
        indicators['news_negative'] = 1
    
    # 약세장 판정 (4개 지표 중 3개 이상 충족)
    bear_score = sum(indicators.values())
    is_bear_market = bear_score >= 3
    confidence = bear_score / 4  # 0~1.0
    
    return {
        'is_bear_market': is_bear_market,
        'confidence': confidence,
        'bear_score': bear_score,
        'indicators': indicators,
        'reason': _get_bear_market_reason(indicators) if is_bear_market else None
    }


def _get_bear_market_reason(indicators):
    """약세장 판정 근거 텍스트 생성"""
    reasons = []
    if indicators['all_coins_down']:
        reasons.append("다수 코인 동시 하락")
    if indicators['volume_decreasing']:
        reasons.append("거래량 급감")
    if indicators['rsi_bearish']:
        reasons.append("RSI 약세 전환")
    if indicators['news_negative']:
        reasons.append("악재 뉴스 발생")
    
    return " + ".join(reasons) if reasons else "약세 신호 감지"
