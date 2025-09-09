#!/usr/bin/env python3
"""
K-Startup 첨부파일 URL 수집 - URL만 수집
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
    'Referer': 'https://www.k-startup.go.kr/'
})

def extract_attachments_url_only(page_url):
    """K-Startup 첨부파일 URL만 추출 - 이중 URL 패턴 지원"""
    all_attachments = []
    
    # pbanc_sn 추출
    if 'pbancSn=' in page_url:
        pbanc_sn_match = re.search(r'pbancSn=(\d+)', page_url)
        if pbanc_sn_match:
            pbanc_sn = pbanc_sn_match.group(1)
        else:
            return []
    else:
        return []
    
    # K-Startup URL 패턴: 접수 진행중 vs 마감됨
    url_patterns = []
    
    # 원본 URL 먼저 시도
    url_patterns.append(page_url)
    
    # 만약 ongoing URL이면 deadline URL도 시도
    if 'bizpbanc-ongoing.do' in page_url:
        deadline_url = page_url.replace('bizpbanc-ongoing.do', 'bizpbanc-deadline.do')
        deadline_url = deadline_url.replace('pbancClssCd=PBC010', 'pbancClssCd=PBC020')
        url_patterns.append(deadline_url)
    
    # 만약 deadline URL이면 ongoing URL도 시도
    elif 'bizpbanc-deadline.do' in page_url:
        ongoing_url = page_url.replace('bizpbanc-deadline.do', 'bizpbanc-ongoing.do')
        ongoing_url = ongoing_url.replace('pbancClssCd=PBC020', 'pbancClssCd=PBC010')
        url_patterns.append(ongoing_url)
    
    # 각 URL 패턴 시도
    for attempt_url in url_patterns:
        try:
            # 페이지 접속
            response = session.get(attempt_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 방법 1: 직접 링크 찾기
            file_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
            for link in file_links:
                href = link.get('href')
                if href:
                    if href.startswith('/'):
                        full_url = 'https://www.k-startup.go.kr' + href
                    else:
                        full_url = href
                    
                    # URL만 저장
                    all_attachments.append({'url': full_url})
            
            # 방법 2: JavaScript onclick 파싱
            onclick_links = soup.find_all('a', onclick=re.compile(r'fileDownBySn'))
            for link in onclick_links:
                onclick = link.get('onclick', '')
                match = re.search(r"fileDownBySn\(\s*'(\d+)'\s*,\s*'(\d+)'\s*\)", onclick)
                if match:
                    file_sn = match.group(1)
                    file_seq = match.group(2)
                    download_url = f'https://www.k-startup.go.kr/afile/fileDownload/{pbanc_sn}/{file_sn}/{file_seq}'
                    
                    # URL만 저장
                    all_attachments.append({'url': download_url})
            
            # 방법 3: 첨부파일 테이블 파싱
            attachment_tables = soup.find_all('table', class_='table_view')
            for table in attachment_tables:
                rows = table.find_all('tr')
                for row in rows:
                    links = row.find_all('a')
                    for link in links:
                        href = link.get('href')
                        if href and '/afile/fileDownload/' in href:
                            if href.startswith('/'):
                                full_url = 'https://www.k-startup.go.kr' + href
                            else:
                                full_url = href
                            
                            # URL만 저장
                            all_attachments.append({'url': full_url})
            
            # 첨부파일을 찾았으면 더 이상 다른 URL 시도하지 않음
            if all_attachments:
                print(f"    첨부파일 발견: {attempt_url}")
                break
                
        except Exception as e:
            print(f"    URL 시도 실패 {attempt_url}: {str(e)}")
            continue
    
    # 중복 제거
    seen_urls = set()
    unique_attachments = []
    for att in all_attachments:
        if att['url'] not in seen_urls:
            seen_urls.add(att['url'])
            unique_attachments.append(att)
    
    return unique_attachments

def process_record(record):
    """레코드 처리 - URL만 수집"""
    try:
        announcement_id = record['announcement_id']
        title = record.get('biz_pbanc_nm', '')
        page_url = record.get('detl_pg_url', '')
        
        if not page_url:
            return False
        
        print(f"처리 중: {announcement_id} - {title[:50]}...")
        
        # 첨부파일 URL만 추출
        attachments = extract_attachments_url_only(page_url)
        
        if attachments:
            # 데이터베이스 업데이트 - URL만 저장
            result = supabase.table('kstartup_complete')\
                .update({
                    'attachment_urls': attachments
                })\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['new_files'] += len(attachments)
                print(f"  ✅ {len(attachments)}개 URL 수집 완료")
                return True
        else:
            # 첨부파일이 없는 경우 빈 배열로 저장
            result = supabase.table('kstartup_complete')\
                .update({
                    'attachment_urls': []
                })\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                print(f"  📝 첨부파일 없음 (빈 배열 저장)")
                return True
        
        with lock:
            progress['error'] += 1
        return False
        
    except Exception as e:
        print(f"  ❌ 오류: {str(e)}")
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행"""
    print("="*70)
    print("📎 K-Startup 첨부파일 URL 수집 (URL만)")
    print("="*70)
    
    # 처리 제한 확인 (환경변수로 받음)
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '0'))
    
    # 처리 대상 조회 - 첨부파일이 없거나 재처리가 필요한 것들
    if processing_limit > 0:
        # Daily 모드: 최근 N개만
        all_records = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm, detl_pg_url, attachment_urls')\
            .order('created_at', desc=True)\
            .limit(processing_limit * 2)\
            .execute()
        print(f"📌 Daily 모드: 최근 {processing_limit*2}개 중에서 처리 필요한 것만 선택")
    else:
        # Full 모드: 전체 - 1000개씩 나눠서 처리
        all_records = {'data': []}
        offset = 0
        batch_size = 1000
        
        while True:
            batch = supabase.table('kstartup_complete')\
                .select('announcement_id, biz_pbanc_nm, detl_pg_url, attachment_urls')\
                .range(offset, offset + batch_size - 1)\
                .execute()
            
            if not batch.data:
                break
                
            all_records['data'].extend(batch.data)
            
            if len(batch.data) < batch_size:
                break
                
            offset += batch_size
        
        print(f"📌 Full 모드: 전체 데이터 {len(all_records['data'])}개 처리")
    
    needs_processing = []
    
    # all_records가 dict인지 확인
    records_data = all_records['data'] if isinstance(all_records, dict) else all_records.data
    
    for record in records_data:
        # 첨부파일 정보가 없는 경우 재처리 (NULL만 처리, 빈 배열은 이미 처리됨)
        attachment_urls = record.get('attachment_urls')
        if attachment_urls is None:
            needs_processing.append(record)
    
    # Daily 모드에서는 최대 N개만 처리
    if processing_limit > 0 and len(needs_processing) > processing_limit:
        needs_processing = needs_processing[:processing_limit]
        print(f"📌 Daily 모드 제한: 최대 {processing_limit}개만 처리")
    
    progress['total'] = len(needs_processing)
    
    print(f"✅ 검토 대상: {len(records_data)}개")
    print(f"📎 처리 필요: {progress['total']}개")
    
    if progress['total'] == 0:
        print("🎉 모든 레코드가 이미 처리되었습니다!")
        return
    
    print(f"🔥 {progress['total']}개 처리 시작 (20 workers)...\n")
    
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
    print("📊 K-Startup 첨부파일 수집 완료")
    print("="*70)
    print(f"✅ 처리 완료: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 URL: {progress['new_files']}개")
    print(f"📝 첨부파일 없음: 빈 배열 []로 저장됨")
    print("\n🔧 개선사항:")
    print("  - 이중 URL 패턴 지원 (ongoing ↔ deadline 자동 변환)")
    print("  - 접수 마감 후에도 첨부파일 수집 가능")
    print("  - 첨부파일 없는 경우 빈 배열 []로 명확히 구분")
    print("  - 순수 다운로드 URL만 저장")
    print("="*70)

if __name__ == "__main__":
    main()