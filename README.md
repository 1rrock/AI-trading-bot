# 🚀 AI Multi-Coin Portfolio Trading Bot

공격적 성장 전략을 위한 다중 암호화폐 포트폴리오 자동매매 시스템

## 📊 투자 전략

### 🔹 공격적 포트폴리오 구성 (현재 잔고 기준)
- **BTC**: 25% - 안정성의 기준
- **ETH**: 25% - DeFi 생태계 대표
- **XRP**: 20% - 실용성 중심 결제 코인
- **SOL**: 15% - 고성능 블록체인
- **MATIC**: 15% - Layer 2 확장성

> 💡 **동적 금액 계산**: 하드코딩된 금액 대신 현재 업비트 잔고를 기준으로 각 코인별 목표 금액을 자동 계산합니다.

### 💡 핵심 전략
1. **DCA (Dollar Cost Averaging)**: 3개월에 걸쳐 12회 분할 매수
2. **리밸런싱**: 3개월마다 포트폴리오 비중 재조정
3. **KPI 목표**:
   - 30일: BTC 대비 -10% 이내 유지
   - 90일: 시장 대비 +5~10% 초과 성과

### 🎯 장점 & 리스크
**👍 장점**: 알트코인 급등 시 높은 수익률 가능  
**⚠️ 리스크**: 큰 조정 시 손실 확대 가능성

## 🐳 Docker로 실행하기 (권장)

### 1. 환경 설정
```bash
# .env 파일 생성
cp .env.example .env
# .env 파일을 편집하여 Upbit API 키 입력
```

### 2. Docker Compose로 실행
```bash
# 포트폴리오 봇 실행
docker-compose up -d

# 실시간 로그 확인
docker-compose logs -f bitcoin-trading-bot

# 봇 중지
docker-compose down
```

## 🖥️ 로컬 Python으로 실행하기

### 환경 요구사항
- Python 3.9 이상
- Upbit API 키 (KRW 마켓 거래 가능)
- OpenAI API 키

### 설치 및 실행
```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
export UPBIT_ACCESS_KEY="your_upbit_access_key"
export UPBIT_SECRET_KEY="your_upbit_secret_key"
export OPENAI_API_KEY="your_openai_api_key"

# 포트폴리오 봇 실행
python mvp.py
```

## 📈 모니터링 & 로그

### DCA 진행 상태
- `dca_state.json`: DCA 분할 매수 진행 현황
- 주 1회 자동 실행, 총 12회 완료 시 DCA 종료

### 리밸런싱 알림
- 3개월마다 자동 실행
- 5% 이상 비중 차이 발생 시 리밸런싱 수행

### KPI 추적
- 30일/90일 성과 실시간 모니터링
- BTC 대비 성과 및 절대 수익률 추적

## ⚙️ 설정 커스터마이징

### 포트폴리오 비중 수정
```python
# mvp.py 파일에서 수정 가능
PORTFOLIO_CONFIG = {
    "BTC": {"weight": 0.25, "symbol": "KRW-BTC"},
    "ETH": {"weight": 0.25, "symbol": "KRW-ETH"},
    # ... 비중 조정 가능 (금액은 현재 잔고 기준 자동 계산)
}
```

### DCA 주기 조정
```python
DCA_CONFIG = {
    "duration_months": 3,        # 총 기간
    "intervals_per_month": 4,    # 월 실행 횟수
    "total_intervals": 12        # 총 분할 횟수
}
```
```bash
pip3 install -r requirements.txt
```

### 환경 변수 설정
Upbit API 키를 .env 파일에 아래와 같이 작성하세요:
```
UPBIT_ACCESS_KEY=여기에_액세스키
UPBIT_SECRET_KEY=여기에_시크릿키
OPENAI_API_KEY=여기에_OpenAI_API키
```

### 실행 방법
```bash
python mvp.py
```

## 📊 로깅 및 모니터링

### 생성되는 로그 파일들
- `trading_log.md`: 마크다운 형식의 거래 기록
- `trading_log.json`: JSON 형식의 상세 거래 데이터
- `news_cache.json`: 뉴스 캐시 (4시간)
- `ai_decision_cache.json`: AI 결정 캐시 (45분)

### Docker 볼륨 마운트
Docker 실행 시 로그 파일들이 호스트의 `./logs` 디렉토리와 프로젝트 루트에 저장됩니다.

## ⚡ 최적화 기능

### 스마트 결정 시스템
- **규칙 기반 필터링**: 과매수/과매도 등 명확한 상황에서 AI 호출 없이 결정
- **45분 AI 캐싱**: AI 결정을 45분간 재사용하여 API 호출 최소화
- **시장 변화 감지**: 중요한 변화가 있을 때만 새로운 AI 호출
- **뉴스 캐싱**: 4시간 동안 뉴스 데이터 캐싱

### API 호출 최적화
- 하루 약 10-20회 OpenAI API 호출 (기존 96회 → 80% 절약)
- 200회 제한으로 약 10-20일간 운영 가능

## 주요 파일 설명
- `mvp.py`: 자동매매 및 AI 판단 메인 코드
- `requirements.txt`: 필요 패키지 목록
- `test.py`: 테스트 코드(선택)

## 주의사항
- 실제 거래가 발생하므로 소액으로 테스트 후 사용하세요.
- OpenAI API 사용 시 요금이 발생할 수 있습니다.

## 문의
- 개선/문의: GitHub Issues 또는 이메일로 연락 바랍니다.

