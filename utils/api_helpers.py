"""
API 헬퍼 함수 모듈
업비트 API 호출 관련 유틸리티 함수들
"""

import pyupbit
import logging


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
        
        for balance in balances:
            if balance['currency'] != 'KRW':
                ticker = f"KRW-{balance['currency']}"
                try:
                    current_price = pyupbit.get_current_price(ticker)
                    if current_price:
                        total_value += float(balance['balance']) * current_price
                except Exception as e:
                    # 거래되지 않는 코인은 무시
                    logging.debug(f"{ticker} 가격 조회 실패 (무시): {e}")
                    continue
        
        return total_value
    except Exception as e:
        logging.error(f"총 자산 계산 실패: {e}")
        return 0
