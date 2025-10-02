#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
실제 투자 데이터 분석 도구
- 거래 로그 분석
- AI 신호 성과 분석  
- 포트폴리오 성과 추적
- 비용 효율성 분석
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import glob
import warnings
warnings.filterwarnings('ignore')

# 한글 폰트 설정 (맥OS)
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

class TradingLogAnalyzer:
    def __init__(self, log_date=None):
        """로그 분석기 초기화"""
        if log_date is None:
            log_date = datetime.now().strftime('%Y%m%d')
        
        self.log_date = log_date
        self.trade_file = f'trades_{log_date}.json'
        self.signal_file = f'ai_signals_{log_date}.json'
        self.performance_file = f'performance_{log_date}.json'
        
        print(f"📊 거래 로그 분석 ({log_date})")
        print(f"파일: {self.trade_file}, {self.signal_file}, {self.performance_file}")
    
    def load_trade_logs(self):
        """거래 로그 로드"""
        trades = []
        if Path(self.trade_file).exists():
            with open(self.trade_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        trade = json.loads(line.strip())
                        trades.append(trade)
                    except:
                        continue
        
        return pd.DataFrame(trades) if trades else pd.DataFrame()
    
    def load_signal_logs(self):
        """AI 신호 로그 로드"""
        signals = []
        if Path(self.signal_file).exists():
            with open(self.signal_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        signal = json.loads(line.strip())
                        signals.append(signal)
                    except:
                        continue
        
        return pd.DataFrame(signals) if signals else pd.DataFrame()
    
    def load_performance_logs(self):
        """성과 로그 로드"""
        performances = []
        if Path(self.performance_file).exists():
            with open(self.performance_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        perf = json.loads(line.strip())
                        performances.append(perf)
                    except:
                        continue
        
        return pd.DataFrame(performances) if performances else pd.DataFrame()
    
    def analyze_trades(self):
        """거래 분석"""
        trades_df = self.load_trade_logs()
        
        if trades_df.empty:
            print("❌ 거래 데이터가 없습니다.")
            return
        
        print(f"\n📈 거래 분석 결과 ({len(trades_df)}건)")
        print("=" * 50)
        
        # 코인별 거래 통계
        print("🪙 코인별 거래 현황:")
        coin_stats = trades_df.groupby('coin').agg({
            'action': 'count',
            'total_value': 'sum',
            'balance_change': 'sum'
        }).round(0)
        coin_stats.columns = ['거래횟수', '총거래금액', '잔고변화']
        print(coin_stats)
        
        # 매수/매도 분석
        print(f"\n💰 매수/매도 분석:")
        action_stats = trades_df.groupby('action').agg({
            'coin': 'count',
            'total_value': ['sum', 'mean'],
            'balance_change': 'sum'
        }).round(0)
        print(action_stats)
        
        # 신뢰도별 성과
        if 'ai_signal' in trades_df.columns:
            print(f"\n🤖 AI 신뢰도별 분석:")
            trades_df['confidence'] = trades_df['ai_signal'].apply(
                lambda x: x.get('confidence', 0) if isinstance(x, dict) else 0
            )
            
            # 신뢰도 구간별 분석
            trades_df['confidence_range'] = pd.cut(trades_df['confidence'], 
                                                 bins=[0, 0.5, 0.7, 0.9, 1.0], 
                                                 labels=['낮음(~50%)', '보통(50-70%)', '높음(70-90%)', '매우높음(90%~)'])
            
            confidence_stats = trades_df.groupby('confidence_range').agg({
                'coin': 'count',
                'total_value': 'sum',
                'balance_change': 'sum'
            }).round(0)
            confidence_stats.columns = ['거래횟수', '총거래금액', '잔고변화']
            print(confidence_stats)
    
    def analyze_ai_signals(self):
        """AI 신호 분석"""
        signals_df = self.load_signal_logs()
        
        if signals_df.empty:
            print("❌ AI 신호 데이터가 없습니다.")
            return
        
        print(f"\n🤖 AI 신호 분석 결과 ({len(signals_df)}개)")
        print("=" * 50)
        
        # 신호별 통계
        signal_counts = signals_df['signal'].value_counts()
        print("📊 신호 분포:")
        for signal, count in signal_counts.items():
            pct = (count / len(signals_df)) * 100
            print(f"  {signal}: {count}회 ({pct:.1f}%)")
        
        # 코인별 신호 분석
        print(f"\n🪙 코인별 AI 신호:")
        coin_signal_crosstab = pd.crosstab(signals_df['coin'], signals_df['signal'])
        print(coin_signal_crosstab)
        
        # 신뢰도 분석
        if 'confidence' in signals_df.columns:
            avg_confidence = signals_df.groupby('signal')['confidence'].agg(['mean', 'std']).round(3)
            print(f"\n📈 신호별 평균 신뢰도:")
            print(avg_confidence)
        
        # AI 비용 분석
        if 'cost_info' in signals_df.columns:
            total_cost = 0
            total_tokens = 0
            
            for _, row in signals_df.iterrows():
                cost_info = row.get('cost_info', {})
                if isinstance(cost_info, dict):
                    total_cost += cost_info.get('cost_krw', 0)
                    total_tokens += cost_info.get('tokens_used', 0)
            
            if total_cost > 0:
                print(f"\n💰 AI 사용 비용:")
                print(f"  총 비용: {total_cost:,.0f}원")
                print(f"  총 토큰: {total_tokens:,}개")
                print(f"  평균 비용/신호: {total_cost/len(signals_df):.0f}원")
    
    def analyze_performance(self):
        """성과 분석"""
        perf_df = self.load_performance_logs()
        
        if perf_df.empty:
            print("❌ 성과 데이터가 없습니다.")
            return
        
        print(f"\n📊 포트폴리오 성과 분석")
        print("=" * 50)
        
        # 포트폴리오 가치 변화
        if 'portfolio_value' in perf_df.columns:
            initial_value = perf_df['portfolio_value'].iloc[0]
            final_value = perf_df['portfolio_value'].iloc[-1]
            total_return = ((final_value - initial_value) / initial_value) * 100
            
            print(f"🏦 포트폴리오 가치 변화:")
            print(f"  시작: {initial_value:,.0f}원")
            print(f"  현재: {final_value:,.0f}원")
            print(f"  수익률: {total_return:+.2f}%")
        
        # 일일 수익률 통계
        if 'daily_return' in perf_df.columns:
            daily_returns = perf_df['daily_return']
            print(f"\n📈 일일 수익률 통계:")
            print(f"  평균: {daily_returns.mean():+.2f}%")
            print(f"  표준편차: {daily_returns.std():.2f}%")
            print(f"  최대: {daily_returns.max():+.2f}%")
            print(f"  최소: {daily_returns.min():+.2f}%")
        
        # AI 비용 효율성
        if 'ai_cost_today' in perf_df.columns:
            total_ai_cost = perf_df['ai_cost_today'].iloc[-1] if len(perf_df) > 0 else 0
            if total_ai_cost > 0 and 'portfolio_value' in perf_df.columns:
                portfolio_value = perf_df['portfolio_value'].iloc[-1]
                cost_ratio = (total_ai_cost / portfolio_value) * 100
                print(f"\n💰 AI 비용 효율성:")
                print(f"  총 AI 비용: {total_ai_cost:,.0f}원")
                print(f"  포트폴리오 대비: {cost_ratio:.3f}%")
    
    def generate_charts(self):
        """차트 생성"""
        trades_df = self.load_trade_logs()
        signals_df = self.load_signal_logs()
        perf_df = self.load_performance_logs()
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'거래 데이터 분석 ({self.log_date})', fontsize=16)
        
        # 1. 코인별 거래 횟수
        if not trades_df.empty:
            coin_counts = trades_df['coin'].value_counts()
            axes[0, 0].bar(coin_counts.index, coin_counts.values)
            axes[0, 0].set_title('코인별 거래 횟수')
            axes[0, 0].set_ylabel('거래 횟수')
        
        # 2. AI 신호 분포
        if not signals_df.empty:
            signal_counts = signals_df['signal'].value_counts()
            axes[0, 1].pie(signal_counts.values, labels=signal_counts.index, autopct='%1.1f%%')
            axes[0, 1].set_title('AI 신호 분포')
        
        # 3. 시간별 거래 패턴
        if not trades_df.empty:
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
            trades_df['hour'] = trades_df['timestamp'].dt.hour
            hourly_trades = trades_df['hour'].value_counts().sort_index()
            axes[1, 0].plot(hourly_trades.index, hourly_trades.values, marker='o')
            axes[1, 0].set_title('시간별 거래 패턴')
            axes[1, 0].set_xlabel('시간')
            axes[1, 0].set_ylabel('거래 횟수')
        
        # 4. 포트폴리오 가치 변화
        if not perf_df.empty and 'portfolio_value' in perf_df.columns:
            perf_df['timestamp'] = pd.to_datetime(perf_df['timestamp'])
            axes[1, 1].plot(perf_df['timestamp'], perf_df['portfolio_value'])
            axes[1, 1].set_title('포트폴리오 가치 변화')
            axes[1, 1].set_ylabel('가치 (원)')
            axes[1, 1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        chart_filename = f'trading_analysis_{self.log_date}.png'
        plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
        print(f"\n📊 차트 저장: {chart_filename}")
        plt.show()
    
    def generate_daily_report(self):
        """일일 보고서 생성"""
        print(f"\n📋 일일 거래 보고서 ({self.log_date})")
        print("=" * 60)
        
        self.analyze_trades()
        self.analyze_ai_signals()
        self.analyze_performance()
        self.generate_charts()
        
        # 개선사항 제안
        print(f"\n💡 전략 개선 제안:")
        print("=" * 30)
        
        trades_df = self.load_trade_logs()
        signals_df = self.load_signal_logs()
        
        if not trades_df.empty:
            # 성과가 좋은 신뢰도 구간 찾기
            if 'ai_signal' in trades_df.columns:
                trades_df['confidence'] = trades_df['ai_signal'].apply(
                    lambda x: x.get('confidence', 0) if isinstance(x, dict) else 0
                )
                
                high_conf_trades = trades_df[trades_df['confidence'] > 0.8]
                if len(high_conf_trades) > 0:
                    high_conf_return = high_conf_trades['balance_change'].sum()
                    print(f"  • 높은 신뢰도(80%+) 거래 성과: {high_conf_return:+,.0f}원")
                    if high_conf_return > 0:
                        print("    → 높은 신뢰도 신호에 더 집중 권장")
        
        if not signals_df.empty:
            # 가장 많이 나온 신호
            most_common_signal = signals_df['signal'].mode()[0]
            print(f"  • 가장 빈번한 AI 신호: {most_common_signal}")
            
            # AI 비용 효율성
            signals_today = len(signals_df)
            if signals_today > 0:
                print(f"  • AI 호출 빈도: {signals_today}회/일")
                if signals_today > 10:
                    print("    → 비용 절약을 위해 체크 주기 연장 고려")

def main():
    """메인 실행 함수"""
    import sys
    
    # 날짜 인자 처리
    if len(sys.argv) > 1:
        log_date = sys.argv[1]
    else:
        log_date = datetime.now().strftime('%Y%m%d')
    
    analyzer = TradingLogAnalyzer(log_date)
    analyzer.generate_daily_report()

if __name__ == "__main__":
    main()