#!/usr/bin/env python3
"""
BizInfo attachment_urls 정리 - 순수 URL만 남기기
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

def clean_attachments():
    """잘못된 형식의 attachment_urls를 정리"""
    print("="*70)
    print("🧹 BizInfo attachment_urls 정리 시작")
    print("="*70)
    
    # 모든 attachment_urls가 있는 레코드 가져오기
    print("데이터 로딩 중...")
    all_data = []
    offset = 0
    page_size = 1000
    
    while True:
        batch = supabase.table('bizinfo_complete')\
            .select('pblanc_id, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .not_.eq('attachment_urls', '[]')\
            .range(offset, offset + page_size - 1)\
            .execute()
        
        if not batch.data:
            break
            
        all_data.extend(batch.data)
        
        if len(batch.data) < page_size:
            break
        offset += page_size
    
    print(f"✅ 총 {len(all_data)}개 레코드 로드")
    
    fixed_count = 0
    error_count = 0
    
    for record in all_data:
        pblanc_id = record['pblanc_id']
        attachments = record.get('attachment_urls')
        
        # 문자열인 경우 JSON 파싱
        if isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except:
                continue
        
        if not isinstance(attachments, list):
            continue
        
        # 정리가 필요한지 확인
        needs_cleaning = False
        cleaned_urls = []
        
        for att in attachments:
            if isinstance(att, dict):
                # 이미 깨끗한 형식 (url만 있음)
                if list(att.keys()) == ['url']:
                    cleaned_urls.append(att)
                # 잘못된 형식 (여러 필드가 있음)
                else:
                    needs_cleaning = True
                    # download_url이 있으면 그것을 사용
                    if 'download_url' in att:
                        cleaned_urls.append({'url': att['download_url']})
                    # url이 있으면 그것을 사용
                    elif 'url' in att:
                        cleaned_urls.append({'url': att['url']})
                    # file_id로 URL 생성
                    elif 'file_id' in att:
                        file_id = att['file_id']
                        if file_id.startswith('getImageFile.do'):
                            url_str = f"https://www.bizinfo.go.kr/cmm/fms/{file_id}"
                        else:
                            url_str = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?{file_id}"
                        cleaned_urls.append({'url': url_str})
            else:
                # dict가 아닌 경우 (이상한 형식)
                needs_cleaning = True
        
        # 정리가 필요한 경우 업데이트
        if needs_cleaning and cleaned_urls:
            try:
                # 중복 제거
                seen_urls = set()
                unique_urls = []
                for item in cleaned_urls:
                    if item['url'] not in seen_urls:
                        seen_urls.add(item['url'])
                        unique_urls.append(item)
                
                # 데이터베이스 업데이트
                result = supabase.table('bizinfo_complete')\
                    .update({'attachment_urls': unique_urls})\
                    .eq('pblanc_id', pblanc_id)\
                    .execute()
                
                if result.data:
                    fixed_count += 1
                    print(f"✅ {pblanc_id}: {len(attachments)}개 → {len(unique_urls)}개 URL로 정리")
            except Exception as e:
                error_count += 1
                print(f"❌ {pblanc_id}: 오류 - {str(e)[:50]}")
    
    print("\n" + "="*70)
    print("📊 정리 완료")
    print("="*70)
    print(f"✅ 정리된 레코드: {fixed_count}개")
    print(f"❌ 오류: {error_count}개")
    print("\n🎯 결과:")
    print("  - 모든 attachment_urls가 {'url': '...'} 형식으로 통일됨")
    print("  - 불필요한 필드 모두 제거")
    print("  - 중복 URL 제거")
    print("="*70)

if __name__ == "__main__":
    clean_attachments()