# 🔧 AI 트레이딩 봇 설정 가이드

## 📋 개요
이 문서는 `config.json` 파일의 각 설정값에 대한 상세한 설명을 제공합니다.

## 🚀 주요 설정 카테### 7. 체크 주기 설정 (check_intervals)
```json
{
  "extreme_volatility_threshold": 8.0,
  "extreme_volatility_interval": 15,
  "high_volatility_threshold": 5.0,
  "high_volatility_interval": 30,
  "medium_volatility_threshold": 2.0,
  "medium_volatility_interval": 60,
  "low_volatility_interval": 120,
  "default_interval": 60
}
```

**주요 포인트:**
- **동적 체크 주기**: 시장 변동성에 따라 자동으로 체크 간격 조정
- **극고변동성**(8% 이상): 15분 간격으로 빠른 대응
- **고변동성**(5% 이상): 30분 간격
- **중변동성**(2% 이상): 60분 간격  
- **저변동성**(2% 미만): 120분 간격으로 효율적 운영

### 🔄 실시간 설정 변경

### 설정 재로드
- 봇은 **매 10사이클마다** 자동으로 `config.json`을 재로드
- 파일 수정 후 최대 10사이클 내 자동 반영
- 재시작 없이 실시간 파라미터 조정 가능# 1. 거래 설정 (trading)
```json
{
  "base_trade_ratio": 0.15,           // 기본 거래 비율 (15%)
  "stop_loss_percent": 15,            // 손절매 기준 (15% 손실)
  "min_trade_amount": 5000,           // 최소 거래 금액 (5,000원)
  "max_position_multiplier": 1.5      // 최대 포지션 배수 (고신뢰도 시)
}
```

**주요 포인트:**
- `base_trade_ratio`: 포트폴리오 대비 한 번에 거래할 비율
- GPT-4o-mini 모델로 더 적극적인 15% 거래
- 고신뢰도 AI 신호 시 1.5배까지 확대 매수 가능

### 2. 기술적 분석 (technical_analysis)
```json
{
  "rsi_oversold": 30,                 // RSI 과매도 기준
  "rsi_overbought": 70,               // RSI 과매수 기준
  "data_period_days": 30              // 분석 데이터 기간
}
```

**주요 포인트:**
- RSI 30 이하: 과매도 → 매수 시그널
- RSI 70 이상: 과매수 → 매도 시그널
- 30일치 차트 데이터로 분석

### 3. 시장 상황 감지 (market_conditions)
```json
{
  "bull_market_threshold": 10,        // 강세장 기준 (+10%)
  "bear_market_threshold": -10,       // 약세장 기준 (-10%)
  "fear_greed_extreme_fear": 25,      // 극단적 공포 기준
  "fear_greed_extreme_greed": 75      // 극단적 탐욕 기준
}
```

**주요 포인트:**
- 시장 상황에 따라 거래 전략 자동 조정
- 공포탐욕지수 연동으로 심리적 요인 반영

### 4. 리스크 관리 (risk_management)
```json
{
  "bull_market_multiplier": 1.2,      // 강세장 시 거래량 증가
  "bear_market_multiplier": 0.6,      // 약세장 시 거래량 감소
  "high_volatility_multiplier": 0.5   // 고변동성 시 거래량 대폭 감소
}
```

**주요 포인트:**
- 시장 상황별 자동 포지션 크기 조정
- 리스크 최소화를 위한 동적 승수 적용

### 5. 거래 대상 코인 (coins)
```json
{
  "list": ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP"],
  "target_allocation": {
    "KRW-BTC": 0.25,
    "KRW-ETH": 0.25,
    "KRW-SOL": 0.30,
    "KRW-XRP": 0.20
  },
  "allocation_desc": "BTC(25%), ETH(25%), SOL(30%), XRP(20%) 목표 비중"
}
```

**주요 포인트:**
- 4개 주요 코인으로 포트폴리오 구성
- 솔라나(SOL) 30% 최대 비중으로 공격적 배치
- **자동 리밸런싱**: 매 20사이클마다 목표 비율 대비 15% 이상 편차 시 자동 조정
- 구조화된 비율 데이터로 코드에서 직접 활용 가능

