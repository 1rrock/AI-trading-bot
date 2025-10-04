#!/bin/bash

# 🔄 AI Trading Bot - 새로운 테스트 시작 스크립트
# 이전 로그/데이터를 백업하고 깨끗한 상태에서 시작합니다.

echo "🚀 AI Trading Bot - 새로운 테스트 시작"
echo "========================================="
echo ""

# 현재 날짜 및 시간
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="backup/before_${TIMESTAMP}"

echo "📦 1. 이전 데이터 백업 중..."
echo "   백업 위치: ${BACKUP_DIR}"

# 백업 디렉토리 생성
mkdir -p "${BACKUP_DIR}"

# 백업할 파일들 (있는 경우에만)
if ls *.log 1> /dev/null 2>&1; then
    echo "   - 로그 파일 백업 중..."
    mv *.log "${BACKUP_DIR}/" 2>/dev/null || true
fi

if ls ai_signals_*.json 1> /dev/null 2>&1; then
    echo "   - AI 신호 파일 백업 중..."
    mv ai_signals_*.json "${BACKUP_DIR}/" 2>/dev/null || true
fi

if ls performance_*.json 1> /dev/null 2>&1; then
    echo "   - 성과 파일 백업 중..."
    mv performance_*.json "${BACKUP_DIR}/" 2>/dev/null || true
fi

if ls trades_*.json 1> /dev/null 2>&1; then
    echo "   - 거래 파일 백업 중..."
    mv trades_*.json "${BACKUP_DIR}/" 2>/dev/null || true
fi

if [ -f news_cache.json ]; then
    echo "   - 뉴스 캐시 백업 중..."
    mv news_cache.json "${BACKUP_DIR}/" 2>/dev/null || true
fi

echo ""
echo "✅ 백업 완료!"
echo ""

# 백업된 파일 수 확인
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}" 2>/dev/null | wc -l)
echo "   총 ${BACKUP_COUNT}개 파일이 백업되었습니다."
echo ""

# 현재 설정 확인
echo "⚙️  2. 현재 설정 확인..."
echo ""

if [ -f config.json ]; then
    echo "   config.json 주요 설정:"
    echo "   -----------------------"
    python3 << 'EOF'
import json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    print(f"   기본 거래 비율: {config.get('trading_constraints', {}).get('base_trade_ratio', 'N/A')}")
    print(f"   최대 코인 비중: {config.get('trading_constraints', {}).get('max_single_coin_ratio', 'N/A')}")
    print(f"   손절 임계값: {config.get('safety_thresholds', {}).get('stop_loss_threshold', 'N/A')}")
    print(f"   최소 AI 신뢰도: {config.get('safety_thresholds', {}).get('min_ai_confidence', 'N/A')}")
except Exception as e:
    print(f"   ⚠️  설정 파일 읽기 실패: {e}")
EOF
else
    echo "   ⚠️  config.json 파일이 없습니다!"
fi

echo ""
echo "🔍 3. Python 환경 확인..."

# 가상환경 활성화 여부 확인
if [ -d ".venv" ]; then
    echo "   ✅ 가상환경 발견: .venv"
    if [[ "$VIRTUAL_ENV" == *".venv"* ]]; then
        echo "   ✅ 가상환경 활성화됨"
    else
        echo "   ⚠️  가상환경이 활성화되지 않았습니다."
        echo "   실행: source .venv/bin/activate"
    fi
else
    echo "   ⚠️  가상환경이 없습니다. 생성하시겠습니까?"
fi

echo ""
echo "📊 4. 최종 확인..."
echo ""
echo "   백업 위치: ${BACKUP_DIR}"
echo "   새 테스트 시작 준비 완료!"
echo ""
echo "========================================="
echo "🎯 봇을 실행하려면 다음 명령어를 입력하세요:"
echo ""
echo "   python3 mvp.py"
echo ""
echo "또는 가상환경 활성화 후:"
echo ""
echo "   source .venv/bin/activate"
echo "   python mvp.py"
echo ""
echo "========================================="
echo ""
echo "💡 팁:"
echo "   - 로그는 실시간으로 trading_bot_YYYYMMDD.log에 기록됩니다"
echo "   - Ctrl+C로 안전하게 중단할 수 있습니다"
echo "   - 이전 데이터는 ${BACKUP_DIR}에 보관됩니다"
echo ""
