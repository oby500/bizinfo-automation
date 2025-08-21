#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
간단한 Bizinfo 테스트 스크립트
GitHub Actions 테스트용
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

print("="*60)
print("🏢 Bizinfo 테스트 수집")
print("="*60)

# 환경 확인
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

print("\n📋 환경 확인:")
print(f"  - Supabase URL: {SUPABASE_URL[:30]}..." if SUPABASE_URL else "  - Supabase URL: ❌ 없음")
print(f"  - Supabase Key: {SUPABASE_KEY[:30]}..." if SUPABASE_KEY else "  - Supabase Key: ❌ 없음")

# Bizinfo API 테스트
print("\n📊 Bizinfo API 테스트:")
try:
    url = "https://www.bizinfo.go.kr/uss/rss/bizinfo.do"
    response = requests.get(url, timeout=10)
    print(f"  - HTTP 상태: {response.status_code}")
    
    if response.status_code == 200:
        print(f"  - 응답 크기: {len(response.text)} bytes")
        # RSS 피드 파싱 테스트
        if '<rss' in response.text:
            print("  - RSS 피드: ✅ 확인")
        else:
            print("  - RSS 피드: ❌ 형식 오류")
    else:
        print(f"  - HTTP 오류: {response.status_code}")
        
except Exception as e:
    print(f"  - 오류 발생: {e}")

# Supabase 테스트
print("\n💾 Supabase 연결 테스트:")
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 테이블 존재 확인
        try:
            result = supabase.table('bizinfo_complete').select('id').limit(1).execute()
            print("  - bizinfo_complete 테이블: ✅ 존재")
        except Exception as e:
            if 'does not exist' in str(e) or '42P01' in str(e):
                print("  - bizinfo_complete 테이블: ❌ 없음")
            else:
                print(f"  - 테이블 확인 오류: {e}")
                
    except ImportError:
        print("  - Supabase 라이브러리: ❌ 설치 필요")
    except Exception as e:
        print(f"  - 연결 오류: {e}")
else:
    print("  - 환경변수 없음")

print("\n" + "="*60)
print("✅ 테스트 완료")
print("="*60)