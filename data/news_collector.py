"""
뉴스 수집 및 감정 분석 모듈
"""

import os
import json
import time
import logging
import requests


def get_news_headlines(portfolio_coins, cache_file, cache_duration):
    """
    뉴스 헤드라인 수집 (캐시 지원)
    
    Args:
        portfolio_coins: 포트폴리오 코인 리스트
        cache_file: 캐시 파일 경로
        cache_duration: 캐시 유효 기간 (초)
    
    Returns:
        list: 뉴스 헤드라인 리스트
    """
    try:
        # 캐시 파일이 있으면, 4시간 이내면 캐시 데이터 반환
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cache = json.load(f)
            if time.time() - cache["timestamp"] < cache_duration:
                return cache["data"]
        
        # API 호출 및 캐시 저장
        news_api_key = os.getenv("NEWS_API_KEY")
        if not news_api_key:
            print("⚠️ 뉴스 API 키가 없어 뉴스 수집을 건너뜁니다.")
            return []
        
        # 포트폴리오 코인들의 뉴스 수집
        all_headlines = []
        coin_names = []
        
        # 포트폴리오 코인 이름 추출 및 검색 키워드 생성
        for ticker in portfolio_coins:
            coin_name = ticker.split('-')[1].lower()
            if coin_name == 'btc':
                coin_names.extend(['bitcoin', 'btc'])
            elif coin_name == 'eth':
                coin_names.extend(['ethereum', 'eth'])
            elif coin_name == 'sol':
                coin_names.extend(['solana', 'sol'])
            elif coin_name == 'xrp':
                coin_names.extend(['ripple', 'xrp'])
            else:
                coin_names.append(coin_name)
        
        # 각 코인에 대해 뉴스 검색
        search_query = " OR ".join(coin_names[:10])
        resp = requests.get(f"https://newsdata.io/api/1/latest?apikey={news_api_key}&q={search_query}")
        data = resp.json()
        
        if data.get('results'):
            for item in data['results']:
                headline = item.get('title', '')
                if headline:
                    all_headlines.append(headline)
        
        # 중복 제거
        unique_headlines = list(dict.fromkeys(all_headlines))
        
        with open(cache_file, "w") as f:
            json.dump({"timestamp": time.time(), "data": unique_headlines}, f)
        
        print(f"📰 포트폴리오 코인 뉴스 수집: {len(unique_headlines)}개")
        return unique_headlines
        
    except Exception as e:
        logging.error(f"뉴스 수집 실패: {e}")
        return get_free_crypto_news()


def get_free_crypto_news():
    """무료 암호화폐 뉴스 소스 (Reddit 기반)"""
    try:
        url = "https://www.reddit.com/r/CryptoCurrency/hot.json?limit=25"
        headers = {'User-Agent': 'AI-Trading-Bot/1.0'}
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        headlines = []
        
        # 포트폴리오 코인 키워드 정의
        portfolio_keywords = {
            'bitcoin': ['bitcoin', 'btc', 'Bitcoin', 'BTC'],
            'ethereum': ['ethereum', 'eth', 'Ethereum', 'ETH'],
            'solana': ['solana', 'sol', 'Solana', 'SOL'],
            'ripple': ['ripple', 'xrp', 'Ripple', 'XRP']
        }
        
        if 'data' in data and 'children' in data['data']:
            for post in data['data']['children']:
                title = post['data']['title']
                score = post['data']['score']
                
                if score > 3:
                    # 포트폴리오 코인 관련 뉴스인지 확인
                    is_relevant = False
                    for coin, keywords in portfolio_keywords.items():
                        if any(keyword in title for keyword in keywords):
                            is_relevant = True
                            break
                    
                    # 일반적인 암호화폐 뉴스도 포함
                    general_crypto_keywords = ['crypto', 'cryptocurrency', 'blockchain', 'DeFi', 'NFT', 'altcoin', 'bull', 'bear', 'pump', 'dump']
                    if not is_relevant:
                        is_relevant = any(keyword.lower() in title.lower() for keyword in general_crypto_keywords)
                    
                    if is_relevant:
                        headlines.append(title)
        
        print(f"📰 Reddit 뉴스 수집: {len(headlines)}개 (포트폴리오 코인 중심)")
        return headlines[:15]
        
    except Exception as e:
        logging.warning(f"무료 뉴스 수집 실패: {e}")
        return []


