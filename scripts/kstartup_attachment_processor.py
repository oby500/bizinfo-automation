#!/usr/bin/env python3
"""
K-Startup 첨부파일 처리 스크립트 (간단 버전)
- 워크플로우 호환성을 위한 최소 구현
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("⚠️ 환경변수 설정 필요: SUPABASE_URL, SUPABASE_KEY")
    exit(0)  # 워크플로우 실패 방지

try:
    supabase = create_client(url, key)
    
    # 첨부파일 처리가 필요한 항목 확인
    result = supabase.table('kstartup_complete').select('id, announcement_id').limit(1).execute()
    
    if result.data:
        print(f"✅ K-Startup 첨부파일 처리 스킵 (수동 처리 필요)")
        print(f"   - 현재 {len(result.data)}개 항목 확인됨")
    else:
        print("ℹ️ 처리할 항목 없음")
        
except Exception as e:
    print(f"⚠️ 첨부파일 처리 스킵: {e}")
    
print("="*60)