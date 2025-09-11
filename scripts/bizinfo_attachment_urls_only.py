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
    """BizInfo 첨부파일 URL만 추출 - 순수 URL만"""
    all_urls = []
    
    try:
        response = session.get(detail_url, timeout=15)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. onclick 패턴들 (fnFileDown, fileLoad, fileBlank)
        onclick_links = soup.find_all('a', onclick=True)
        
        for link in onclick_links:
            onclick = link.get('onclick', '')
            
            # fnFileDown 패턴: fnFileDown('파일ID')
            if 'fnFileDown' in onclick:
                match = re.search(r"fnFileDown\('([^']+)'", onclick)
                if match:
                    file_id = match.group(1)
                    # 실제 다운로드 URL 형식
                    url = f"https://www.bizinfo.go.kr/webapp/download.do?file_id={file_id}"
                    all_urls.append({'url': url})
            
            # fileLoad/fileBlank 패턴: fileLoad('/path/to/file.pdf', ...)
            elif 'fileLoad' in onclick or 'fileBlank' in onclick:
                # 첫 번째 파라미터가 파일 경로
                match = re.search(r"(fileLoad|fileBlank)\s*\(\s*'([^']+)'", onclick)
                if match:
                    file_path = match.group(2)
                    # 경로가 /로 시작하면 그대로, 아니면 /webapp/upload/ 추가
                    if file_path.startswith('/'):
                        url = f"https://www.bizinfo.go.kr{file_path}"
                    else:
                        url = f"https://www.bizinfo.go.kr/webapp/upload/{file_path}"
                    all_urls.append({'url': url})
                else:
                    # 문자열 조합 패턴 처리: '/path' + '/' + 'filename.pdf'
                    parts = re.findall(r"'([^']+)'", onclick)
                    if parts and len(parts) >= 2:
                        # 파일 경로 조합
                        file_path = ''.join(parts[:3] if len(parts) >= 3 else parts)
                        if file_path:
                            url = f"https://www.bizinfo.go.kr{file_path}"
                            all_urls.append({'url': url})
        
        # 2. href 직접 링크 패턴
        href_patterns = [
            r'/webapp/download\.do',
            r'/webapp/upload/',
            r'/down\.jsp',
            r'/download/',
            r'\.hwp$',
            r'\.pdf$',
            r'\.zip$',
            r'\.doc[x]?$',
            r'\.xls[x]?$'
        ]
        
        for pattern in href_patterns:
            links = soup.find_all('a', href=re.compile(pattern, re.IGNORECASE))
            for link in links:
                href = link.get('href', '')
                if href and href != '#':
                    if href.startswith('/'):
                        url = f"https://www.bizinfo.go.kr{href}"
                    elif href.startswith('http'):
                        url = href
                    else:
                        url = f"https://www.bizinfo.go.kr/{href}"
                    all_urls.append({'url': url})
        
        # 3. class="fileDown" 링크들
        file_down_links = soup.find_all('a', class_='fileDown')
        for link in file_down_links:
            href = link.get('href', '')
            if href and href != '#' and href != 'javascript:void(0);':
                if href.startswith('/'):
                    url = f"https://www.bizinfo.go.kr{href}"
                elif href.startswith('http'):
                    url = href
                else:
                    continue
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
                print(f"  ✅ {len(attachments)}개 URL 수집 완료")
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
    print("📎 BizInfo 첨부파일 URL 수집 (순수 URL만)")
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
    
    print(f"📌 전체 데이터: {len(all_data)}개")
    
    needs_processing = []
    
    for record in all_data:
        # URL이 있는지 확인
        detail_url = record.get('detail_url') or record.get('dtl_url')
        if not detail_url:
            continue
        
        # 첨부파일 정보 확인
        attachment_urls = record.get('attachment_urls')
        
        # NULL이거나 빈 배열인 경우 항상 재처리
        if attachment_urls is None or attachment_urls == []:
            needs_processing.append(record)
    
    # 처리 제한 적용 (최신 데이터 우선)
    if processing_limit > 0 and len(needs_processing) > processing_limit:
        # 최신 데이터부터 처리하도록 정렬
        needs_processing.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        needs_processing = needs_processing[:processing_limit]
        print(f"📌 제한 모드: 최대 {processing_limit}개만 처리 (최신 데이터 우선)")
    
    progress['total'] = len(needs_processing)
    
    print(f"✅ 검토 대상: {len(all_data)}개")
    print(f"📎 처리 필요: {progress['total']}개")
    
    if progress['total'] == 0:
        print("🎉 모든 레코드가 이미 정상 처리되었습니다!")
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
    print("📊 BizInfo 첨부파일 수집 완료")
    print("="*70)
    print(f"✅ 처리 완료: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 URL: {progress['new_files']}개")
    print(f"📝 첨부파일 없음: 빈 배열 []로 저장됨")
    print("\n🔧 개선사항:")
    print("  - 순수 다운로드 URL만 저장")
    print("  - 타입, 파일명 등 불필요한 정보 전부 제거")
    print("  - K-Startup과 동일한 방식")
    print("  - 최신 데이터 우선 처리")
    print("="*70)

if __name__ == "__main__":
    main()