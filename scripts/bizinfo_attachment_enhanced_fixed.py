#!/usr/bin/env python3
"""
BizInfo 첨부파일 URL 수집 - URL만 수집
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
from urllib.parse import urljoin, unquote, urlparse, parse_qs
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


def extract_bizinfo_attachments(detail_url, pblanc_id, announcement_title=None):
    """BizInfo 첨부파일 추출"""
    all_attachments = []
    
    try:
        response = session.get(detail_url, timeout=15)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # BizInfo 첨부파일 패턴 찾기
        # 1. .fileDown 클래스 링크들
        file_links = soup.find_all('a', class_='fileDown')
        
        # 2. onclick="javascript:fnFileDown" 패턴
        if not file_links:
            file_links = soup.find_all('a', onclick=re.compile(r'fnFileDown'))
        
        # 3. fileLoad, fileBlank 패턴 (새로운 패턴)
        if not file_links:
            file_links = soup.find_all('a', onclick=re.compile(r'(fileLoad|fileBlank)'))
        
        # 4. 일반 파일 다운로드 링크 (href="/jsp/down.jsp" 등)
        if not file_links:
            file_links = soup.find_all('a', href=re.compile(r'(down\.jsp|download|file|getImageFile)'))
        
        attachments = []
        
        for idx, link in enumerate(file_links, 1):
            href = link.get('href', '')
            text = link.get_text(strip=True) or ''
            onclick = link.get('onclick', '')
            
            # URL 결정
            full_url = None
            if href and href.startswith('/'):
                full_url = urljoin('https://www.bizinfo.go.kr', href)
            elif href and href.startswith('http'):
                full_url = href
            elif onclick:
                # onclick에서 파일 정보 추출
                if 'fnFileDown' in onclick:
                    match = re.search(r"fnFileDown\('([^']+)'", onclick)
                    if match:
                        file_param = match.group(1)
                        full_url = f"https://www.bizinfo.go.kr/jsp/down.jsp?file={file_param}"
                elif 'fileLoad' in onclick or 'fileBlank' in onclick:
                    # fileLoad('/webapp/upload/bizinfo/file/2025/09' + '/' + '202509101035440192.pdf', ...
                    match = re.search(r"(fileLoad|fileBlank)\(([^)]+)\)", onclick)
                    if match:
                        params = match.group(2)
                        # 경로 조합 - 첫 3개 문자열 조합
                        path_parts = re.findall(r"'([^']+)'", params)
                        if path_parts:
                            file_path = ''.join(path_parts[:3] if len(path_parts) >= 3 else path_parts)
                            full_url = f"https://www.bizinfo.go.kr{file_path}"
            
            if not full_url:
                continue
            
            # URL만 저장 (파일명과 타입 정보는 다운로드 시 HTTP 헤더에서 추출)
            attachment = {
                'url': full_url
            }
            
            attachments.append(attachment)
        
        all_attachments.extend(attachments)
        
    except Exception as e:
        pass
    
    # 중복 제거
    unique_attachments = []
    seen_urls = set()
    for att in all_attachments:
        if att['url'] not in seen_urls:
            seen_urls.add(att['url'])
            unique_attachments.append(att)
    
    return unique_attachments

def process_bizinfo_record(record):
    """BizInfo 레코드 처리"""
    pblanc_id = record['pblanc_id']
    detail_url = record.get('detail_url') or record.get('dtl_url')
    title = record.get('pblanc_nm') or record.get('bsns_title', '')
    
    if not detail_url:
        with lock:
            progress['error'] += 1
        return False
    
    try:
        attachments = extract_bizinfo_attachments(detail_url, pblanc_id, title)
        
        if attachments:
            # 첨부파일이 있는 경우 저장
            result = supabase.table('bizinfo_complete')\
                .update({'attachment_urls': attachments})\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['new_files'] += len(attachments)
                print(f"  ✅ {len(attachments)}개 URL 수집 완료")
                return True
        else:
            # 첨부파일이 없는 경우 빈 배열로 저장
            result = supabase.table('bizinfo_complete')\
                .update({'attachment_urls': []})\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                print(f"  📝 첨부파일 없음 (빈 배열 저장)")
                return True
        
        with lock:
            progress['error'] += 1
        return False
        
    except Exception:
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행"""
    print("="*70)
    print("📎 BizInfo 첨부파일 URL 수집 (URL만)")
    print("="*70)
    
    # 처리 제한 확인 - 기본값 200개로 증가 (100% 수집 보장)
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '200'))
    
    # 처리 대상 조회 - 항상 전체 처리 (페이지네이션)
    all_data = []
    page_size = 1000
    offset = 0
    
    while True:
        batch = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, bsns_title, detail_url, dtl_url, attachment_urls')\
            .range(offset, offset + page_size - 1)\
            .execute()
        
        if not batch.data:
            break
            
        all_data.extend(batch.data)
        print(f"  로딩: {len(all_data)}개...")
        
        if len(batch.data) < page_size:
            break
        offset += page_size
    
    all_records = type('obj', (object,), {'data': all_data})()
    print(f"📌 Full 모드: 전체 데이터 처리 ({len(all_records.data)}개)")
    
    needs_processing = []
    
    for record in all_records.data:
        # 첨부파일 정보가 없는 경우만 처리 (NULL만 처리, 빈 배열은 이미 처리됨)
        attachment_urls = record.get('attachment_urls')
        detail_url = record.get('detail_url') or record.get('dtl_url')
        
        if not detail_url:
            continue  # URL이 없으면 처리 불가
            
        # NULL이거나 빈 배열인 경우 처리 (최근 데이터 첨부파일 재수집)
        # 또는 잘못된 형식의 attachment_urls도 재처리 (getImageFile, DOC, UNKNOWN 타입)
        if attachment_urls is None or attachment_urls == [] or \
           (isinstance(attachment_urls, list) and len(attachment_urls) > 0 and \
            any(att.get('type') in ['getImageFile', 'DOC', 'UNKNOWN', 'HTML'] for att in attachment_urls if isinstance(att, dict))):
            needs_processing.append(record)
    
    # 처리 제한 적용 (기본 200개)
    if processing_limit > 0 and len(needs_processing) > processing_limit:
        # 최신 데이터부터 처리하도록 정렬
        needs_processing.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        needs_processing = needs_processing[:processing_limit]
        print(f"📌 제한 모드: 최대 {processing_limit}개만 처리 (최신 데이터 우선)")
    
    progress['total'] = len(needs_processing)
    
    print(f"✅ 검토 대상: {len(all_records.data)}개")
    print(f"📎 처리 필요: {progress['total']}개")
    
    if progress['total'] == 0:
        print("🎉 모든 레코드가 이미 처리되었습니다!")
        return
    
    print(f"🔥 {progress['total']}개 처리 시작 (15 workers)...\n")
    
    # 병렬 처리 (안정성과 속도 균형을 위해 worker 수 최적화)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_bizinfo_record, record): record for record in needs_processing}
        
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                if i % 100 == 0:
                    print(f"진행: {i}/{progress['total']} | 성공: {progress['success']} | 파일: {progress['new_files']}개")
            except:
                pass
    
    # 결과 출력
    print("\n" + "="*70)
    print("📊 BizInfo 첨부파일 수집 완료")
    print("="*70)
    print(f"✅ 처리 완료: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 URL: {progress['new_files']}개")
    print(f"📝 첨부파일 없음: 빈 배열 []로 저장됨")
    print("\n🔧 개선사항:")
    print("  - NULL vs 빈 배열 명확히 구분")
    print("  - 첨부파일 없는 경우 빈 배열 []로 저장")
    print("  - 순수 다운로드 URL만 저장")
    print("="*70)

if __name__ == "__main__":
    main()