def analyze_news_sentiment(headlines):
    """뉴스 감정 분석 및 긴급 이벤트 감지"""
    if not headlines:
        return {"sentiment": "neutral", "emergency": False, "events": []}
    
    # 긴급 키워드 정의
    emergency_negative = ["hack", "hacked", "stolen", "exploit", "attack", "collapse", "bankrupt", "scam", "rugpull", "crash", "dump"]
    emergency_positive = ["ETF approved", "approved", "institutional", "Tesla", "Microsoft", "MicroStrategy", "adoption", "pump", "moon", "breakthrough"]
    regulatory_risk = ["SEC", "ban", "illegal", "lawsuit", "investigation", "probe", "fine", "regulatory"]
    
    # 포트폴리오 코인별 특별 이벤트
    coin_specific_positive = {
        'bitcoin': ['halving', 'mining', 'store of value', 'digital gold'],
        'ethereum': ['merge', 'staking', 'defi', 'smart contract', 'gas fee reduction'],
        'solana': ['fast transaction', 'ecosystem growth', 'nft', 'validator'],
        'ripple': ['payment', 'bank partnership', 'cross border', 'legal victory']
    }
    
    coin_specific_negative = {
        'bitcoin': ['energy consumption', 'mining ban'],
        'ethereum': ['gas fee', 'scalability issue'],
        'solana': ['network outage', 'downtime'],
        'ripple': ['sec lawsuit', 'delisting']
    }
    
    sentiment_score = 0
    emergency_events = []
    coin_mentions = {'bitcoin': 0, 'ethereum': 0, 'solana': 0, 'ripple': 0}
    
    for headline in headlines:
        headline_lower = headline.lower()
        
        # 긴급 부정 이벤트
        for keyword in emergency_negative:
            if keyword in headline_lower:
                sentiment_score -= 3
                emergency_events.append(f"🚨 위험: {keyword}")
        
        # 긴급 긍정 이벤트
        for keyword in emergency_positive:
            if keyword in headline_lower:
                sentiment_score += 2
                emergency_events.append(f"🚀 호재: {keyword}")
        
        # 규제 리스크
        for keyword in regulatory_risk:
            if keyword in headline_lower:
                sentiment_score -= 1
                emergency_events.append(f"⚖️ 규제: {keyword}")
        
        # 포트폴리오 코인별 특별 이벤트 분석
        for coin, positive_keywords in coin_specific_positive.items():
            if any(kw in headline_lower for kw in positive_keywords):
                sentiment_score += 1
                coin_mentions[coin] += 1
                emergency_events.append(f"💎 {coin.upper()} 호재")
        
        for coin, negative_keywords in coin_specific_negative.items():
            if any(kw in headline_lower for kw in negative_keywords):
                sentiment_score -= 1
                coin_mentions[coin] += 1
                emergency_events.append(f"⚠️ {coin.upper()} 악재")
        
        # 일반적인 코인 언급 체크
        coin_keywords = {
            'bitcoin': ['bitcoin', 'btc'],
            'ethereum': ['ethereum', 'eth'],
            'solana': ['solana', 'sol'],
            'ripple': ['ripple', 'xrp']
        }
        
        for coin, keywords in coin_keywords.items():
            if any(kw in headline_lower for kw in keywords):
                coin_mentions[coin] += 1
    
    # 감정 분류
    if sentiment_score >= 4:
        sentiment = "very_bullish"
    elif sentiment_score >= 2:
        sentiment = "bullish"
    elif sentiment_score <= -4:
        sentiment = "very_bearish"
    elif sentiment_score <= -2:
        sentiment = "bearish"
    else:
        sentiment = "neutral"
    
    # 가장 많이 언급된 코인 정보 추가
    most_mentioned_coin = max(coin_mentions, key=coin_mentions.get) if max(coin_mentions.values()) > 0 else None
    
    return {
        "sentiment": sentiment,
        "score": sentiment_score,
        "emergency": abs(sentiment_score) >= 3,
        "events": emergency_events[:5],
        "coin_mentions": coin_mentions,
        "focus_coin": most_mentioned_coin
    }
