#!/usr/bin/env python3
"""
attachment_urls를 JSON 문자열에서 배열로 복구
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

def restore_attachments():
    """JSON 문자열을 배열로 복구"""
    print("="*70)
    print("attachment_urls 복구 시작")
    print("="*70)
    
    # 모든 레코드 조회
    offset = 0
    batch_size = 100
    total_fixed = 0
    
    while True:
        # K-Startup 처리
        result = supabase.table('kstartup_complete')\
            .select('announcement_id, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not result.data:
            break
        
        print(f"\n배치 {offset//batch_size + 1}: {offset+1}~{offset+len(result.data)}")
        
        for record in result.data:
            ann_id = record['announcement_id']
            att = record.get('attachment_urls')
            
            if not att:
                continue
            
            # 문자열인 경우 JSON 파싱해서 배열로 저장
            if isinstance(att, str):
                try:
                    parsed = json.loads(att)
                    
                    # KS_KS_ 중복 제거
                    for item in parsed:
                        if isinstance(item, dict):
                            safe_filename = item.get('safe_filename', '')
                            if 'KS_KS_' in safe_filename:
                                item['safe_filename'] = safe_filename.replace('KS_KS_', 'KS_', 1)
                    
                    # 배열로 저장 (문자열 아님!)
                    supabase.table('kstartup_complete')\
                        .update({'attachment_urls': parsed})\
                        .eq('announcement_id', ann_id)\
                        .execute()
                    
                    total_fixed += 1
                    print(f"  ✅ {ann_id} 복구")
                except Exception as e:
                    print(f"  ❌ {ann_id} 실패: {str(e)[:50]}")
        
        offset += batch_size
        
        if offset >= 2000:
            print("\n최대 2000개까지만 처리")
            break
    
    print(f"\n✅ 총 {total_fixed}개 레코드 복구 완료")
    
    # 결과 검증
    print("\n검증 중...")
    result = supabase.table('kstartup_complete')\
        .select('attachment_urls')\
        .not_.is_('attachment_urls', 'null')\
        .limit(100)\
        .execute()
    
    str_count = 0
    list_count = 0
    
    for record in result.data:
        att = record.get('attachment_urls')
        if isinstance(att, str):
            str_count += 1
        elif isinstance(att, list):
            list_count += 1
    
    print(f"\n최종 상태 (100개 샘플):")
    print(f"  문자열: {str_count}개")
    print(f"  배열: {list_count}개")
    
    if str_count == 0:
        print("✅ 모든 데이터가 배열로 복구되었습니다!")
    else:
        print(f"⚠️ 아직 {str_count}개가 문자열입니다. 다시 실행이 필요할 수 있습니다.")

if __name__ == "__main__":
    restore_attachments()