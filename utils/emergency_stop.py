"""
비상 정지 시스템
연속 실패, API 장애, 급격한 폭락 시 자동 거래 정지
"""

import logging
from datetime import datetime, timedelta
import pyupbit


class EmergencyStopSystem:
    """비상 정지 시스템"""
    
    def __init__(self):
        self.consecutive_failures = 0
        self.api_failures = 0
        self.last_check_time = datetime.now()
        self.is_stopped = False
        self.stop_reason = None
        
        # 임계값 설정
        self.MAX_CONSECUTIVE_FAILURES = 3
        self.MAX_API_FAILURES = 5
        self.CRASH_THRESHOLD = -0.10  # -10% 30분 내 폭락
        self.CRASH_TIMEFRAME = 30  # 30분
        
        # 가격 이력
        self.price_history = {}
    
    def check_consecutive_failures(self, success):
        """연속 실패 체크"""
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self.trigger_emergency_stop(f"연속 실패 {self.consecutive_failures}회")
            return True
        
        return False
    
    def check_api_health(self, upbit):
        """API 상태 체크"""
        try:
            # 간단한 API 호출 테스트
            balance = upbit.get_balance("KRW")
            if balance is None:
                self.api_failures += 1
            else:
                self.api_failures = 0
                
            if self.api_failures >= self.MAX_API_FAILURES:
                self.trigger_emergency_stop(f"API 장애 {self.api_failures}회")
                return False
                
            return True
            
        except Exception as e:
            self.api_failures += 1
            logging.error(f"API 상태 체크 실패: {e}")
            
            if self.api_failures >= self.MAX_API_FAILURES:
                self.trigger_emergency_stop(f"API 연결 실패 {self.api_failures}회")
                return False
            
            return True
    
    def check_market_crash(self, ticker, current_price):
        """급격한 폭락 감지 (30분 -10%)"""
        now = datetime.now()
        
        # 가격 이력 업데이트
        if ticker not in self.price_history:
            self.price_history[ticker] = []
        
        self.price_history[ticker].append({
            'time': now,
            'price': current_price
        })
        
        # 30분 이전 데이터 제거
        cutoff_time = now - timedelta(minutes=self.CRASH_TIMEFRAME)
        self.price_history[ticker] = [
            p for p in self.price_history[ticker] 
            if p['time'] > cutoff_time
        ]
        
        # 30분 전 가격이 있으면 비교
        if len(self.price_history[ticker]) >= 2:
            old_price = self.price_history[ticker][0]['price']
            change_rate = (current_price - old_price) / old_price
            
            if change_rate <= self.CRASH_THRESHOLD:
                self.trigger_emergency_stop(
                    f"{ticker} 급격한 폭락 감지: {change_rate:.1%} ({self.CRASH_TIMEFRAME}분)"
                )
                return True
        
        return False
    
    def trigger_emergency_stop(self, reason):
        """비상 정지 트리거"""
        self.is_stopped = True
        self.stop_reason = reason
        
        logging.critical(f"🚨 비상 정지 발동: {reason}")
        print(f"\n{'='*60}")
        print(f"🚨🚨🚨 비상 정지 시스템 작동 🚨🚨🚨")
        print(f"사유: {reason}")
        print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # 알림 (추후 Slack/Email 연동 가능)
        self.send_alert(reason)
    
    def send_alert(self, reason):
        """관리자 알림 (현재는 로그만)"""
        alert_message = f"""
        ⚠️ 긴급 알림 ⚠️
        
        비상 정지 시스템이 작동했습니다.
        
        사유: {reason}
        시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        즉시 확인이 필요합니다.
        1. 로그 파일 확인
        2. API 연결 상태 점검
        3. 시장 상황 확인
        4. 수동 개입 여부 결정
        """
        
        logging.critical(alert_message)
        
        # TODO: Slack/Email/SMS 알림 추가
        # - Slack Webhook
        # - Email (SMTP)
        # - Telegram Bot
    
    def emergency_sell_all(self, upbit, portfolio_coins):
        """긴급 전량 청산 (옵션)"""
        if not self.is_stopped:
            return False
        
        print("\n💸 긴급 청산 시작...")
        
        try:
            balances = upbit.get_balances()
            
            for balance in balances:
                if balance['currency'] == 'KRW':
                    continue
                
                ticker = f"KRW-{balance['currency']}"
                amount = float(balance['balance'])
                
                if amount > 0:
                    print(f"  매도: {ticker} {amount:.6f}")
                    result = upbit.sell_market_order(ticker, amount)
                    
                    if result:
                        print(f"  ✅ {ticker} 청산 완료")
                    else:
                        print(f"  ❌ {ticker} 청산 실패")
            
            print("💸 긴급 청산 완료\n")
            return True
            
        except Exception as e:
            logging.error(f"긴급 청산 오류: {e}")
            return False
    
    def can_trade(self):
        """거래 가능 여부"""
        return not self.is_stopped
    
    def reset(self, reason="수동 리셋"):
        """비상 정지 해제 (수동)"""
        self.is_stopped = False
        self.stop_reason = None
        self.consecutive_failures = 0
        self.api_failures = 0
        
        logging.info(f"✅ 비상 정지 해제: {reason}")
        print(f"\n✅ 비상 정지 해제: {reason}\n")
    
    def get_status(self):
        """현재 상태 반환"""
        return {
            'is_stopped': self.is_stopped,
            'stop_reason': self.stop_reason,
            'consecutive_failures': self.consecutive_failures,
            'api_failures': self.api_failures
        }


# 전역 비상 정지 시스템 인스턴스
emergency_system = EmergencyStopSystem()
