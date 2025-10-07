#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Supabase 데이터 개수 및 상태 확인
"""

import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime

# 환경변수 로드
load_dotenv()

# Supabase 연결
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(supabase_url, supabase_key)

print("\n" + "="*70)
print("[ Data Count Verification ]")
print("="*70)

# K-Startup 데이터 개수
print("\n[K-Startup Data]")
try:
    ks_response = supabase.table('kstartup_complete').select("announcement_id", count="exact").execute()
    ks_count = ks_response.count if hasattr(ks_response, 'count') else len(ks_response.data)
    print(f"  총 레코드 수: {ks_count}개")

    # 샘플 데이터 확인
    sample = supabase.table('kstartup_complete').select("*").limit(1).execute()
    if sample.data:
        print(f"  샘플 ID: {sample.data[0].get('announcement_id')}")
        print(f"  마감일 컬럼: {sample.data[0].get('end_date') or sample.data[0].get('pbanc_rcpt_end_dt')}")
except Exception as e:
    print(f"  ❌ 오류: {e}")

# BizInfo 데이터 개수
print("\n[BizInfo Data]")
try:
    bi_response = supabase.table('bizinfo_complete').select("pblanc_id", count="exact").execute()
    bi_count = bi_response.count if hasattr(bi_response, 'count') else len(bi_response.data)
    print(f"  총 레코드 수: {bi_count}개")

    # 샘플 데이터 확인
    sample = supabase.table('bizinfo_complete').select("*").limit(1).execute()
    if sample.data:
        print(f"  샘플 ID: {sample.data[0].get('pblanc_id')}")
        print(f"  마감일 컬럼: {sample.data[0].get('bsns_pbanc_end_dt') or sample.data[0].get('reqst_end_ymd')}")
except Exception as e:
    print(f"  ❌ 오류: {e}")

# 총합
print("\n" + "="*70)
total = ks_count + bi_count
print(f"[TOTAL] {total} records (K-Startup: {ks_count}, BizInfo: {bi_count})")
print("="*70 + "\n")

# 마감일 기준 통계
print("\n[Deadline Statistics]")
today = datetime.now().strftime("%Y-%m-%d")

try:
    # K-Startup 진행중
    ks_ongoing = supabase.table('kstartup_complete').select("announcement_id", count="exact").gte("end_date", today).execute()
    ks_ongoing_count = ks_ongoing.count if hasattr(ks_ongoing, 'count') else len(ks_ongoing.data)

    # BizInfo 진행중
    bi_ongoing = supabase.table('bizinfo_complete').select("pblanc_id", count="exact").gte("bsns_pbanc_end_dt", today).execute()
    bi_ongoing_count = bi_ongoing.count if hasattr(bi_ongoing, 'count') else len(bi_ongoing.data)

    print(f"  진행중: {ks_ongoing_count + bi_ongoing_count}개")
    print(f"  마감: {total - (ks_ongoing_count + bi_ongoing_count)}개")
except Exception as e:
    print(f"  ❌ 통계 계산 오류: {e}")

print()
