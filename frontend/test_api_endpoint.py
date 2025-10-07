#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 엔드포인트 테스트
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("\n" + "="*70)
print("API Endpoint Test")
print("="*70)

# 1. 통계 API 테스트
print("\n[1] Testing /api/stats")
try:
    response = requests.get(f"{BASE_URL}/api/stats", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"  Total: {data.get('total', 0)}")
        print(f"  Ongoing: {data.get('ongoing', 0)}")
        print(f"  Deadline: {data.get('deadline', 0)}")
        print("  [OK] Stats API working")
    else:
        print(f"  [ERROR] Status code: {response.status_code}")
except Exception as e:
    print(f"  [ERROR] {e}")

# 2. 검색 API 테스트
print("\n[2] Testing /api/search")
try:
    response = requests.get(f"{BASE_URL}/api/search?q=AI&limit=5", timeout=5)
    if response.status_code == 200:
        data = response.json()
        count = len(data.get('data', []))
        print(f"  Found: {count} results")
        if count > 0:
            first = data['data'][0]
            print(f"  Sample: {first.get('title', '')[:50]}...")
        print("  [OK] Search API working")
    else:
        print(f"  [ERROR] Status code: {response.status_code}")
except Exception as e:
    print(f"  [ERROR] {e}")

# 3. 상세 조회 API 테스트
print("\n[3] Testing /api/announcement/{id}")
try:
    # 먼저 검색으로 ID 하나 가져오기
    search_response = requests.get(f"{BASE_URL}/api/search?limit=1", timeout=5)
    if search_response.status_code == 200:
        search_data = search_response.json()
        if search_data.get('data'):
            test_id = search_data['data'][0]['id']
            print(f"  Testing with ID: {test_id}")

            # 상세 조회
            detail_response = requests.get(f"{BASE_URL}/api/announcement/{test_id}", timeout=5)
            if detail_response.status_code == 200:
                detail_data = detail_response.json()
                if detail_data.get('success'):
                    item = detail_data['data']
                    print(f"  Title: {item.get('title', '')[:50]}...")
                    print(f"  Organization: {item.get('organization', '')}")
                    print(f"  Simple Summary: {'YES' if item.get('simple_summary') else 'NO'}")
                    print(f"  Detailed Summary: {'YES' if item.get('detailed_summary') else 'NO'}")
                    print(f"  Attachments: {len(item.get('attachment_urls', []))}")
                    print("  [OK] Detail API working")
                else:
                    print(f"  [ERROR] Success: False")
            else:
                print(f"  [ERROR] Status code: {detail_response.status_code}")
        else:
            print("  [SKIP] No data to test")
    else:
        print(f"  [ERROR] Search failed: {search_response.status_code}")
except Exception as e:
    print(f"  [ERROR] {e}")

print("\n" + "="*70)
print("Test Complete")
print("="*70 + "\n")
