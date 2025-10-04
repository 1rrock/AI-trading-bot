# 🧪 AI Trading Bot 테스트 가이드

## 📋 새로운 테스트 시작하기

### 방법 1: 자동 백업 스크립트 사용 (추천) ⭐

```bash
# 이전 로그 자동 백업 + 깨끗한 상태로 시작
./start_fresh_test.sh

# 봇 실행
python3 mvp.py
```

**장점:**
- ✅ 이전 데이터 자동 백업 (`backup/before_TIMESTAMP/`)
- ✅ 설정 자동 확인
- ✅ 안전하고 편리함

---

### 방법 2: 수동으로 백업 및 삭제

```bash
# 1. 현재 날짜로 백업 디렉토리 생성
mkdir -p backup/manual_$(date +%Y%m%d_%H%M%S)

# 2. 이전 데이터 백업
mv *.log backup/manual_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
mv ai_signals_*.json backup/manual_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
mv performance_*.json backup/manual_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
mv trades_*.json backup/manual_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
mv news_cache.json backup/manual_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true

# 3. 봇 실행
python3 mvp.py
```

---

### 방법 3: 백업 없이 바로 삭제 (⚠️ 주의)

```bash
# 모든 로그 및 데이터 삭제 (복구 불가!)
rm -f *.log ai_signals_*.json performance_*.json trades_*.json news_cache.json

# 봇 실행
python3 mvp.py
```

⚠️ **경고**: 이전 데이터를 영구 삭제합니다!

---

## 🎯 테스트 시나리오별 가이드

### 1️⃣ 단기 테스트 (1-2시간)

**목적**: 새로운 로직 검증

```bash
# 백업 후 시작
./start_fresh_test.sh

# 봇 실행 (1-2시간 모니터링)
python3 mvp.py

# Ctrl+C로 중단 후 로그 확인
tail -100 trading_bot_*.log
```

**확인 사항:**
- ✅ RSI 70-75 구간에서 매도 제한되는지
- ✅ 거래량 검증이 작동하는지
- ✅ 부분 매도가 실행되는지

---

### 2️⃣ 중기 테스트 (1-3일)

**목적**: 실전 성능 검증

```bash
# 백업 후 시작
./start_fresh_test.sh

# 백그라운드 실행
nohup python3 mvp.py > bot_output.log 2>&1 &

# 프로세스 확인
ps aux | grep mvp.py

# 실시간 로그 모니터링
tail -f trading_bot_*.log
```

**확인 사항:**
- ✅ 상승장에서 조기 매도 안하는지
- ✅ 하락장에서 빠르게 대응하는지
- ✅ AI 비용이 예상 범위 내인지

---

### 3️⃣ 성과 비교 테스트

**목적**: 이전 버전 vs 새 버전 비교

```bash
# 이전 성과 데이터 확인
cat backup/before_*/performance_*.json | tail -5

# 새 테스트 시작
./start_fresh_test.sh
python3 mvp.py

# 새 성과 확인
cat performance_*.json | tail -5
```

---

## 📊 로그 분석 명령어

### 실시간 모니터링
```bash
# 최신 로그 실시간 확인
tail -f trading_bot_$(date +%Y%m%d).log

# 매도 관련 로그만 확인
tail -f trading_bot_*.log | grep "매도"

# RSI 관련 로그만 확인
tail -f trading_bot_*.log | grep "RSI"
```

### 이벤트 추출
```bash
# 모든 매도 이벤트 추출
grep "매도" trading_bot_*.log > sell_events.txt

# 부분 매도 이벤트만 추출
grep "부분 매도" trading_bot_*.log > partial_sell_events.txt

# RSI 70+ 이벤트 추출
grep -E "RSI.*7[0-9]|RSI.*8[0-9]" trading_bot_*.log > high_rsi_events.txt
```

### 성과 요약
```bash
# 최종 성과 확인
cat performance_*.json | jq -r '.portfolio_value' | tail -1

# 일일 수익률 계산
python3 << 'EOF'
import json
import glob

files = sorted(glob.glob('performance_*.json'))
if len(files) >= 2:
    with open(files[0], 'r') as f:
        start = json.load(f)
    with open(files[-1], 'r') as f:
        end = json.load(f)
    
    start_val = start.get('portfolio_value', 0)
    end_val = end.get('portfolio_value', 0)
    profit_rate = ((end_val - start_val) / start_val * 100) if start_val > 0 else 0
    
    print(f"시작: {start_val:,.0f}원")
    print(f"종료: {end_val:,.0f}원")
    print(f"수익률: {profit_rate:+.2f}%")
EOF
```

---

## 🛠️ 문제 해결

### 봇이 시작되지 않을 때
```bash
# Python 환경 확인
which python3
python3 --version

# 가상환경 활성화
source .venv/bin/activate

# 패키지 재설치
pip install -r requirements.txt
```

### 로그가 생성되지 않을 때
```bash
# 파일 권한 확인
ls -la *.log

# 디렉토리 권한 확인
ls -la .

# 수동으로 로그 파일 생성
touch trading_bot_$(date +%Y%m%d).log
```

### 이전 백업 복원하기
```bash
# 백업 목록 확인
ls -lt backup/

# 특정 백업 복원 (예: before_20251004_120000)
cp backup/before_20251004_120000/* .
```

---

## 💡 베스트 프랙티스

### ✅ DO (권장 사항)
1. **항상 백업**: 새 테스트 전 `./start_fresh_test.sh` 실행
2. **소액 테스트**: 처음엔 소액으로 1-2일 테스트
3. **로그 모니터링**: 실시간으로 `tail -f` 사용
4. **정기 확인**: 2-4시간마다 성과 확인
5. **문서화**: 특이사항은 메모로 기록

### ❌ DON'T (피해야 할 것)
1. **백업 없이 삭제**: 복구 불가능!
2. **무감독 장기 운영**: 초기엔 반드시 모니터링
3. **설정 무시**: config.json 확인 필수
4. **에러 방치**: 로그의 ERROR 즉시 대응
5. **과신**: 항상 리스크 관리 염두

---

## 📈 성과 평가 체크리스트

테스트 후 다음 항목들을 확인하세요:

- [ ] 상승장에서 조기 매도 안했는가?
- [ ] 하락장에서 빠르게 대응했는가?
- [ ] RSI 70-75 구간에서 매도 제한 작동했는가?
- [ ] 부분 매도가 적절하게 실행되었는가?
- [ ] 거래량 검증이 가짜 돌파를 막았는가?
- [ ] AI 비용이 예산 내인가?
- [ ] 전체 수익률이 목표치 이상인가?

---

## 🆘 긴급 중단

### 봇 즉시 중단
```bash
# 프로세스 찾기
ps aux | grep mvp.py

# 강제 종료 (PID는 위에서 확인)
kill -9 [PID]

# 또는 터미널에서
Ctrl + C
```

### 긴급 전량 매도 (수동)
봇을 중단한 후 업비트 앱/웹에서 수동으로 매도하세요.

---

**🎯 준비되셨나요? 새로운 테스트를 시작해보세요!**

```bash
./start_fresh_test.sh
python3 mvp.py
```

행운을 빕니다! 🚀
