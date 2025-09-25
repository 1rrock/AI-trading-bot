#!/usr/bin/env python3
"""
비트코인 10만원 매수 테스트 스크립트
"""

import os
from dotenv import load_dotenv
import pyupbit
import time

def test_buy_bitcoin(amount_krw=100000):
    """
    지정한 금액만큼 비트코인을 매수하는 테스트 함수
    
    Args:
        amount_krw (int): 매수할 원화 금액 (기본값: 100,000원)
    """
    print("🤖 비트코인 매수 테스트 시작")
    print("=" * 40)
    
    # 환경변수 로드
    load_dotenv()
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    
    if not access or not secret:
        print("❌ 오류: UPBIT API 키가 설정되지 않았습니다.")
        print("📝 .env 파일에 다음을 설정하세요:")
        print("   UPBIT_ACCESS_KEY=your_access_key")
        print("   UPBIT_SECRET_KEY=your_secret_key")
        return False
    
    # Upbit 연결
    upbit = pyupbit.Upbit(access, secret)
    
    try:
        # 1. 현재 잔고 확인
        print("💰 현재 잔고 확인 중...")
        my_krw = upbit.get_balance("KRW")
        my_btc = upbit.get_balance("KRW-BTC")
        
        print(f"   보유 KRW: {my_krw:,.0f} 원")
        print(f"   보유 BTC: {my_btc:.8f} BTC")
        
        # 2. 현재 비트코인 가격 확인
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")['orderbook_units'][0]['ask_price']
        print(f"   현재 BTC 가격: {current_price:,.0f} 원")
        
        # 3. 매수 가능 여부 확인
        if my_krw < amount_krw:
            print(f"❌ 잔고 부족: {amount_krw:,}원이 필요하지만 {my_krw:,.0f}원만 있습니다.")
            return False
        
        if amount_krw < 5000:
            print(f"❌ 최소 주문 금액 미달: 5,000원 이상이어야 합니다. (입력: {amount_krw:,}원)")
            return False
        
        # 4. 매수 확인
        print(f"\n🎯 매수 계획:")
        print(f"   매수 금액: {amount_krw:,}원")
        print(f"   예상 수량: {amount_krw/current_price:.8f} BTC")
        print(f"   수수료 고려: {amount_krw*0.9995:,.0f}원 실제 투자")
        
        confirmation = input(f"\n정말로 {amount_krw:,}원어치 비트코인을 매수하시겠습니까? (y/N): ")
        
        if confirmation.lower() != 'y':
            print("❌ 매수가 취소되었습니다.")
            return False
        
        # 5. 매수 실행
        print(f"\n🚀 {amount_krw:,}원어치 비트코인 매수 실행 중...")
        
        # 수수료를 고려한 실제 매수 금액
        actual_amount = amount_krw * 0.9995
        
        result = upbit.buy_market_order("KRW-BTC", actual_amount)
        
        if result:
            print("✅ 매수 주문이 성공적으로 전송되었습니다!")
            print(f"📋 주문 정보:")
            print(f"   주문 UUID: {result.get('uuid', 'N/A')}")
            print(f"   주문 유형: {result.get('ord_type', 'N/A')}")
            print(f"   주문 금액: {float(result.get('price', 0)):,.0f} 원")
            
            # 잠시 대기 후 잔고 재확인
            print("\n⏳ 3초 후 잔고를 재확인합니다...")
            time.sleep(3)
            
            new_krw = upbit.get_balance("KRW")
            new_btc = upbit.get_balance("KRW-BTC")
            
            print(f"\n📊 매수 후 잔고:")
            print(f"   KRW: {my_krw:,.0f} → {new_krw:,.0f} 원 (차이: {new_krw-my_krw:+,.0f})")
            print(f"   BTC: {my_btc:.8f} → {new_btc:.8f} BTC (차이: {new_btc-my_btc:+.8f})")
            
            if new_btc > my_btc:
                print("✅ 비트코인 매수가 성공적으로 완료되었습니다! 🎉")
                return True
            else:
                print("⚠️  주문은 전송되었지만 잔고 변화를 확인할 수 없습니다. 거래소에서 확인해주세요.")
                return True
        else:
            print("❌ 매수 주문에 실패했습니다.")
            return False
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

def show_balance():
    """현재 잔고만 확인하는 함수"""
    print("💰 현재 잔고 확인")
    print("=" * 20)
    
    load_dotenv()
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    
    if not access or not secret:
        print("❌ API 키가 설정되지 않았습니다.")
        return
    
    upbit = pyupbit.Upbit(access, secret)
    
    try:
        krw = upbit.get_balance("KRW")
        btc = upbit.get_balance("KRW-BTC")
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")['orderbook_units'][0]['ask_price']
        
        print(f"KRW 잔고: {krw:,.0f} 원")
        print(f"BTC 잔고: {btc:.8f} BTC")
        print(f"BTC 가치: {btc * current_price:,.0f} 원")
        print(f"총 자산: {krw + (btc * current_price):,.0f} 원")
        print(f"현재 BTC 가격: {current_price:,.0f} 원")
        
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    import sys
    
    print("🤖 비트코인 매수 테스트 도구")
    print("=" * 30)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "balance":
            show_balance()
        elif command == "buy":
            amount = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
            test_buy_bitcoin(amount)
        elif command == "help":
            print("사용법:")
            print("  python test_buy.py buy [금액]     # 지정 금액만큼 매수 (기본: 100,000원)")
            print("  python test_buy.py balance        # 현재 잔고 확인")
            print("  python test_buy.py help           # 도움말")
            print("")
            print("예시:")
            print("  python test_buy.py buy 50000      # 5만원어치 매수")
            print("  python test_buy.py buy 200000     # 20만원어치 매수")
        else:
            print("❌ 잘못된 명령어입니다. 'help'를 입력하세요.")
    else:
        # 기본값: 10만원어치 매수
        test_buy_bitcoin(100000)