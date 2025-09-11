#!/usr/bin/env python3
"""
K-Startup attachment_urls 데이터 정규화
- {'url': 'https://...'} 형태를 'https://...' 형태로 변환
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL', 'https://csuziaogycciwgxxmahm.supabase.co')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')

if not key:
    key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzdXppYW9neWNjaXdneHhtYWhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYxNTc4MCwiZXhwIjoyMDY5MTkxNzgwfQ.HnhM7zSLzi7lHVPd2IVQKIACDq_YA05mBMgZbSN1c9Q'

supabase = create_client(url, key)

def normalize_urls():
    """attachment_urls 정규화"""
    
    print("K-Startup attachment_urls 정규화 시작...")
    
    # attachment_urls가 있는 모든 레코드 조회
    offset = 0
    limit = 100
    total_processed = 0
    total_updated = 0
    
    while True:
        result = supabase.table('kstartup_complete')\
            .select('announcement_id, attachment_urls')\
            .neq('attachment_urls', '[]')\
            .range(offset, offset + limit - 1)\
            .execute()
        
        if not result.data:
            break
        
        for item in result.data:
            announcement_id = item['announcement_id']
            attachment_urls = item.get('attachment_urls', [])
            
            # 정규화 필요 여부 체크
            needs_update = False
            normalized_urls = []
            
            for url_item in attachment_urls:
                if isinstance(url_item, dict) and 'url' in url_item:
                    # {'url': 'https://...'} 형태인 경우
                    normalized_urls.append(url_item['url'])
                    needs_update = True
                elif isinstance(url_item, str):
                    # 이미 문자열인 경우
                    normalized_urls.append(url_item)
                else:
                    # 기타 형태는 건너뛰기
                    continue
            
            # 업데이트 필요한 경우
            if needs_update and normalized_urls:
                try:
                    supabase.table('kstartup_complete').update({
                        'attachment_urls': normalized_urls
                    }).eq('announcement_id', announcement_id).execute()
                    
                    print(f"[정규화] {announcement_id}: {len(normalized_urls)}개 URL")
                    total_updated += 1
                except Exception as e:
                    print(f"[오류] {announcement_id}: {e}")
            
            total_processed += 1
        
        offset += limit
        
        if len(result.data) < limit:
            break
    
    print(f"\n정규화 완료:")
    print(f"- 검사한 레코드: {total_processed}개")
    print(f"- 업데이트한 레코드: {total_updated}개")

if __name__ == "__main__":
    normalize_urls()