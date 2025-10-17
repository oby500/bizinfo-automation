#!/usr/bin/env python3
"""
BizInfo 첨부파일 URL 수집 - URL만 수집 (K-Startup 방식과 동일)
- 첨부파일 URL만 수집
- 파일명과 타입 정보는 다운로드 시 HTTP 헤더에서 추출
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
from urllib.parse import urljoin

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

lock = threading.Lock()
progress = {
    'success': 0, 
    'error': 0, 
    'total': 0,
    'new_files': 0
}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.bizinfo.go.kr/'
})

def extract_attachment_urls_only(detail_url):
    """BizInfo 첨부파일 URL만 추출 - 순수 URL만 (K-Startup 방식과 동일)"""
    all_urls = []

    try:
        response = session.get(detail_url, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # getImageFile.do href 패턴 - BizInfo의 실제 다운로드 URL
        # 예: /cmm/fms/getImageFile.do;jsessionid=...?atchFileId=FILE_XXX&fileSn=0
        getImageFile_links = soup.find_all('a', href=re.compile(r'getImageFile\.do', re.IGNORECASE))

        for link in getImageFile_links:
            href = link.get('href', '')
            if not href or href == '#':
                continue

            # JSESSIONID 제거 (세션 만료 방지)
            if ';jsessionid=' in href:
                # JSESSIONID 이전 부분 + 파라미터 부분만 추출
                before_session = href.split(';jsessionid=')[0]
                after_session = href.split(';jsessionid=')[1]

                # 파라미터가 있으면 보존
                if '?' in after_session:
                    params = '?' + after_session.split('?', 1)[1]
                    href = before_session + params
                else:
                    href = before_session

            # 파라미터 확인 - atchFileId가 있어야 유효한 다운로드 URL
            if 'atchFileId=' not in href:
                continue

            # 절대 URL로 변환
            if href.startswith('/'):
                url = f"https://www.bizinfo.go.kr{href}"
            elif href.startswith('http'):
                url = href
            else:
                url = f"https://www.bizinfo.go.kr/{href}"

            # URL만 저장 (K-Startup과 동일한 형식)
            all_urls.append({'url': url})

    except Exception as e:
        print(f"    오류 발생: {str(e)[:100]}")
        return []

    # 중복 제거
    seen_urls = set()
    unique_urls = []
    for item in all_urls:
        if item['url'] not in seen_urls:
            seen_urls.add(item['url'])
            unique_urls.append(item)

    return unique_urls

def process_record(record):
    """레코드 처리 - URL만 수집"""
    try:
        pblanc_id = record['pblanc_id']
        title = record.get('pblanc_nm', '')
        detail_url = record.get('detail_url') or record.get('dtl_url')
        
        if not detail_url:
            return False
        
        print(f"처리 중: {pblanc_id} - {title[:50]}...")
        
        # 첨부파일 URL만 추출
        attachments = extract_attachment_urls_only(detail_url)
        
        if attachments:
            # 데이터베이스 업데이트 - URL만 저장
            result = supabase.table('bizinfo_complete')\
                .update({
                    'attachment_urls': attachments
                })\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['new_files'] += len(attachments)
                print(f"   {len(attachments)}개 URL 수집 완료")
                return True
        else:
            # 첨부파일이 없는 경우 빈 배열로 저장
            result = supabase.table('bizinfo_complete')\
                .update({
                    'attachment_urls': []
                })\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                print(f"   첨부파일 없음 (빈 배열 저장)")
                return True
        
        with lock:
            progress['error'] += 1
        return False
        
    except Exception as e:
        print(f"   오류: {str(e)}")
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행"""
    print("="*70)
    print(" BizInfo 첨부파일 URL 수집 (순수 URL만)")
    print("="*70)
    
    # 처리 제한 확인 - 기본값 200개
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '200'))
    
    # 전체 데이터 로드
    print("데이터 로딩 중...")
    all_data = []
    offset = 0
    page_size = 1000
    
    while True:
        batch = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, detail_url, dtl_url, attachment_urls, created_at')\
            .range(offset, offset + page_size - 1)\
            .execute()
        
        if not batch.data:
            break
            
        all_data.extend(batch.data)
        print(f"  로딩: {len(all_data)}개...")
        
        if len(batch.data) < page_size:
            break
        offset += page_size
    
    print(f" 전체 데이터: {len(all_data)}개")
    
    needs_processing = []
    
    for record in all_data:
        # URL이 있는지 확인
        detail_url = record.get('detail_url') or record.get('dtl_url')
        if not detail_url:
            continue

        # 첨부파일 정보 확인
        attachment_urls = record.get('attachment_urls')

        # 다음 경우에 재처리:
        # 1. NULL인 경우
        # 2. 빈 배열인 경우
        # 3. 잘못된 URL 패턴 (/webapp/upload/)인 경우
        needs_reprocess = False

        if attachment_urls is None or attachment_urls == []:
            needs_reprocess = True
        elif isinstance(attachment_urls, list) and len(attachment_urls) > 0:
            # 첫 번째 URL 확인
            first_url = attachment_urls[0].get('url', '') if isinstance(attachment_urls[0], dict) else str(attachment_urls[0])
            # 잘못된 패턴 확인
            if '/webapp/upload/' in first_url:
                needs_reprocess = True

        if needs_reprocess:
            needs_processing.append(record)
    
    # 처리 제한 적용 (최신 데이터 우선)
    if processing_limit > 0 and len(needs_processing) > processing_limit:
        # 최신 데이터부터 처리하도록 정렬
        needs_processing.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        needs_processing = needs_processing[:processing_limit]
        print(f" 제한 모드: 최대 {processing_limit}개만 처리 (최신 데이터 우선)")
    
    progress['total'] = len(needs_processing)
    
    print(f" 검토 대상: {len(all_data)}개")
    print(f" 처리 필요: {progress['total']}개")
    
    if progress['total'] == 0:
        print(" 모든 레코드가 이미 정상 처리되었습니다!")
        return
    
    print(f" {progress['total']}개 처리 시작 (20 workers)...\n")
    
    # 병렬 처리
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_record, record): record for record in needs_processing}
        
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                if i % 50 == 0:
                    print(f"진행: {i}/{progress['total']} | 성공: {progress['success']} | URL: {progress['new_files']}개")
            except:
                pass
    
    # 결과 출력
    print("\n" + "="*70)
    print(" BizInfo 첨부파일 수집 완료")
    print("="*70)
    print(f" 처리 완료: {progress['success']}/{progress['total']}")
    print(f" 수집된 URL: {progress['new_files']}개")
    print(f" 첨부파일 없음: 빈 배열 []로 저장됨")
    print("\n 개선사항:")
    print("  - 순수 다운로드 URL만 저장")
    print("  - 타입, 파일명 등 불필요한 정보 전부 제거")
    print("  - K-Startup과 동일한 방식")
    print("  - 최신 데이터 우선 처리")
    print("="*70)

if __name__ == "__main__":
    main()