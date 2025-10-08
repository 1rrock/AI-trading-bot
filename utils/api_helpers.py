"""
API 헬퍼 함수 모듈
업비트 API 호출 관련 유틸리티 함수들
"""

import pyupbit
import logging
import time


def get_safe_price(ticker, max_retries=3):
    """
    안전한 가격 조회 함수 (재시도 로직 포함)
    
    Args:
        ticker: 티커 심볼 (예: "KRW-BTC")
        max_retries: 최대 재시도 횟수
    
    Returns:
        float: 현재 가격 또는 None
    """
    for attempt in range(max_retries):
        try:
            # API 부하 방지를 위한 짧은 대기
            if attempt > 0:
                time.sleep(0.3)  # 재시도 시 0.3초 대기
            
            price = pyupbit.get_current_price(ticker)
            
            # 가격이 유효하면 반환
            if price is not None and price > 0:
                return price
            
            # 가격이 0이거나 None이면 재시도
            if attempt < max_retries - 1:
                time.sleep(0.5)  # 0.5초 대기 후 재시도
                continue
                
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            else:
                logging.debug(f"{ticker} 가격 조회 실패: {e}")
                
    return None


def check_slippage_risk(ticker, order_amount, max_slippage=0.02):
    """
    슬리피지 리스크 체크 (호가 깊이 기반)
    
    Args:
        ticker: 티커 심볼
        order_amount: 주문 금액 (KRW)
        max_slippage: 최대 허용 슬리피지 (기본 2%)
    
    Returns:
        dict: {'safe': bool, 'expected_slippage': float, 'limit_price': float}
    """
    try:
        orderbook = get_safe_orderbook(ticker)
        if not orderbook:
            return {'safe': False, 'expected_slippage': 0, 'limit_price': 0}
        
        ask_price = orderbook['orderbook_units'][0]['ask_price']
        
        # 매도 1~5호가 총 금액 계산
        cumulative_amount = 0
        weighted_price = 0
        
        for unit in orderbook['orderbook_units'][:5]:
            size = unit['ask_size']
            price = unit['ask_price']
            unit_amount = size * price
            
            cumulative_amount += unit_amount
            weighted_price += price * unit_amount
            
            # 주문 금액을 커버할 수 있으면 중단
            if cumulative_amount >= order_amount:
                break
        
        # 예상 평균 체결가
        expected_avg_price = weighted_price / cumulative_amount if cumulative_amount > 0 else ask_price
        
        # 예상 슬리피지 계산
        expected_slippage = (expected_avg_price - ask_price) / ask_price
        
        # 안전 여부 판단
        is_safe = expected_slippage <= max_slippage and cumulative_amount >= order_amount
        
        # 지정가 한도 (슬리피지 제한)
        limit_price = ask_price * (1 + max_slippage)
        
        return {
            'safe': is_safe,
            'expected_slippage': expected_slippage,
            'limit_price': limit_price,
            'ask_price': ask_price,
            'cumulative_depth': cumulative_amount
        }
        
    except Exception as e:
        logging.error(f"슬리피지 체크 오류 ({ticker}): {e}")
        return {'safe': False, 'expected_slippage': 0, 'limit_price': 0}


def safe_market_order(upbit, ticker, order_type, amount, max_slippage=0.02):
    """
    슬리피지 제어된 안전한 주문 (지정가 우선, 실패 시 시장가)
    
    Args:
        upbit: Upbit 객체
        ticker: 티커 심볼
        order_type: 'buy' 또는 'sell'
        amount: 주문 금액 (buy) 또는 수량 (sell)
        max_slippage: 최대 허용 슬리피지
    
    Returns:
        주문 결과 또는 None
    """
    try:
        # 슬리피지 체크
        slippage_check = check_slippage_risk(ticker, amount if order_type == 'buy' else amount * get_safe_price(ticker), max_slippage)
        
        if slippage_check['safe']:
            # 안전: 지정가 주문
            if order_type == 'buy':
                limit_price = slippage_check['limit_price']
                quantity = amount / limit_price
                print(f"✅ 슬리피지 안전 - 지정가 매수: {ticker} @ {limit_price:,.0f}원")
                return upbit.buy_limit_order(ticker, limit_price, quantity)
            else:
                limit_price = slippage_check['ask_price'] * (1 - max_slippage)
                print(f"✅ 슬리피지 안전 - 지정가 매도: {ticker} @ {limit_price:,.0f}원")
                return upbit.sell_limit_order(ticker, limit_price, amount)
        else:
            # 위험: 시장가 주문 (긴급)
            print(f"⚠️ 슬리피지 위험 ({slippage_check['expected_slippage']:.1%}) - 시장가 주문: {ticker}")
            if order_type == 'buy':
                return upbit.buy_market_order(ticker, amount)
            else:
                return upbit.sell_market_order(ticker, amount)
                
    except Exception as e:
        logging.error(f"안전 주문 오류 ({ticker}): {e}")
        # 오류 시 기본 시장가 주문
        if order_type == 'buy':
            return upbit.buy_market_order(ticker, amount)
        else:
            return upbit.sell_market_order(ticker, amount)


