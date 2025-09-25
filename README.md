# gptbitcoin

비트코인 자동매매 및 AI 투자 판단 시스템

## 🐳 Docker로 실행하기 (권장)

### 1. 환경 설정
```bash
# .env 파일 생성
cp .env.example .env
# .env 파일을 편집하여 API 키 입력
```

### 2. Docker Compose로 실행
```bash
# 백그라운드에서 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f bitcoin-trading-bot

# 중지
docker-compose down
```

### 3. 로그 모니터링 (선택사항)
```bash
# 웹 로그 뷰어와 함께 실행
docker-compose --profile monitoring up -d

# 브라우저에서 http://localhost:8080 으로 로그 확인 가능
```

### 4. 컨테이너 상태 확인
```bash
# 실행 중인 컨테이너 확인
docker ps

# 헬스체크 상태 확인
docker-compose ps
```

## 🖥️ 로컬 Python으로 실행하기

### Python 버전
- Python 3.9 이상 권장

### 필수 라이브러리 설치
아래 명령어로 필요한 패키지를 설치하세요:
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

