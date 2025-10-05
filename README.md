# 🤖 AI Trading Bot

OpenAI GPT-4를 활용한 암호화폐 자동매매 봇

## 📊 핵심 기능

### 투자 전략
- **AI 기반 의사결정**: GPT-4o-mini를 활용한 실시간 시장 분석
- **리스크 관리**: 
  - 손절매: -15%
  - 최소 AI 신뢰도: 70%
  - 단일 코인 최대 비중: 35%
- **다중 안전장치**:
  - 부분매도 쿨다운: 6시간
  - 일별 매도 제한: 1회/코인 (손절매/고신뢰도 예외)
  - 리밸런싱 쿨다운: 2시간
  - 연속 매수 제한: 3-6회

### 지원 코인
- BTC, ETH, XRP, SOL (config.json에서 설정 가능)

## � 빠른 시작

### 1. 환경 설정
```bash
# 환경 변수 파일 생성
cp .env.example .env
```

`.env` 파일에 API 키 입력:
```env
UPBIT_ACCESS_KEY=여기에_액세스키
UPBIT_SECRET_KEY=여기에_시크릿키
OPENAI_API_KEY=여기에_OpenAI_API키
```

### 2. 의존성 설치
```bash
pip3 install -r requirements.txt
```

### 3. 실행
```bash
# 새로운 테스트 시작 (이전 로그 백업)
sh start_fresh_test.sh

# 또는 바로 실행
python mvp.py
```

## 📊 로깅 및 모니터링

### 생성되는 로그 파일들 (`log/` 폴더)
- `trading_bot_YYYYMMDD.log`: 일별 거래 로그 + **의사결정 상세 기록**
- `trades_YYYYMMDD.json`: 거래 데이터
- `ai_signals_YYYYMMDD.json`: AI 신호 기록
- `performance_YYYYMMDD.json`: 성과 추적

### 로그 분석 명령어
```bash
# 모든 의사결정 확인
grep "의사결정" log/trading_bot_*.log

# 거부된 매수 확인
grep "결과: ❌ 거부" log/trading_bot_*.log | grep "BUY"

# 특정 코인 추적
grep "의사결정: BTC" log/trading_bot_*.log

# 쿨다운 작동 확인
grep "쿨다운" log/trading_bot_*.log
```

### 의사결정 로그 예시
```
===== BUY 의사결정: SOL =====
결과: ❌ 거부
이유: 비중 초과 (리밸런싱 악순환 방지)
컨텍스트: {
  "current_allocation": "33.0%",
  "threshold": "28%",
  "confidence": "78%",
  "signal": "BUY"
}
============================================================
```

## ⚙️ 설정 커스터마이징

### `config.json` 주요 설정
```json
{
  "trading_constraints": {
    "base_trade_ratio": 0.15,           // 기본 거래 비율 15%
    "max_single_coin_ratio": 0.35,      // 최대 코인 비중 35%
    "min_cash_ratio": 0.15              // 최소 현금 비율 15%
  },
  "safety_thresholds": {
    "stop_loss_threshold": 0.15,        // 손절매 -15%
    "min_ai_confidence": 0.70,          // 최소 AI 신뢰도 70%
    "rsi_overbought": 75,               // RSI 과매수 기준
    "rsi_oversold": 25                  // RSI 과매도 기준
  }
}
```

## 🛠️ 유틸리티 스크립트

### `start_fresh_test.sh`
- 이전 로그 자동 백업 (`backup/before_TIMESTAMP/`)
- log/ 폴더 정리
- 깨끗한 상태로 봇 시작

### `move_logs_to_folder.sh`
- 루트 폴더의 로그 파일들을 `log/` 폴더로 이동

## ⚡ 최적화 기능

### AI 호출 최적화
- **뉴스 캐싱**: 4시간 (비용 절감)
- **RSI 기반 필터링**: 극단적 상황에서 AI 호출 생략
- **하루 약 10-20회** OpenAI API 호출

### 악순환 방지 로직
- **리밸런싱 루프 방지**: 매수 → 리밸런싱 → 매수 반복 차단
- **비중 기반 매수 제한**: 28% 이상 시 추가 매수 제한
- **강제 매수 모드**: 현금 비율 40% 초과 시 자동 활성화

## 주요 파일 설명
- `mvp.py`: 자동매매 및 AI 판단 메인 코드
- `requirements.txt`: 필요 패키지 목록
- `test.py`: 테스트 코드(선택)

## 주의사항
- 실제 거래가 발생하므로 소액으로 테스트 후 사용하세요.
- OpenAI API 사용 시 요금이 발생할 수 있습니다.

## 문의
- 개선/문의: GitHub Issues 또는 이메일로 연락 바랍니다.

