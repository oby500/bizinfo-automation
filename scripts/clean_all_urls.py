#!/usr/bin/env python3
"""
K-Startup과 BizInfo 모두 정리 - 순수 URL만 남기기
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

def clean_kstartup():
    """K-Startup attachment_urls 정리"""
    print("\n" + "="*70)
    print("🧹 K-Startup attachment_urls 정리")
    print("="*70)
    
    # 모든 attachment_urls가 있는 레코드 가져오기
    all_data = []
    offset = 0
    page_size = 1000
    
    while True:
        batch = supabase.table('kstartup_complete')\
            .select('announcement_id, attachment_urls')\
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
    
    print(f"✅ K-Startup {len(all_data)}개 레코드 로드")
    
    fixed_count = 0
    
    for record in all_data:
        announcement_id = record['announcement_id']
        attachments = record.get('attachment_urls')
        
        if isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except:
                continue
        
        if not isinstance(attachments, list):
            continue
        
        needs_cleaning = False
        cleaned_urls = []
        
        for att in attachments:
            if isinstance(att, dict):
                # 이미 깨끗한 형식
                if list(att.keys()) == ['url']:
                    cleaned_urls.append(att)
                # 잘못된 형식
                else:
                    needs_cleaning = True
                    # download_url 우선
                    if 'download_url' in att:
                        cleaned_urls.append({'url': att['download_url']})
                    # url 필드
                    elif 'url' in att:
                        cleaned_urls.append({'url': att['url']})
            elif isinstance(att, str):
                # 문자열인 경우 그대로 URL로 사용
                needs_cleaning = True
                cleaned_urls.append({'url': att})
        
        if needs_cleaning and cleaned_urls:
            try:
                # 중복 제거
                seen_urls = set()
                unique_urls = []
                for item in cleaned_urls:
                    if item['url'] not in seen_urls:
                        seen_urls.add(item['url'])
                        unique_urls.append(item)
                
                # 업데이트
                result = supabase.table('kstartup_complete')\
                    .update({'attachment_urls': unique_urls})\
                    .eq('announcement_id', announcement_id)\
                    .execute()
                
                if result.data:
                    fixed_count += 1
                    if fixed_count % 50 == 0:
                        print(f"  처리 중... {fixed_count}개 완료")
            except:
                pass
    
    print(f"✅ K-Startup 정리 완료: {fixed_count}개")
    return fixed_count

def clean_bizinfo():
    """BizInfo attachment_urls 정리"""
    print("\n" + "="*70)
    print("🧹 BizInfo attachment_urls 정리")
    print("="*70)
    
    # 모든 attachment_urls가 있는 레코드 가져오기
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
    
    print(f"✅ BizInfo {len(all_data)}개 레코드 로드")
    
    fixed_count = 0
    
    for record in all_data:
        pblanc_id = record['pblanc_id']
        attachments = record.get('attachment_urls')
        
        if isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except:
                continue
        
        if not isinstance(attachments, list):
            continue
        
        needs_cleaning = False
        cleaned_urls = []
        
        for att in attachments:
            if isinstance(att, dict):
                # 이미 깨끗한 형식
                if list(att.keys()) == ['url']:
                    cleaned_urls.append(att)
                # 잘못된 형식
                else:
                    needs_cleaning = True
                    # download_url 우선
                    if 'download_url' in att:
                        cleaned_urls.append({'url': att['download_url']})
                    # url 필드
                    elif 'url' in att:
                        cleaned_urls.append({'url': att['url']})
                    # file_id로 URL 생성
                    elif 'file_id' in att:
                        file_id = att['file_id']
                        if file_id.startswith('getImageFile.do'):
                            url_str = f"https://www.bizinfo.go.kr/cmm/fms/{file_id}"
                        elif file_id.startswith('FILE_'):
                            url_str = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={file_id}"
                        else:
                            url_str = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?{file_id}"
                        cleaned_urls.append({'url': url_str})
            elif isinstance(att, str):
                # 문자열인 경우 그대로 URL로 사용
                needs_cleaning = True
                cleaned_urls.append({'url': att})
        
        if needs_cleaning and cleaned_urls:
            try:
                # 중복 제거
                seen_urls = set()
                unique_urls = []
                for item in cleaned_urls:
                    if item['url'] not in seen_urls:
                        seen_urls.add(item['url'])
                        unique_urls.append(item)
                
                # 업데이트
                result = supabase.table('bizinfo_complete')\
                    .update({'attachment_urls': unique_urls})\
                    .eq('pblanc_id', pblanc_id)\
                    .execute()
                
                if result.data:
                    fixed_count += 1
                    if fixed_count % 50 == 0:
                        print(f"  처리 중... {fixed_count}개 완료")
            except:
                pass
    
    print(f"✅ BizInfo 정리 완료: {fixed_count}개")
    return fixed_count

def main():
    """메인 실행"""
    print("="*70)
    print("🧹 전체 attachment_urls 정리 - URL만 남기기")
    print("="*70)
    
    # K-Startup 정리
    kstartup_fixed = clean_kstartup()
    
    # BizInfo 정리
    bizinfo_fixed = clean_bizinfo()
    
    print("\n" + "="*70)
    print("📊 전체 정리 완료")
    print("="*70)
    print(f"✅ K-Startup: {kstartup_fixed}개 정리")
    print(f"✅ BizInfo: {bizinfo_fixed}개 정리")
    print(f"✅ 총합: {kstartup_fixed + bizinfo_fixed}개 정리")
    print("\n🎯 결과:")
    print("  - 모든 attachment_urls가 {'url': '...'} 형식으로 통일")
    print("  - 다운로드 URL만 저장")
    print("  - 불필요한 필드 모두 제거")
    print("="*70)

if __name__ == "__main__":
    main()