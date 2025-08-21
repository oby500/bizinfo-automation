#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
간단한 K-Startup 테스트 스크립트
GitHub Actions 테스트용
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

print("="*60)
print("🚀 K-Startup 테스트 수집")
print("="*60)

# 환경 확인
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

print("\n📋 환경 확인:")
print(f"  - Supabase URL: {SUPABASE_URL[:30]}..." if SUPABASE_URL else "  - Supabase URL: ❌ 없음")
print(f"  - Supabase Key: {SUPABASE_KEY[:30]}..." if SUPABASE_KEY else "  - Supabase Key: ❌ 없음")

# API 테스트
API_KEY = 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=='
BASE_URL = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'

print("\n📊 API 테스트:")
try:
    params = {
        'ServiceKey': API_KEY,
        'pageNo': 1,
        'numOfRows': 5
    }
    
    response = requests.get(BASE_URL, params=params, timeout=10)
    print(f"  - HTTP 상태: {response.status_code}")
    
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        header = root.find('.//header')
        
        if header and header.find('resultCode').text == '00':
            items = root.findall('.//item')
            print(f"  - 데이터 수집: {len(items)}개")
            
            # 첫 번째 아이템 정보 출력
            if items:
                first_item = items[0]
                title = first_item.find('pblancNm').text if first_item.find('pblancNm') is not None else "제목 없음"
                print(f"  - 첫 번째 공고: {title[:50]}...")
        else:
            print(f"  - API 오류: {header.find('resultMsg').text if header else 'Unknown'}")
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
            result = supabase.table('kstartup_complete').select('id').limit(1).execute()
            print("  - kstartup_complete 테이블: ✅ 존재")
        except Exception as e:
            if 'does not exist' in str(e) or '42P01' in str(e):
                print("  - kstartup_complete 테이블: ❌ 없음")
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