### 6. 안전장치 (safety)
```json
{
  "min_cash_ratio": 0.15,             // 최소 현금 비율 (15%)
  "max_portfolio_concentration": 0.45  // 최대 포트폴리오 집중도 (45%)
}
```

**주요 포인트:**
- 현금 15% 미만 시 자동 매도로 유동성 확보
- 단일 코인 45% 초과 시 자동 리밸런싱
- 과도한 집중 투자 방지

## 🔄 실시간 설정 변경

### 설정 재로드
- 봇은 **매 10사이클마다** 자동으로 `config.json`을 재로드
- 파일 수정 후 최대 10사이클(약 2.5-20시간) 내 자동 반영
- 재시작 없이 실시간 파라미터 조정 가능

### 🎯 자동 포트폴리오 리밸런싱
- **실행 주기**: 매 20사이클마다 자동 실행
- **편차 기준**: 목표 비율 대비 15% 이상 편차 시 실행
- **리밸런싱 순서**: 
  1. 과보유 코인 매도 (목표 비율까지)
  2. 매도 수익금으로 부족한 코인 매수
- **예시**: SOL이 45%까지 상승 시 (목표 30%) → 15% 분량 자동 매도

### 권장 설정 변경 시나리오

#### 🐂 강세장 대응
```json
{
  "base_trade_ratio": 0.20,           // 거래 비율 증가
  "rsi_oversold": 35,                 // 과매도 기준 상향
  "min_cash_ratio": 0.10              // 현금 비율 축소
}
```

#### 🐻 약세장 대응
```json
{
  "base_trade_ratio": 0.10,           // 거래 비율 감소
  "stop_loss_percent": 10,            // 손절매 더 엄격하게
  "min_cash_ratio": 0.25              // 현금 비율 확대
}
```

#### 📈 고변동성 대응
```json
{
  "base_trade_ratio": 0.08,           // 거래 비율 대폭 감소
  "stop_loss_percent": 8,             // 빠른 손절매
  "high_volatility_multiplier": 0.3,  // 거래량 더욱 축소
  "extreme_volatility_interval": 10,  // 체크 주기 더 빠르게 (10분)
  "high_volatility_interval": 20      // 고변동성 체크 주기 단축 (20분)
}
```

#### ⚡ 초고속 트레이딩 모드
```json
{
  "extreme_volatility_interval": 5,   // 극고변동성 시 5분 간격
  "high_volatility_interval": 15,     // 고변동성 시 15분 간격
  "medium_volatility_interval": 30,   // 중변동성 시 30분 간격
  "base_trade_ratio": 0.20            // 거래 비율 증가로 공격적 매매
}
```

#### 🐌 안전 운영 모드
```json
{
  "extreme_volatility_interval": 30,  // 극고변동성도 30분 간격
  "high_volatility_interval": 60,     // 고변동성 시 60분 간격
  "low_volatility_interval": 240,     // 저변동성 시 4시간 간격
  "base_trade_ratio": 0.08            // 거래 비율 축소로 안전 운영
}
```

## ⚠️ 주의사항

### 설정 변경 시 고려사항
1. **거래 비율**: 너무 높으면 리스크 증가, 너무 낮으면 수익 기회 상실
2. **손절매**: 너무 낮으면 잦은 손절, 너무 높으면 큰 손실 위험
3. **안전장치**: 현금 비율과 집중도 제한은 리스크 관리의 핵심

### 백업 권장
- 설정 변경 전 현재 `config.json` 백업
- 중요한 실험 시에는 소액으로 먼저 테스트

## 📊 성과 모니터링

### 로그 파일 확인
- `trading_bot_*.log`: 일반 로그
- `trades_*.json`: 거래 내역
- `ai_signals_*.json`: AI 신호 데이터
- `performance_*.json`: 성과 데이터

### 분석 도구
```bash
python3 log_analyzer.py  # 로그 분석 및 성과 리포트
```

---

💡 **팁**: 설정 변경 후에는 로그를 주의 깊게 모니터링하여 의도한 대로 동작하는지 확인하세요!