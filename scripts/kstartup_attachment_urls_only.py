#!/usr/bin/env python3
"""
K-Startup 첨부파일 URL만 수집 (BizInfo와 동일한 방식)
- URL만 수집
- 파일명과 타입은 수집하지 않음
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

# Supabase 설정 (SERVICE_KEY 우선 사용)
url = os.environ.get('SUPABASE_URL', 'https://csuziaogycciwgxxmahm.supabase.co')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')

# 키가 없으면 하드코딩된 값 사용
if not key:
    key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzdXppYW9neWNjaXdneHhtYWhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYxNTc4MCwiZXhwIjoyMDY5MTkxNzgwfQ.HnhM7zSLzi7lHVPd2IVQKIACDq_YA05mBMgZbSN1c9Q'

supabase = create_client(url, key)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.k-startup.go.kr/'
})

def extract_attachments_urls_only(page_url):
    """K-Startup 첨부파일 URL만 추출 (BizInfo 방식)"""
    all_urls = []
    
    # pbancSn 추출
    if 'pbancSn=' in page_url:
        pbanc_sn_match = re.search(r'pbancSn=([^&]+)', page_url)
        if pbanc_sn_match:
            pbanc_sn = pbanc_sn_match.group(1)
            # KS_ 접두사 제거
            pbanc_sn = pbanc_sn.replace('KS_', '')
        else:
            return []
    else:
        return []
    
    try:
        # 페이지 접속
        response = session.get(page_url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 다운로드 링크 찾기
        download_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
        
        for link in download_links:
            href = link.get('href')
            if href:
                # 파일 ID 추출
                file_id = href.split('/')[-1]
                
                # 다운로드 URL
                if href.startswith('/'):
                    download_url = 'https://www.k-startup.go.kr' + href
                else:
                    download_url = href
                
                # URL만 저장 (BizInfo 방식)
                if download_url not in all_urls:
                    all_urls.append(download_url)
                    print(f"    [URL 수집] {download_url}")
        
        # JavaScript onclick 방식도 확인
        onclick_links = soup.find_all('a', onclick=re.compile(r'fnPdfView'))
        for link in onclick_links:
            onclick = link.get('onclick', '')
            match = re.search(r"fnPdfView\('([^']+)'\)", onclick)
            if match:
                file_id = match.group(1)
                download_url = f'https://www.k-startup.go.kr/afile/fileDownload/{file_id}'
                
                # URL만 저장
                if download_url not in all_urls:
                    all_urls.append(download_url)
                    print(f"    [URL 수집] {download_url}")
        
    except Exception as e:
        print(f"  오류: {e}")
    
    return all_urls

def process_announcement(announcement):
    """공고 하나 처리"""
    announcement_id = announcement.get('announcement_id')
    
    # KS_ 제거
    numeric_id = announcement_id.replace('KS_', '') if announcement_id else None
    if not numeric_id:
        return None
    
    # 상세 페이지 URL 생성
    detail_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={numeric_id}'
    
    print(f"\n처리 중: {announcement_id} - {announcement.get('biz_pbanc_nm', 'N/A')[:30]}...")
    
    # 첨부파일 URL만 추출
    attachment_urls = extract_attachments_urls_only(detail_url)
    
    if attachment_urls:
        print(f"  → {len(attachment_urls)}개 URL 발견")
        
        # DB 업데이트 (URL 리스트만 저장)
        try:
            result = supabase.table('kstartup_complete').update({
                'attachment_urls': attachment_urls  # URL 리스트만 저장
            }).eq('announcement_id', announcement_id).execute()
            
            return {
                'announcement_id': announcement_id,
                'urls': attachment_urls,
                'status': 'success'
            }
        except Exception as e:
            print(f"  DB 업데이트 실패: {e}")
            return None
    else:
        print(f"  → 첨부파일 없음")
        
        # 첨부파일이 없어도 빈 배열로 저장
        try:
            result = supabase.table('kstartup_complete').update({
                'attachment_urls': []
            }).eq('announcement_id', announcement_id).execute()
        except:
            pass
            
        return None

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("K-Startup 첨부파일 URL 수집 (BizInfo 방식)")
    print("=" * 60)
    
    # 처리 제한 설정
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '10'))
    
    # 처리할 공고 조회 (첨부파일이 없거나 비어있는 것)
    try:
        query = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm, attachment_urls')
        
        if processing_limit > 0:
            query = query.limit(processing_limit)
        
        result = query.execute()
        
        if not result.data:
            print("처리할 공고가 없습니다.")
            return
        
        print(f"처리 대상: {len(result.data)}개 공고")
        
        # 병렬 처리
        success_count = 0
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(process_announcement, ann): ann 
                      for ann in result.data}
            
            for future in as_completed(futures):
                result = future.result()
                if result and result['status'] == 'success':
                    success_count += 1
        
        print("\n" + "=" * 60)
        print(f"완료: {success_count}개 공고 처리")
        print("=" * 60)
        
    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    main()