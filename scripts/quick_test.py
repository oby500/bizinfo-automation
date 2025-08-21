import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, date

print("🚀 K-Startup 최신 100개 유효 공고 수집 시작")
print("=" * 60)

base_url = "https://www.k-startup.go.kr/api/apisvc/xml/GetPblancListSvc"
today = date.today()

print(f"📅 오늘 날짜: {today}")
print()

# API 파라미터
params = {
    'perPage': '100',
    'page': '1', 
    'sortColumn': 'REG_YMD',
    'sortDirection': 'DESC'
}

print("📡 API 호출 중...")

try:
    response = requests.get(base_url, params=params, timeout=30)
    print(f"응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ API 호출 성공!")
        print(f"응답 크기: {len(response.content)} bytes")
        
        # XML 파싱
        root = ET.fromstring(response.text)
        print(f"XML 루트: {root.tag}")
        
        # 아이템 찾기
        items = []
        for elem in root.iter():
            if elem.tag.lower().endswith('item'):
                items.append(elem)
        
        print(f"발견된 아이템: {len(items)}개")
        
        if items:
            print()
            print("샘플 아이템 구조 (첫 번째):")
            print("-" * 40)
            first_item = items[0]
            for child in first_item:
                if child.text and child.text.strip():
                    value = child.text.strip()
                    if len(value) > 50:
                        value = value[:50] + "..."
                    print(f"{child.tag}: {value}")
        
    else:
        print(f"❌ API 호출 실패: {response.status_code}")
        
except Exception as e:
    print(f"❌ 오류: {e}")

print()
print("🎉 초기 테스트 완료")
