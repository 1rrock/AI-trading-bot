"""
상장폐지/거래정지 코인 관리 모듈
중앙 집중식 관리로 유지보수 용이
"""

# 상장폐지/거래정지 코인 목록 (티커에서 'KRW-' 제외한 코인명)
DELISTED_COINS = {
    'APENFT',  # 업비트 상장폐지
    'XCORE',   # 업비트 상장폐지
    'NFT',     # 업비트 상장폐지
}


def is_delisted(ticker_or_currency: str) -> bool:
    """
    상장폐지 코인 여부 확인
    
    Args:
        ticker_or_currency: 티커 (예: "KRW-BTC") 또는 코인명 (예: "BTC")
    
    Returns:
        bool: 상장폐지 코인이면 True
    
    Examples:
        >>> is_delisted("KRW-APENFT")
        True
        >>> is_delisted("APENFT")
        True
        >>> is_delisted("KRW-BTC")
        False
        >>> is_delisted("BTC")
        False
    """
    # 'KRW-' 접두사 제거
    currency = ticker_or_currency.replace('KRW-', '')
    return currency in DELISTED_COINS


def get_delisted_coins() -> set:
    """
    상장폐지 코인 목록 반환
    
    Returns:
        set: 상장폐지 코인 집합
    """
    return DELISTED_COINS.copy()


def add_delisted_coin(currency: str) -> None:
    """
    상장폐지 코인 추가 (런타임 동적 추가)
    
    Args:
        currency: 코인명 (예: "BTC")
    """
    DELISTED_COINS.add(currency.replace('KRW-', ''))


def remove_delisted_coin(currency: str) -> None:
    """
    상장폐지 코인 제거 (재상장 시)
    
    Args:
        currency: 코인명 (예: "BTC")
    """
    DELISTED_COINS.discard(currency.replace('KRW-', ''))
