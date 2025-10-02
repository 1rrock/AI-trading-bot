# 🗃️ 실제 투자 데이터 수집 & 로깅 시스템 가이드

## 📋 개요

실제 투자 환경에서 모든 거래, AI 신호, 성과 데이터를 체계적으로 수집하여 전략 개선에 활용하는 종합 로깅 시스템입니다.

## 🎯 수집되는 데이터

### 1. 거래 로그 (`trades_YYYYMMDD.json`)
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "coin": "BTC",
  "action": "BUY",
  "amount": 0.00125,
  "price": 52000000,
  "total_value": 65000,
  "balance_change": -65000,
  "market_data": {
    "rsi": 35.2,
    "ma_20": 51500000,
    "bb_upper": 53000000,
    "bb_lower": 50000000,
    "volume_ratio": 1.8,
    "price_change_24h": 2.5
  },
  "ai_signal": {
    "signal": "BUY",
    "confidence": 0.85,
    "reasoning": "RSI 과매도 + 볼린저밴드 하단 접촉",
    "tokens_used": 650,
    "cost": 150
  },
  "portfolio_before": {...},
  "portfolio_after": {...}
}
```

### 2. AI 신호 로그 (`ai_signals_YYYYMMDD.json`)
```json
{
  "timestamp": "2024-01-15T10:29:30",
  "coin": "BTC",
  "signal": "BUY",
  "confidence": 0.85,
  "reasoning": "RSI 35로 과매도 상태, 20일선 위 돌파 시도",
  "market_context": {
    "rsi": 35.2,
    "ma_20": 51500000,
    "current_price": 52000000,
    "fear_greed_index": 25
  },
  "cost_info": {
    "tokens_used": 650,
    "cost_usd": 0.0012,
    "cost_krw": 156,
    "model": "gpt-3.5-turbo"
  }
}
```

### 3. 성과 로그 (`performance_YYYYMMDD.json`)
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "portfolio_value": 280000,
  "daily_return": 1.8,
  "portfolio_allocation": {
    "BTC": 25.5,
    "ETH": 24.1,
    "SOL": 28.9,
    "XRP": 19.2,
    "KRW": 2.3
  },
  "market_summary": {
    "market_condition": "neutral",
    "fear_greed_index": 45,
    "total_portfolio_change": 1.8
  },
  "ai_cost_today": 850
}
```

## 🚀 사용법

### 1. 실제 투자 실행 (로깅 활성화)
```bash
# 상세 로깅과 함께 실제 투자 시작
python mvp.py

# 출력 예시:
# 🚀 실제 거래 모드 - 상세 데이터 수집 활성화
# 📊 실제 투자 데이터 수집 시작:
#   - 거래 로그: trades_20240115.json
#   - AI 신호 로그: ai_signals_20240115.json
#   - 성과 로그: performance_20240115.json
```

### 2. 실시간 모니터링
```bash
# 실시간 대시보드 실행
python monitor.py

# 30초마다 자동 업데이트되는 실시간 현황:
# - 포트폴리오 가치 및 수익률
# - 최근 거래 내역
# - AI 신호 추적
# - 알림 및 경고
```

### 3. 일일 데이터 분석
```bash
# 오늘 데이터 분석
python log_analyzer.py

# 특정 날짜 분석
python log_analyzer.py 20240115

# 분석 내용:
# - 거래 통계 (코인별, 신뢰도별)
# - AI 신호 성과 분석
# - 포트폴리오 성과 추적
# - 비용 효율성 분석
# - 차트 및 시각화
```

## 📊 분석 기능

### 1. 거래 분석
- **코인별 거래 현황**: 거래 횟수, 총 거래금액, 잔고 변화
- **매수/매도 분석**: 액션별 통계 및 평균 거래금액
- **신뢰도별 성과**: AI 신뢰도 구간별 거래 성과 분석

### 2. AI 신호 분석
- **신호 분포**: STRONG_BUY, BUY, HOLD, SELL 비율
- **코인별 신호 패턴**: 각 코인의 신호 경향 분석
- **신뢰도 통계**: 신호별 평균 신뢰도 및 표준편차
- **비용 분석**: 총 AI 사용 비용 및 효율성

### 3. 성과 분석
- **포트폴리오 가치 변화**: 시작 대비 현재 가치 및 수익률
- **일일 수익률 통계**: 평균, 표준편차, 최대/최소값
- **AI 비용 효율성**: 포트폴리오 대비 AI 비용 비율

### 4. 시각화
- 코인별 거래 횟수 차트
- AI 신호 분포 파이차트
- 시간별 거래 패턴
- 포트폴리오 가치 변화 추이

## 💡 전략 개선 활용법

### 1. 성과 분석 기반 개선
```python
# 예시: 높은 신뢰도 거래의 성과가 좋다면
if high_confidence_trades_profitable:
    # config.json에서 최소 신뢰도 임계값 상향 조정
    "min_confidence_threshold": 0.8  # 0.7 -> 0.8
```

### 2. AI 비용 최적화
```python
# 예시: AI 비용이 과도하다면
if daily_ai_cost > target_cost:
    # 체크 주기 연장으로 비용 절약
    "cost_efficient_mode": True,
    "min_check_interval": 8  # 시간 단위
```

### 3. 시장 조건별 전략 조정
```python
# 예시: 특정 시장 조건에서 성과가 좋다면
if market_condition == "bullish" and performance > average:
    # 불장에서 더 적극적인 거래
    "bullish_multiplier": 1.3
```

## 🔧 고급 설정

### 1. 로그 파일 관리
```bash
# 오래된 로그 파일 정리 (30일 이상)
find . -name "*.json" -mtime +30 -delete

# 로그 파일 압축 보관
tar -czf logs_$(date +%Y%m).tar.gz *_$(date +%Y%m)*.json
```

### 2. 백업 및 복원
```bash
# 중요 로그 파일 백업
cp trades_*.json signals_*.json performance_*.json ./backup/

# 클라우드 동기화 (선택적)
# rsync -av *.json user@server:/backup/trading_logs/
```

### 3. 알림 설정 (추가 구현 가능)
```python
# 큰 손실 시 알림
if daily_loss > 50000:  # 5만원 이상 손실
    send_telegram_alert(f"큰 손실 발생: {daily_loss:,}원")

# AI 비용 과다 사용 알림
if daily_ai_cost > 5000:  # 일일 5천원 초과
    send_telegram_alert(f"AI 비용 주의: {daily_ai_cost:,}원")
```

## 📝 주의사항

1. **디스크 공간**: 로그 파일이 계속 누적되므로 정기적으로 정리 필요
2. **개인정보**: 로그 파일에 API 키 등 민감한 정보가 포함되지 않도록 주의
3. **백업**: 중요한 거래 데이터이므로 정기적인 백업 권장
4. **분석 주기**: 최소 일주일 데이터 누적 후 의미있는 분석 가능

## 🎯 기대 효과

1. **데이터 기반 의사결정**: 감정이 아닌 실제 데이터로 전략 개선
2. **비용 최적화**: AI 사용 패턴 분석으로 비용 효율성 극대화
3. **성과 추적**: 정확한 수익률 계산 및 벤치마크 비교
4. **리스크 관리**: 손실 패턴 분석으로 리스크 요소 조기 발견
5. **전략 진화**: 지속적인 학습과 개선으로 수익성 향상

---

**💪 실제 투자에서 발생하는 모든 데이터를 활용하여 더 스마트한 트레이딩 전략을 구축하세요!**