#!/usr/bin/env python3
"""
K-Startup 첨부파일 URL 수집 - 개선된 버전
- BizInfo와 일관된 구조로 개선
- 더 체계적인 URL 패턴 감지
- 향상된 오류 처리 및 로깅
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
import time
import json

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL', 'https://csuziaogycciwgxxmahm.supabase.co')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')

if not key:
    key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzdXppYW9neWNjaXdneHhtYWhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYxNTc4MCwiZXhwIjoyMDY5MTkxNzgwfQ.HnhM7zSLzi7lHVPd2IVQKIACDq_YA05mBMgZbSN1c9Q'

supabase = create_client(url, key)

lock = threading.Lock()
progress = {
    'success': 0, 
    'error': 0, 
    'total': 0,
    'new_files': 0,
    'no_attachments': 0,
    'patterns_found': {}
}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.k-startup.go.kr/'
})

def extract_kstartup_attachments(detail_url, announcement_id=None, title=None):
    """K-Startup 첨부파일 URL 추출 - 개선된 버전"""
    all_attachments = []
    debug_info = {
        'url_tried': [],
        'patterns_found': [],
        'error_messages': []
    }
    
    # pbanc_sn 추출
    pbanc_sn = None
    if 'pbancSn=' in detail_url:
        match = re.search(r'pbancSn=(\d+)', detail_url)
        if match:
            pbanc_sn = match.group(1)
    
    if not pbanc_sn:
        debug_info['error_messages'].append('pbancSn not found in URL')
        return [], debug_info
    
    # URL 변형 패턴 생성 (ongoing <-> deadline)
    url_variations = [detail_url]
    
    if 'bizpbanc-ongoing.do' in detail_url:
        deadline_url = detail_url.replace('bizpbanc-ongoing.do', 'bizpbanc-deadline.do')
        deadline_url = deadline_url.replace('pbancClssCd=PBC010', 'pbancClssCd=PBC020')
        url_variations.append(deadline_url)
    elif 'bizpbanc-deadline.do' in detail_url:
        ongoing_url = detail_url.replace('bizpbanc-deadline.do', 'bizpbanc-ongoing.do')
        ongoing_url = ongoing_url.replace('pbancClssCd=PBC020', 'pbancClssCd=PBC010')
        url_variations.append(ongoing_url)
    
    # 각 URL 변형 시도
    for attempt_url in url_variations:
        debug_info['url_tried'].append(attempt_url)
        
        try:
            response = session.get(attempt_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            page_attachments = []
            
            # === 패턴 1: 직접 다운로드 링크 ===
            # /afile/fileDownload/ 형식의 직접 링크
            direct_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
            for link in direct_links:
                href = link.get('href', '')
                if href:
                    full_url = urljoin('https://www.k-startup.go.kr', href)
                    file_info = {
                        'url': full_url,
                        'pattern': 'direct_link',
                        'text': link.get_text(strip=True)
                    }
                    page_attachments.append(file_info)
                    debug_info['patterns_found'].append('direct_link')
            
            # === 패턴 2: JavaScript onclick 함수 ===
            # fileDownBySn 함수 호출 패턴
            onclick_links = soup.find_all('a', onclick=re.compile(r'fileDownBySn'))
            for link in onclick_links:
                onclick = link.get('onclick', '')
                match = re.search(r"fileDownBySn\(\s*'(\d+)'\s*,\s*'(\d+)'\s*\)", onclick)
                if match:
                    file_sn = match.group(1)
                    file_seq = match.group(2)
                    download_url = f'https://www.k-startup.go.kr/afile/fileDownload/{pbanc_sn}/{file_sn}/{file_seq}'
                    file_info = {
                        'url': download_url,
                        'pattern': 'onclick_fileDownBySn',
                        'text': link.get_text(strip=True)
                    }
                    page_attachments.append(file_info)
                    debug_info['patterns_found'].append('onclick_fileDownBySn')
            
            # === 패턴 3: 첨부파일 섹션/테이블 ===
            # 첨부파일이 포함된 테이블 찾기
            attachment_sections = []
            
            # 3-1: table_view 클래스
            attachment_sections.extend(soup.find_all('table', class_='table_view'))
            
            # 3-2: 첨부파일 관련 헤더 찾기
            for header in soup.find_all(['h3', 'h4', 'th'], string=re.compile(r'첨부파일|첨부문서|붙임')):
                parent = header.find_parent(['table', 'div'])
                if parent and parent not in attachment_sections:
                    attachment_sections.append(parent)
            
            # 3-3: file 관련 클래스나 ID
            file_containers = soup.find_all(['div', 'td'], class_=re.compile(r'file|attach'))
            attachment_sections.extend(file_containers)
            
            # 섹션 내 링크 검색
            for section in attachment_sections:
                links = section.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # 파일 다운로드 관련 URL 패턴
                    if any(pattern in href for pattern in ['/afile/', 'download', 'file', '.hwp', '.pdf', '.xlsx', '.docx', '.zip']):
                        full_url = urljoin('https://www.k-startup.go.kr', href)
                        file_info = {
                            'url': full_url,
                            'pattern': 'attachment_section',
                            'text': text
                        }
                        page_attachments.append(file_info)
                        debug_info['patterns_found'].append('attachment_section')
            
            # === 패턴 4: 파일 아이콘과 연결된 링크 ===
            # 파일 아이콘이나 다운로드 아이콘 옆의 링크
            file_icons = soup.find_all('img', src=re.compile(r'(file|download|attach|icon)'))
            for icon in file_icons:
                parent_link = icon.find_parent('a')
                if parent_link and parent_link.get('href'):
                    href = parent_link.get('href')
                    full_url = urljoin('https://www.k-startup.go.kr', href)
                    file_info = {
                        'url': full_url,
                        'pattern': 'file_icon_link',
                        'text': parent_link.get_text(strip=True)
                    }
                    page_attachments.append(file_info)
                    debug_info['patterns_found'].append('file_icon_link')
            
            # 중복 제거 (URL 기준)
            seen_urls = set()
            unique_attachments = []
            for att in page_attachments:
                if att['url'] not in seen_urls:
                    seen_urls.add(att['url'])
                    unique_attachments.append({'url': att['url']})  # URL만 저장
                    
                    # 패턴 통계
                    pattern = att.get('pattern', 'unknown')
                    with lock:
                        if pattern not in progress['patterns_found']:
                            progress['patterns_found'][pattern] = 0
                        progress['patterns_found'][pattern] += 1
            
            if unique_attachments:
                all_attachments = unique_attachments
                print(f"    ✅ {len(unique_attachments)}개 첨부파일 발견 ({attempt_url[:50]}...)")
                break  # 첨부파일을 찾았으면 중단
                
        except requests.RequestException as e:
            debug_info['error_messages'].append(f"Request failed for {attempt_url}: {str(e)}")
            continue
        except Exception as e:
            debug_info['error_messages'].append(f"Unexpected error for {attempt_url}: {str(e)}")
            continue
    
    return all_attachments, debug_info

def process_record(record):
    """레코드 처리 - 개선된 버전"""
    try:
        announcement_id = record['announcement_id']
        title = record.get('biz_pbanc_nm', '')
        page_url = record.get('detl_pg_url', '')
        
        if not page_url:
            with lock:
                progress['error'] += 1
            return False
        
        print(f"\n처리 중: {announcement_id} - {title[:50]}...")
        
        # 첨부파일 추출
        attachments, debug_info = extract_kstartup_attachments(page_url, announcement_id, title)
        
        # 디버그 정보 출력 (문제 발생 시)
        if not attachments and debug_info['error_messages']:
            print(f"  ⚠️ 디버그 정보:")
            for msg in debug_info['error_messages'][:2]:  # 처음 2개만 출력
                print(f"     - {msg}")
        
        # 데이터베이스 업데이트 - URL만 저장
        update_data = {
            'attachment_urls': attachments
        }
        
        result = supabase.table('kstartup_complete')\
            .update(update_data)\
            .eq('announcement_id', announcement_id)\
            .execute()
        
        if result.data:
            with lock:
                progress['success'] += 1
                if attachments:
                    progress['new_files'] += len(attachments)
                    print(f"  ✅ {len(attachments)}개 URL 수집 완료")
                else:
                    progress['no_attachments'] += 1
                    print(f"  📝 첨부파일 없음")
            return True
        else:
            with lock:
                progress['error'] += 1
            return False
            
    except Exception as e:
        print(f"  ❌ 오류: {str(e)}")
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("K-Startup 첨부파일 URL 수집 시작 (개선된 버전)")
    print("=" * 80)
    
    # 처리할 레코드 조회
    print("\n처리할 공고 조회 중...")
    
    # attachment_urls가 null이거나 빈 배열인 레코드 조회
    result = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, detl_pg_url')\
        .or_('attachment_urls.is.null,attachment_urls.eq.[]')\
        .limit(100)\
        .execute()
    
    records = result.data if result.data else []
    
    if not records:
        print("처리할 공고가 없습니다.")
        return
    
    progress['total'] = len(records)
    print(f"총 {len(records)}개 공고 처리 예정\n")
    
    # 병렬 처리
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_record, record) for record in records]
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"처리 중 오류: {e}")
    
    # 결과 출력
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("처리 완료!")
    print("=" * 80)
    print(f"✅ 성공: {progress['success']}개")
    print(f"❌ 실패: {progress['error']}개")
    print(f"📁 수집된 첨부파일 URL: {progress['new_files']}개")
    print(f"📝 첨부파일 없음: {progress['no_attachments']}개")
    print(f"⏱️ 소요 시간: {elapsed_time:.2f}초")
    
    if progress['patterns_found']:
        print("\n📊 발견된 패턴 통계:")
        for pattern, count in progress['patterns_found'].items():
            print(f"  - {pattern}: {count}개")
    
    print("\n완료!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n작업이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()