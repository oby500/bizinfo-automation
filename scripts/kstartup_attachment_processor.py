#!/usr/bin/env python3
"""
K-Startup 첨부파일 처리 스크립트 (워크플로우 호환)
- /afile/fileDownload/ 패턴 사용
- 병렬 처리로 고속 수집
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client
from dotenv import load_dotenv
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

lock = threading.Lock()
progress = {'success': 0, 'error': 0, 'total': 0, 'new_files': 0}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.k-startup.go.kr/'
})

def extract_attachments_correctly(page_url, announcement_id):
    """K-Startup 첨부파일 정확하게 추출"""
    all_attachments = []
    
    # pbanc_sn 추출
    if 'pbancSn=' in page_url:
        pbanc_sn = re.search(r'pbancSn=(\d+)', page_url).group(1)
    else:
        pbanc_sn = announcement_id.replace('KS_', '') if announcement_id.startswith('KS_') else announcement_id
    
    # ongoing과 deadline 모두 시도
    urls_to_try = [
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}',
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?schM=view&pbancSn={pbanc_sn}',
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?pbancClssCd=PBC010&schM=view&pbancSn={pbanc_sn}',
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?pbancClssCd=PBC010&schM=view&pbancSn={pbanc_sn}'
    ]
    
    for try_url in urls_to_try:
        try:
            response = session.get(try_url, timeout=15)
            if response.status_code != 200:
                continue
                
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            attachments = []
            
            # 1. /afile/fileDownload/ 패턴 (가장 정확한 방법)
            download_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
            
            for link in download_links:
                href = link.get('href', '')
                text = link.get_text(strip=True) or ''
                
                # 전체 URL 생성
                full_url = urljoin(try_url, href)
                
                # 파일명 추출
                filename = text
                if not filename or filename == '다운로드':
                    # href에서 파일 ID 추출
                    file_id_match = re.search(r'/afile/fileDownload/([^/\?]+)', href)
                    if file_id_match:
                        file_id = file_id_match.group(1)
                        filename = f"첨부파일_{file_id}"
                    else:
                        filename = f"첨부파일_{len(attachments)+1}"
                
                attachment = {
                    'url': full_url,
                    'text': filename,
                    'type': 'FILE',
                    'params': {},
                    'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",
                    'display_filename': filename,
                    'original_filename': filename
                }
                
                attachments.append(attachment)
            
            # 2. JavaScript onclick 패턴에서 fileDownload 함수 호출 찾기
            elements_with_onclick = soup.find_all(attrs={'onclick': re.compile(r'fileDownload|fnFileDown|fnDownload')})
            
            for elem in elements_with_onclick:
                onclick = elem.get('onclick', '')
                
                # fileDownload('파일ID') 패턴
                matches = re.findall(r"(?:fileDownload|fnFileDown|fnDownload)\s*\(\s*['\"]([^'\"]+)['\"]", onclick)
                for file_id in matches:
                    # /afile/fileDownload/ URL 생성
                    full_url = f'https://www.k-startup.go.kr/afile/fileDownload/{file_id}'
                    
                    text = elem.get_text(strip=True) or f'첨부파일_{file_id}'
                    
                    attachment = {
                        'url': full_url,
                        'text': text,
                        'type': 'FILE',
                        'params': {},
                        'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",
                        'display_filename': text,
                        'original_filename': text
                    }
                    
                    # URL 중복 체크
                    if not any(att['url'] == attachment['url'] for att in attachments):
                        attachments.append(attachment)
            
            if attachments:
                all_attachments.extend(attachments)
                
        except Exception as e:
            continue
    
    # 중복 제거
    unique_attachments = []
    seen_urls = set()
    for att in all_attachments:
        if att['url'] not in seen_urls:
            seen_urls.add(att['url'])
            unique_attachments.append(att)
    
    return unique_attachments

def process_record(record):
    """레코드 처리"""
    announcement_id = record['announcement_id']
    detl_pg_url = record.get('detl_pg_url')
    
    if not detl_pg_url:
        pbanc_sn = announcement_id.replace('KS_', '') if announcement_id.startswith('KS_') else announcement_id
        detl_pg_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}'
    
    try:
        attachments = extract_attachments_correctly(detl_pg_url, announcement_id)
        
        if attachments:
            update_data = {
                'attachment_urls': attachments,
                'attachment_count': len(attachments)
            }
            
            result = supabase.table('kstartup_complete')\
                .update(update_data)\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['new_files'] += len(attachments)
                return True
        
        with lock:
            progress['error'] += 1
        return False
        
    except Exception as e:
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행"""
    print("="*70)
    print("📎 K-Startup 첨부파일 수집 (/afile/fileDownload/ 패턴)")
    print("="*70)
    
    # attachment_count가 0인 레코드들
    no_attach = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, detl_pg_url')\
        .eq('attachment_count', 0)\
        .execute()
    
    progress['total'] = len(no_attach.data) if no_attach.data else 0
    
    print(f"✅ 처리 대상: {progress['total']}개 (첨부파일 없는 레코드)")
    
    if progress['total'] == 0:
        print("🎉 모든 레코드가 첨부파일을 가지고 있습니다!")
        return
    
    print(f"🔥 병렬 처리 시작 (20 workers)...\n")
    
    # ThreadPoolExecutor로 병렬 처리
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_record, record): record for record in no_attach.data}
        
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                if i % 50 == 0:
                    print(f"   진행: {i}/{progress['total']} | 첨부파일: {progress['new_files']}개")
            except:
                pass
    
    # 최종 결과
    print("\n" + "="*70)
    print("📊 처리 결과")
    print("="*70)
    print(f"✅ 성공: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 첨부파일: {progress['new_files']}개")
    print(f"❌ 실패: {progress['error']}/{progress['total']}")
    
    if progress['new_files'] > 0:
        print(f"\n🎉 {progress['new_files']}개의 첨부파일을 성공적으로 수집했습니다!")

if __name__ == "__main__":
    main()