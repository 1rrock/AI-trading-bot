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


def get_safe_orderbook(ticker):
    """
    안전한 호가 조회 함수 (중복 검증 로직 통합)
    
    Args:
        ticker: 티커 심볼 (예: "KRW-BTC")
    
    Returns:
        dict: 유효한 호가 정보 또는 None
    """
    try:
        orderbook = pyupbit.get_orderbook(ticker=ticker)
        if not orderbook:
            logging.debug(f"{ticker} 호가 정보 없음 (None)")
            return None
        
        if 'orderbook_units' not in orderbook:
            logging.debug(f"{ticker} orderbook_units 키 없음")
            return None
            
        if not orderbook['orderbook_units'] or len(orderbook['orderbook_units']) == 0:
            logging.debug(f"{ticker} orderbook_units 비어있음")
            return None
        
        return orderbook
    except Exception as e:
        logging.debug(f"{ticker} 호가 조회 실패: {e}")
        return None


def get_total_portfolio_value(upbit):
    """
    전체 포트폴리오 가치 계산 (KRW + 모든 코인)
    
    Args:
        upbit: Upbit 객체
    
    Returns:
        float: 총 자산 가치 (KRW)
    """
    try:
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
                    logging.debug(f"{ticker} 가격 조회 오류 (무시): {e}")
                    continue
        
        return total_value
    except Exception as e:
        logging.error(f"총 자산 계산 실패: {e}")
        return 0
