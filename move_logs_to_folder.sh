#!/bin/bash

# log 폴더 생성
mkdir -p log

# 기존 로그 파일들을 log 폴더로 이동
echo "📦 기존 로그 파일들을 log/ 폴더로 이동합니다..."

# .log 파일들
if ls trading_bot_*.log 1> /dev/null 2>&1; then
    mv trading_bot_*.log log/
    echo "✅ trading_bot_*.log 이동 완료"
fi

# trades JSON 파일들
if ls trades_*.json 1> /dev/null 2>&1; then
    mv trades_*.json log/
    echo "✅ trades_*.json 이동 완료"
fi

# ai_signals JSON 파일들
if ls ai_signals_*.json 1> /dev/null 2>&1; then
    mv ai_signals_*.json log/
    echo "✅ ai_signals_*.json 이동 완료"
fi

# performance JSON 파일들
if ls performance_*.json 1> /dev/null 2>&1; then
    mv performance_*.json log/
    echo "✅ performance_*.json 이동 완료"
fi

echo ""
echo "✨ 완료! 모든 로그가 log/ 폴더에 정리되었습니다."
echo ""
echo "📁 log/ 폴더 내용:"
ls -lh log/
