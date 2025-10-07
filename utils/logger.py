"""
로깅 유틸리티 모듈
거래 의사결정 및 상세 로깅 함수들
"""

import logging
import json


def log_decision(action: str, coin: str, allowed: bool, reason: str, context: dict):
    """
    거래 의사결정을 상세하게 로깅
    
    Args:
        action: 'BUY', 'SELL', 'PARTIAL_SELL', 'REBALANCE' 등
        coin: 코인 심볼
        allowed: 허용 여부 (True/False)
        reason: 결정 이유
        context: 추가 컨텍스트 정보
    """
    status = "✅ 허용" if allowed else "❌ 거부"
    
    # 콘솔 출력 (간략)
    if not allowed:
        print(f"  {status} {coin} {action}: {reason}")
    
    # 로그 파일 출력 (상세)
    logging.info(f"===== {action} 의사결정: {coin} =====")
    logging.info(f"결과: {status}")
    logging.info(f"이유: {reason}")
    logging.info(f"컨텍스트: {json.dumps(context, ensure_ascii=False, indent=2)}")
    logging.info("=" * 60)
