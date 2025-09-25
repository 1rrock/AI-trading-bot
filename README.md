# gptbitcoin

비트코인 자동매매 및 AI 투자 판단 시스템

## Python 버전
- Python 3.9 이상 권장

## 필수 라이브러리 설치
아래 명령어로 필요한 패키지를 설치하세요:
```bash
pip3 install -r requirements.txt
```

## 환경 변수 설정
Upbit API 키를 .env 파일에 아래와 같이 작성하세요:
```
UPBIT_ACCESS_KEY=여기에_액세스키
UPBIT_SECRET_KEY=여기에_시크릿키
OPENAI_API_KEY=여기에_OpenAI_API키
```

## 실행 방법
```bash
python mvp.py
```

## 주요 파일 설명
- `mvp.py`: 자동매매 및 AI 판단 메인 코드
- `requirements.txt`: 필요 패키지 목록
- `test.py`: 테스트 코드(선택)

## 주의사항
- 실제 거래가 발생하므로 소액으로 테스트 후 사용하세요.
- OpenAI API 사용 시 요금이 발생할 수 있습니다.

## 문의
- 개선/문의: GitHub Issues 또는 이메일로 연락 바랍니다.

