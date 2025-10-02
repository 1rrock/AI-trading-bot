import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

class TradingBotComparator:
    """두 트레이딩 봇의 성과를 비교 분석하는 클래스"""
    
    def __init__(self, conservative_prefix="", contrarian_prefix="contrarian_"):
        self.conservative_prefix = conservative_prefix
        self.contrarian_prefix = contrarian_prefix
        self.date_str = datetime.now().strftime("%Y%m%d")
        
    def load_performance_data(self, bot_type="conservative"):
        """성과 데이터 로드"""
        prefix = self.contrarian_prefix if bot_type == "contrarian" else self.conservative_prefix
        folder = "contrarian_bot/" if bot_type == "contrarian" else ""
        filename = f"{folder}{prefix}performance_{self.date_str}.json"
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = []
                for line in f:
                    try:
                        data.append(json.loads(line.strip()))
                    except:
                        continue
                return data
        except FileNotFoundError:
            print(f"❌ {filename} 파일을 찾을 수 없습니다.")
            return []
    
    def load_trade_data(self, bot_type="conservative"):
        """거래 데이터 로드"""
        prefix = self.contrarian_prefix if bot_type == "contrarian" else self.conservative_prefix
        folder = "contrarian_bot/" if bot_type == "contrarian" else ""
        filename = f"{folder}{prefix}trades_{self.date_str}.json"
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = []
                for line in f:
                    try:
                        data.append(json.loads(line.strip()))
                    except:
                        continue
                return data
        except FileNotFoundError:
            print(f"❌ {filename} 파일을 찾을 수 없습니다.")
            return []
    
    def load_ai_signals(self, bot_type="conservative"):
        """AI 신호 데이터 로드"""
        prefix = self.contrarian_prefix if bot_type == "contrarian" else self.conservative_prefix
        folder = "contrarian_bot/" if bot_type == "contrarian" else ""
        filename = f"{folder}{prefix}ai_signals_{self.date_str}.json"
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = []
                for line in f:
                    try:
                        data.append(json.loads(line.strip()))
                    except:
                        continue
                return data
        except FileNotFoundError:
            print(f"❌ {filename} 파일을 찾을 수 없습니다.")
            return []
    
    def calculate_performance_metrics(self, performance_data, trades_data):
        """성과 지표 계산"""
        if not performance_data:
            return {}
        
        # 포트폴리오 가치 변화
        portfolio_values = [float(p.get('portfolio_value', 0)) for p in performance_data if p.get('portfolio_value')]
        
        if len(portfolio_values) < 2:
            return {}
        
        initial_value = portfolio_values[0]
        final_value = portfolio_values[-1]
        
        # 기본 수익률
        total_return = (final_value - initial_value) / initial_value * 100
        
        # 최대 손실 계산
        max_value = max(portfolio_values)
        min_value_after_max = min(portfolio_values[portfolio_values.index(max_value):]) if portfolio_values.index(max_value) < len(portfolio_values) - 1 else final_value
        max_drawdown = (min_value_after_max - max_value) / max_value * 100
        
        # 거래 관련 지표
        total_trades = len(trades_data)
        buy_trades = len([t for t in trades_data if t.get('action') == 'BUY'])
        sell_trades = len([t for t in trades_data if t.get('action') == 'SELL'])
        
        # 승률 계산 (간단화)
        profitable_trades = len([t for t in trades_data if t.get('action') == 'SELL' and t.get('balance_change', 0) > 0])
        win_rate = (profitable_trades / sell_trades * 100) if sell_trades > 0 else 0
        
        # AI 비용 계산
        ai_costs = [float(p.get('ai_cost_today', 0)) for p in performance_data if p.get('ai_cost_today')]
        total_ai_cost = max(ai_costs) if ai_costs else 0
        
        return {
            'initial_value': initial_value,
            'final_value': final_value,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'win_rate': win_rate,
            'total_ai_cost': total_ai_cost,
            'portfolio_values': portfolio_values
        }
    
    def analyze_signal_patterns(self, ai_signals):
        """AI 신호 패턴 분석"""
        if not ai_signals:
            return {}
        
        signal_counts = {'BUY': 0, 'SELL': 0, 'HOLD': 0, 'STRONG_BUY': 0, 'STRONG_SELL': 0}
        confidence_sum = 0
        signal_count = 0
        
        for signal_data in ai_signals:
            signal = signal_data.get('signal', 'HOLD')
            confidence = signal_data.get('confidence', 0)
            
            if signal in signal_counts:
                signal_counts[signal] += 1
            confidence_sum += confidence
            signal_count += 1
        
        avg_confidence = confidence_sum / signal_count if signal_count > 0 else 0
        
        return {
            'signal_distribution': signal_counts,
            'average_confidence': avg_confidence,
            'total_signals': signal_count
        }
    
    def compare_bots(self):
        """두 봇의 성과 비교"""
        print("🔍 트레이딩 봇 성과 비교 분석")
        print("=" * 60)
        
        # 데이터 로드
        conservative_performance = self.load_performance_data("conservative")
        contrarian_performance = self.load_performance_data("contrarian")
        
        conservative_trades = self.load_trade_data("conservative")
        contrarian_trades = self.load_trade_data("contrarian")
        
        conservative_signals = self.load_ai_signals("conservative")
        contrarian_signals = self.load_ai_signals("contrarian")
        
        # 성과 지표 계산
        conservative_metrics = self.calculate_performance_metrics(conservative_performance, conservative_trades)
        contrarian_metrics = self.calculate_performance_metrics(contrarian_performance, contrarian_trades)
        
        # 신호 패턴 분석
        conservative_signal_analysis = self.analyze_signal_patterns(conservative_signals)
        contrarian_signal_analysis = self.analyze_signal_patterns(contrarian_signals)
        
        # 결과 출력
        self.print_comparison_results(conservative_metrics, contrarian_metrics, 
                                    conservative_signal_analysis, contrarian_signal_analysis)
        
        return {
            'conservative': {
                'metrics': conservative_metrics,
                'signals': conservative_signal_analysis
            },
            'contrarian': {
                'metrics': contrarian_metrics,
                'signals': contrarian_signal_analysis
            }
        }
    
    def print_comparison_results(self, conservative_metrics, contrarian_metrics, 
                               conservative_signals, contrarian_signals):
        """비교 결과 출력"""
        
        print("📊 성과 비교")
        print("-" * 40)
        
        if conservative_metrics and contrarian_metrics:
            print(f"{'지표':<15} {'보수적 봇':<15} {'컨트래리언 봇':<15} {'차이':<10}")
            print("-" * 60)
            
            # 수익률 비교
            cons_return = conservative_metrics.get('total_return', 0)
            cont_return = contrarian_metrics.get('total_return', 0)
            return_diff = cont_return - cons_return
            print(f"{'수익률':<15} {cons_return:>12.2f}% {cont_return:>12.2f}% {return_diff:>+8.2f}%")
            
            # 최대 손실 비교
            cons_dd = conservative_metrics.get('max_drawdown', 0)
            cont_dd = contrarian_metrics.get('max_drawdown', 0)
            dd_diff = cont_dd - cons_dd
            print(f"{'최대손실률':<15} {cons_dd:>12.2f}% {cont_dd:>12.2f}% {dd_diff:>+8.2f}%")
            
            # 거래 횟수 비교
            cons_trades = conservative_metrics.get('total_trades', 0)
            cont_trades = contrarian_metrics.get('total_trades', 0)
            trade_diff = cont_trades - cons_trades
            print(f"{'거래횟수':<15} {cons_trades:>12}회 {cont_trades:>12}회 {trade_diff:>+8}회")
            
            # 승률 비교
            cons_win = conservative_metrics.get('win_rate', 0)
            cont_win = contrarian_metrics.get('win_rate', 0)
            win_diff = cont_win - cons_win
            print(f"{'승률':<15} {cons_win:>12.1f}% {cont_win:>12.1f}% {win_diff:>+8.1f}%")
            
            # AI 비용 비교
            cons_cost = conservative_metrics.get('total_ai_cost', 0)
            cont_cost = contrarian_metrics.get('total_ai_cost', 0)
            cost_diff = cont_cost - cons_cost
            print(f"{'AI비용':<15} {cons_cost:>12.0f}원 {cont_cost:>12.0f}원 {cost_diff:>+8.0f}원")
        
        print("\\n🤖 AI 신호 분석")
        print("-" * 40)
        
        if conservative_signals and contrarian_signals:
            print("보수적 봇 신호 분포:")
            cons_signals = conservative_signals.get('signal_distribution', {})
            for signal, count in cons_signals.items():
                print(f"  {signal}: {count}회")
            print(f"  평균 신뢰도: {conservative_signals.get('average_confidence', 0):.1%}")
            
            print("\\n컨트래리언 봇 신호 분포:")
            cont_signals = contrarian_signals.get('signal_distribution', {})
            for signal, count in cont_signals.items():
                print(f"  {signal}: {count}회")
            print(f"  평균 신뢰도: {contrarian_signals.get('average_confidence', 0):.1%}")
        
        print("\\n🏆 종합 평가")
        print("-" * 40)
        
        if conservative_metrics and contrarian_metrics:
            cons_return = conservative_metrics.get('total_return', 0)
            cont_return = contrarian_metrics.get('total_return', 0)
            cons_dd = abs(conservative_metrics.get('max_drawdown', 0))
            cont_dd = abs(contrarian_metrics.get('max_drawdown', 0))
            
            # 샤프 비율 (간단화된 버전)
            cons_sharpe = cons_return / (cons_dd + 1) if cons_dd > 0 else cons_return
            cont_sharpe = cont_return / (cont_dd + 1) if cont_dd > 0 else cont_return
            
            print(f"위험조정수익률 (수익률/위험도):")
            print(f"  보수적 봇: {cons_sharpe:.2f}")
            print(f"  컨트래리언 봇: {cont_sharpe:.2f}")
            
            if cont_sharpe > cons_sharpe:
                print("\\n🎯 결론: 컨트래리언 봇이 위험조정수익률에서 우수")
            elif cons_sharpe > cont_sharpe:
                print("\\n🎯 결론: 보수적 봇이 위험조정수익률에서 우수")
            else:
                print("\\n🎯 결론: 두 봇의 위험조정수익률이 비슷함")

def main():
    """메인 실행 함수"""
    comparator = TradingBotComparator()
    results = comparator.compare_bots()
    
    # 결과를 JSON 파일로 저장
    comparison_filename = f"bot_comparison_{datetime.now().strftime('%Y%m%d')}.json"
    with open(comparison_filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\\n📁 비교 결과가 {comparison_filename}에 저장되었습니다.")

if __name__ == "__main__":
    main()