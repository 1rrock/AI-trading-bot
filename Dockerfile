# Python 3.11 slim 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일들 복사
COPY mvp.py .

# 로그 파일들을 위한 디렉토리 생성
RUN mkdir -p /app/logs

# 환경변수 설정 (기본값, docker-compose에서 오버라이드 가능)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 애플리케이션 실행
CMD ["python", "mvp.py"]