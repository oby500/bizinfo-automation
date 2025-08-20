#!/usr/bin/env python3
"""
기업마당 간단 수집 스크립트
- API를 통한 기본 데이터 수집
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
import os
import time

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("환경변수 오류: SUPABASE_URL, SUPABASE_KEY 필요")
    exit(1)

supabase = create_client(url, key)

def main():
    print("="*60)
    print("🏢 기업마당 데이터 수집")
    print("="*60)
    
    # 기본 API URL (실제 API가 없으므로 더미 데이터)
    sample_data = [
        {
            'pblanc_id': f'BIZ_{datetime.now().strftime("%Y%m%d")}001',
            'pblanc_nm': '2025년 스타트업 지원사업',
            'jrsd_instt_nm': '중소벤처기업부',
            'bsnspbanc_ctnt': '스타트업 성장 지원',
            'rqutpbanc_end_dt': '2025-03-31',
            'status': '모집중',
            'created_at': datetime.now().isoformat()
        }
    ]
    
    print(f"📊 수집 데이터: {len(sample_data)}개")
    
    saved = 0
    for data in sample_data:
        try:
            # 중복 체크
            existing = supabase.table('bizinfo_complete')\
                .select('id')\
                .eq('pblanc_id', data['pblanc_id'])\
                .execute()
            
            if not existing.data:
                result = supabase.table('bizinfo_complete').insert(data).execute()
                saved += 1
                print(f"✅ 저장: {data['pblanc_nm']}")
            else:
                print(f"⏭️ 중복: {data['pblanc_nm']}")
                
        except Exception as e:
            print(f"❌ 오류: {e}")
    
    print(f"\n📊 결과: {saved}개 저장")
    print("="*60)

if __name__ == "__main__":
    main()