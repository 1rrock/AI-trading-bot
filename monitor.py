#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
실시간 거래 모니터링 대시보드
- 실시간 포트폴리오 상태
- 최근 거래 내역
- AI 신호 추적
- 성과 지표 모니터링
"""

import json
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

class RealTimeDashboard:
    def __init__(self):
        self.log_date = datetime.now().strftime('%Y%m%d')
        self.update_interval = 30  # 30초마다 업데이트
        
    def clear_screen(self):
        """화면 초기화"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def load_latest_data(self):
        """최신 데이터 로드"""
        data = {
            'trades': [],
            'signals': [],
            'performance': []
        }
        
        # 거래 로그
        trade_file = f'trades_{self.log_date}.json'
        if Path(trade_file).exists():
            with open(trade_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        trade = json.loads(line.strip())
                        data['trades'].append(trade)
                    except:
                        continue
        
        # AI 신호 로그
        signal_file = f'ai_signals_{self.log_date}.json'
        if Path(signal_file).exists():
            with open(signal_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        signal = json.loads(line.strip())
                        data['signals'].append(signal)
                    except:
                        continue
        
        # 성과 로그
        performance_file = f'performance_{self.log_date}.json'
        if Path(performance_file).exists():
            with open(performance_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        perf = json.loads(line.strip())
                        data['performance'].append(perf)
                    except:
                        continue
        
        return data
    
    def format_time(self, timestamp_str):
        """시간 포맷팅"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%H:%M:%S')
        except:
            return timestamp_str
    
    def format_number(self, num):
        """숫자 포맷팅"""
        if isinstance(num, (int, float)):
            if num >= 1000000:
                return f"{num/1000000:.1f}M"
            elif num >= 1000:
                return f"{num/1000:.0f}K"
            else:
                return f"{num:,.0f}"
        return str(num)
    
    def display_header(self):
        """헤더 표시"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("🚀 AI 코인 트레이딩 봇 - 실시간 모니터링")
        print("=" * 60)
        print(f"📅 현재 시간: {now}")
        print(f"📊 데이터 날짜: {self.log_date}")
    
    def display_portfolio_status(self, data):
        """포트폴리오 현황 표시"""
        print("\n💼 포트폴리오 현황")
        print("-" * 40)
        
        if data['performance']:
            latest_perf = data['performance'][-1]
            portfolio_value = latest_perf.get('portfolio_value', 0)
            daily_return = latest_perf.get('daily_return', 0)
            ai_cost = latest_perf.get('ai_cost_today', 0)
            
            print(f"💰 총 자산: {self.format_number(portfolio_value)}원")
            print(f"📈 일일 수익률: {daily_return:+.2f}%")
            print(f"🤖 AI 비용: {self.format_number(ai_cost)}원")
            
            # 포트폴리오 배분
            allocation = latest_perf.get('portfolio_allocation', {})
            if allocation:
                print("\n🪙 자산 배분:")
                for asset, pct in allocation.items():
                    bar_length = int(pct / 5)  # 5%당 1개 바
                    bar = "█" * bar_length
                    print(f"  {asset:4s}: {pct:5.1f}% {bar}")
        else:
            print("❌ 포트폴리오 데이터 없음")
    
    def display_recent_trades(self, data):
        """최근 거래 내역"""
        print("\n💱 최근 거래 내역 (최대 10건)")
        print("-" * 40)
        
        if data['trades']:
            recent_trades = data['trades'][-10:]  # 최근 10건
            
            for trade in reversed(recent_trades):  # 최신순
                time_str = self.format_time(trade.get('timestamp', ''))
                coin = trade.get('coin', '')
                action = trade.get('action', '')
                amount = trade.get('amount', 0)
                price = trade.get('price', 0)
                total = trade.get('total_value', 0)
                
                # 액션 이모지
                action_emoji = "🟢" if action == "BUY" else "🔴"
                
                print(f"{time_str} {action_emoji} {coin:4s} {action:4s} "
                      f"{amount:8.4f} @ {self.format_number(price)}원 "
                      f"(총 {self.format_number(total)}원)")
        else:
            print("❌ 거래 내역 없음")
    
    def display_ai_signals(self, data):
        """AI 신호 현황"""
        print("\n🤖 최근 AI 신호 (최대 8개)")
        print("-" * 40)
        
        if data['signals']:
            recent_signals = data['signals'][-8:]  # 최근 8개
            
            for signal in reversed(recent_signals):  # 최신순
                # 데이터 타입 검증
                if not isinstance(signal, dict):
                    continue
                    
                time_str = self.format_time(signal.get('timestamp', ''))
                coin = signal.get('coin', '')
                signal_type = signal.get('signal', '')
                confidence = signal.get('confidence', 0)
                
                # 신호 이모지
                signal_emoji = {
                    'STRONG_BUY': '🟢🟢',
                    'BUY': '🟢',
                    'HOLD': '🟡',
                    'SELL': '🔴'
                }.get(signal_type, '⚪')
                
                print(f"{time_str} {signal_emoji} {coin:4s} {signal_type:10s} "
                      f"신뢰도: {confidence:.1%}")
        else:
            print("❌ AI 신호 없음")
    
    def display_statistics(self, data):
        """통계 정보"""
        print("\n📊 오늘의 통계")
        print("-" * 40)
        
        # 거래 통계
        trades_count = len(data['trades'])
        if trades_count > 0:
            buy_count = sum(1 for t in data['trades'] if t.get('action') == 'BUY')
            sell_count = sum(1 for t in data['trades'] if t.get('action') == 'SELL')
            total_volume = sum(t.get('total_value', 0) for t in data['trades'])
            
            print(f"💱 총 거래: {trades_count}건 (매수 {buy_count}, 매도 {sell_count})")
            print(f"💰 거래량: {self.format_number(total_volume)}원")
        
        # AI 신호 통계
        signals_count = len(data['signals'])
        if signals_count > 0:
            signal_types = {}
            total_cost = 0
            
            for signal in data['signals']:
                # 데이터 타입 검증
                if not isinstance(signal, dict):
                    continue
                    
                signal_type = signal.get('signal', 'UNKNOWN')
                signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
                
                cost_info = signal.get('cost_info', {})
                if isinstance(cost_info, dict):
                    total_cost += cost_info.get('cost_krw', 0)
            
            print(f"🤖 AI 호출: {signals_count}회")
            print(f"💸 AI 비용: {self.format_number(total_cost)}원")
            
            # 신호 분포
            signal_summary = ", ".join([f"{k}:{v}" for k, v in signal_types.items()])
            print(f"📊 신호 분포: {signal_summary}")
    
    def display_alerts(self, data):
        """알림 및 경고"""
        print("\n⚠️ 알림")
        print("-" * 40)
        
        alerts = []
        
        # 최근 거래에서 큰 손실 체크
        if data['trades']:
            recent_trades = data['trades'][-5:]  # 최근 5건
            for trade in recent_trades:
                balance_change = trade.get('balance_change', 0)
                if balance_change < -50000:  # 5만원 이상 손실
                    coin = trade.get('coin', '')
                    alerts.append(f"🔴 {coin} 큰 손실: {self.format_number(abs(balance_change))}원")
        
        # AI 비용 과다 사용 체크
        if data['signals']:
            today_cost = 0
            for signal in data['signals']:
                cost_info = signal.get('cost_info', {})
                if isinstance(cost_info, dict):
                    today_cost += cost_info.get('cost_krw', 0)
            
            if today_cost > 5000:  # 일일 5천원 초과
                alerts.append(f"💸 AI 비용 주의: {self.format_number(today_cost)}원/일")
        
        # 포트폴리오 가치 급락 체크
        if len(data['performance']) >= 2:
            current_value = data['performance'][-1].get('portfolio_value', 0)
            prev_value = data['performance'][-2].get('portfolio_value', 0)
            
            if prev_value > 0:
                change_pct = ((current_value - prev_value) / prev_value) * 100
                if change_pct < -5:  # 5% 이상 하락
                    alerts.append(f"📉 포트폴리오 급락: {change_pct:.1f}%")
        
        if alerts:
            for alert in alerts:
                print(f"  {alert}")
        else:
            print("  ✅ 특별한 알림 없음")
    
    def run_dashboard(self):
        """대시보드 실행"""
        print("🚀 실시간 모니터링 대시보드 시작")
        print("종료하려면 Ctrl+C를 누르세요.")
        
        try:
            while True:
                # 화면 클리어
                self.clear_screen()
                
                # 데이터 로드
                data = self.load_latest_data()
                
                # 화면 구성
                self.display_header()
                self.display_portfolio_status(data)
                self.display_recent_trades(data)
                self.display_ai_signals(data)
                self.display_statistics(data)
                self.display_alerts(data)
                
                # 하단 정보
                print(f"\n🔄 {self.update_interval}초마다 자동 업데이트 중...")
                print("종료: Ctrl+C")
                
                # 대기
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 모니터링을 종료합니다.")

def main():
    """메인 실행"""
    dashboard = RealTimeDashboard()
    dashboard.run_dashboard()

if __name__ == "__main__":
    main()