def get_safe_orderbook(ticker, max_retries=3):
    """
    안전한 호가 조회 함수 (SSL 에러 대응 강화)
    
    Args:
        ticker: 티커 심볼 (예: "KRW-BTC")
        max_retries: 최대 재시도 횟수
    
    Returns:
        dict: 유효한 호가 정보 또는 None
    """
    for attempt in range(max_retries):
        try:
            # SSL 에러 방지를 위한 대기
            if attempt > 0:
                time.sleep(1.0)  # SSL 에러 시 1초 대기
            
            orderbook = pyupbit.get_orderbook(ticker=ticker)
            if not orderbook:
                logging.debug(f"{ticker} 호가 정보 없음 (None)")
                if attempt < max_retries - 1:
                    continue
                return None
            
            if 'orderbook_units' not in orderbook:
                logging.debug(f"{ticker} orderbook_units 키 없음")
                if attempt < max_retries - 1:
                    continue
                return None
                
            if not orderbook['orderbook_units'] or len(orderbook['orderbook_units']) == 0:
                logging.debug(f"{ticker} orderbook_units 비어있음")
                if attempt < max_retries - 1:
                    continue
                return None
            
            return orderbook
            
        except Exception as e:
            # SSL 에러 로깅
            if 'SSL' in str(e):
                logging.warning(f"{ticker} SSL 에러 (재시도 {attempt+1}/{max_retries}): {e}")
            else:
                logging.debug(f"{ticker} 호가 조회 실패: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(1.0)  # SSL 에러 시 1초 대기
                continue
            
    return None


def get_total_portfolio_value(upbit, max_retries=3):
    """
    전체 포트폴리오 가치 계산 (KRW + 모든 코인) - SSL 에러 대응 강화
    
    Args:
        upbit: Upbit 객체
        max_retries: 최대 재시도 횟수
    
    Returns:
        float: 총 자산 가치 (KRW)
    """
    for attempt in range(max_retries):
        try:
            # SSL 에러 방지를 위한 대기
            if attempt > 0:
                time.sleep(1.0)
            
            total_value = upbit.get_balance("KRW")
            balances = upbit.get_balances()
            
            for i, balance in enumerate(balances):
                if balance['currency'] != 'KRW':
                    ticker = f"KRW-{balance['currency']}"
                    
                    # API 부하 방지: 5개당 0.1초 대기
                    if i > 0 and i % 5 == 0:
                        time.sleep(0.1)
                    
                    try:
                        # 안전한 가격 조회 (재시도 포함)
                        current_price = get_safe_price(ticker, max_retries=3)
                        
                        if current_price is not None and current_price > 0:
                            coin_value = float(balance['balance']) * current_price
                            total_value += coin_value
                        else:
                            # 가격 조회 실패 시 경고
                            logging.warning(f"⚠️ {ticker} 가격 조회 실패 - 총 자산 계산에서 제외 (보유량: {balance['balance']})")
                    except Exception as e:
                        # 거래되지 않는 코인은 무시
                        logging.debug(f"{ticker} 총자산 계산 중 오류 (무시): {e}")
                        pass
            
            return total_value
            
        except Exception as e:
            # SSL 에러 로깅
            if 'SSL' in str(e):
                logging.warning(f"총 자산 계산 SSL 에러 (재시도 {attempt+1}/{max_retries}): {e}")
            else:
                logging.error(f"총 자산 계산 실패: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(1.0)
                continue
    
    # 모든 재시도 실패 시 0 반환
    logging.error("총 자산 계산 최종 실패 - 0 반환")
    return 0
