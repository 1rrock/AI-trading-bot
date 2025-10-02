# 📁 프로젝트 구조

## 🏗️ 현재 폴더 구조

```
📁 AI-trading-bot/
├── 📄 README.md (메인 프로젝트 설명)
├── 📄 mvp.py (보수적 AI 트레이딩 봇)
├── 📄 config.json (보수적 봇 설정)
├── 📄 compare_results.py (봇 성과 비교 도구)
├── 📄 monitor.py (시스템 모니터링)
├── 📄 log_analyzer.py (로그 분석 도구)
├── 📄 requirements.txt (Python 패키지 목록)
├── 📄 .env (API 키 등 환경변수)
│
├── 📁 contrarian_bot/ (🆕 컨트래리언 봇 전용 폴더)
│   ├── 📄 contrarian_bot.py (컨트래리언 AI 트레이딩 봇)
│   ├── 📄 config_contrarian.json (공격적 거래 설정)
│   ├── 📄 README_contrarian.md (컨트래리언 봇 가이드)
│   ├── 📄 contrarian_bot_analysis.md (전략 분석 보고서)
│   ├── 📄 contrarian_trades_YYYYMMDD.json (거래 로그)
│   ├── 📄 contrarian_ai_signals_YYYYMMDD.json (AI 신호)
│   └── 📄 contrarian_performance_YYYYMMDD.json (성과 추적)
│
├── 📁 backup/ (백업 파일들)
│   └── 📁 20251001_before_optimization/
│       ├── 📄 config_before_optimization.json
│       ├── 📄 trades_20251001_backup.json
│       └── ...
│
├── 📄 trades_YYYYMMDD.json (보수적 봇 거래 로그)
├── 📄 ai_signals_YYYYMMDD.json (보수적 봇 AI 신호)
├── 📄 performance_YYYYMMDD.json (보수적 봇 성과)
├── 📄 trading_bot_YYYYMMDD.log (시스템 로그)
└── 📄 news_cache.json (뉴스 캐시)
```

## 🚀 봇 실행 방법

### 🛡️ 보수적 봇 (루트 폴더에서)
```bash
python mvp.py
```

### ⚡ 컨트래리언 봇 (contrarian_bot 폴더에서)
```bash
cd contrarian_bot
python contrarian_bot.py
```

### 📊 성과 비교 (루트 폴더에서)
```bash
python compare_results.py
```

## 📋 봇 별 특징 비교

| 항목 | 보수적 봇 | 컨트래리언 봇 |
|------|-----------|---------------|
| **전략** | 추세 추종 | 역추세 매매 |
| **기본 거래비율** | 15% | 30% |
| **최대 집중도** | 35% | 70% |
| **최소 현금** | 15% | 5% |
| **체크 주기** | 60분 | 30분 |
| **신뢰도 기준** | 70% | 40% |
| **로그 위치** | 루트 폴더 | contrarian_bot/ |

## 🔄 데이터 분리 원칙

### 파일명 규칙
- **보수적 봇**: `파일명_YYYYMMDD.json`
- **컨트래리언 봇**: `contrarian_파일명_YYYYMMDD.json`

### 폴더 분리 이유
1. **명확한 구분**: 두 전략의 파일들이 섞이지 않음
2. **독립적 실행**: 각각 독립적으로 실행 가능
3. **쉬운 관리**: contrarian_bot 폴더만 백업/삭제 가능
4. **확장성**: 향후 다른 전략 봇도 별도 폴더로 관리

## 📈 로그 파일 설명

### 보수적 봇 로그 (루트 폴더)
- `trades_20251002.json` - 실제 거래 내역
- `ai_signals_20251002.json` - AI 분석 신호
- `performance_20251002.json` - 수익률 추적

### 컨트래리언 봇 로그 (contrarian_bot 폴더)
- `contrarian_trades_20251002.json` - 컨트래리언 거래 내역
- `contrarian_ai_signals_20251002.json` - 역추세 AI 신호
- `contrarian_performance_20251002.json` - 공격적 전략 성과

## 🎯 폴더 정리 완료

✅ **정리 내용**:
1. 컨트래리언 봇 관련 파일들을 `contrarian_bot/` 폴더로 이동
2. 로그 파일 경로를 폴더 내부로 수정
3. 비교 도구에서 새로운 경로 인식하도록 업데이트
4. 실행 방법을 폴더 구조에 맞게 수정

이제 프로젝트가 **깔끔하게 정리**되어 두 봇을 독립적으로 실행하고 관리할 수 있습니다! 🎉