#!/usr/bin/env python3
"""
나머지 첨부파일 재수집 (1000개 이후)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from supabase import create_client
from dotenv import load_dotenv
import json

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 먼저 전체 개수를 확인
print("="*70)
print("📊 나머지 데이터 확인")
print("="*70)

# K-Startup 나머지
ks_total = supabase.table('kstartup_complete')\
    .select('id', count='exact')\
    .execute()
print(f"\nK-Startup 전체: {ks_total.count}개")

# 1000번째 이후 데이터 조회
if ks_total.count > 1000:
    print(f"K-Startup 나머지: {ks_total.count - 1000}개 추가 처리 필요")
    
    # 1001번째부터 조회
    ks_remaining = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm')\
        .range(1000, ks_total.count)\
        .execute()
    
    print(f"실제 조회된 나머지: {len(ks_remaining.data)}개")
    if ks_remaining.data:
        print("샘플:")
        for item in ks_remaining.data[:3]:
            print(f"  - {item['announcement_id']}: {item.get('biz_pbanc_nm', 'No Title')[:30]}...")

# BizInfo 나머지
bi_total = supabase.table('bizinfo_complete')\
    .select('id', count='exact')\
    .execute()
print(f"\nBizInfo 전체: {bi_total.count}개")

if bi_total.count > 1000:
    print(f"BizInfo 나머지: {bi_total.count - 1000}개 추가 처리 필요")
    
    # 1001번째부터 조회 (offset 사용)
    bi_remaining = supabase.table('bizinfo_complete')\
        .select('announcement_id, pblanc_nm')\
        .range(1000, bi_total.count)\
        .execute()
    
    print(f"실제 조회된 나머지: {len(bi_remaining.data)}개")
    if bi_remaining.data:
        print("샘플:")
        for item in bi_remaining.data[:3]:
            print(f"  - {item.get('announcement_id', 'N/A')}: {item.get('pblanc_nm', 'No Title')[:30]}...")

print("\n" + "="*70)
print("💡 처리 방법:")
print("1. range() 메서드로 1000개씩 나눠서 처리")
print("2. 각 배치별로 재수집 실행")
print("="*70)