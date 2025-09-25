#!/bin/bash

# Bitcoin Trading Bot 실행 스크립트

echo "🤖 Bitcoin Trading Bot Docker Setup"
echo "=================================="

# .env 파일 확인
if [ ! -f .env ]; then
    echo "⚠️  .env 파일이 없습니다. .env.example을 복사합니다..."
    cp .env.example .env
    echo "✅ .env 파일이 생성되었습니다. API 키를 입력해주세요."
    echo "📝 편집 명령어: nano .env"
    exit 1
fi

# logs 디렉토리 생성
mkdir -p logs

echo "🐳 Docker 컨테이너를 시작합니다..."

# Docker Compose 실행
if [ "$1" = "monitoring" ]; then
    echo "📊 로그 모니터링과 함께 실행합니다 (http://localhost:8080)"
    docker-compose --profile monitoring up -d
else
    docker-compose up -d
fi

echo ""
echo "🚀 봇이 실행되었습니다!"
echo ""
echo "📋 유용한 명령어들:"
echo "  docker-compose logs -f bitcoin-trading-bot  # 실시간 로그 보기"
echo "  docker-compose ps                           # 컨테이너 상태 확인"  
echo "  docker-compose down                         # 봇 중지"
echo "  ./run.sh monitoring                         # 모니터링과 함께 실행"
echo ""
echo "📊 로그 파일들:"
echo "  ./trading_log.md      # 마크다운 거래 로그"
echo "  ./logs/               # 기타 로그 파일들"

if [ "$1" = "monitoring" ]; then
    echo ""
    echo "🌐 웹 로그 뷰어: http://localhost:8080"
fi