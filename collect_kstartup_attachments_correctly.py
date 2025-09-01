#!/usr/bin/env python3
"""
K-Startup 첨부파일 정확하게 수집
/afile/fileDownload/ 패턴 사용
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
import json

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

def detect_file_type_from_url(url, filename=''):
    """URL에서 실제 파일 타입 감지 (헤더 기반)"""
    try:
        # HEAD 요청으로 먼저 시도
        response = session.head(url, timeout=5)
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Content-Type으로 판단
        if 'pdf' in content_type:
            return 'PDF', 'pdf'
        elif 'image' in content_type:
            if 'png' in content_type:
                return 'IMAGE', 'png'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                return 'IMAGE', 'jpg'
            elif 'gif' in content_type:
                return 'IMAGE', 'gif'
            else:
                return 'IMAGE', 'img'
        elif 'zip' in content_type or 'x-zip' in content_type:
            return 'ZIP', 'zip'
        elif 'rar' in content_type or 'x-rar' in content_type:
            return 'ZIP', 'rar'
        elif 'excel' in content_type or 'spreadsheet' in content_type:
            return 'EXCEL', 'xlsx'
        elif 'word' in content_type or 'document' in content_type:
            return 'WORD', 'docx'
        elif 'powerpoint' in content_type or 'presentation' in content_type:
            return 'PPT', 'pptx'
        elif 'hwp' in content_type:
            return 'HWP', 'hwp'
        
        # Content-Disposition에서 파일명 추출 시도
        content_disp = response.headers.get('Content-Disposition', '')
        if 'filename=' in content_disp:
            import re
            filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disp)
            if filename_match:
                extracted_name = filename_match.group(1).strip('"\'')
                filename = extracted_name
        
    except:
        pass
    
    # 파일명 기반 판단
    if filename:
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        file_type = 'HWP' if file_ext == 'hwp' else \
                   'HWPX' if file_ext == 'hwpx' else \
                   'PDF' if file_ext == 'pdf' else \
                   'IMAGE' if file_ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp'] else \
                   'ZIP' if file_ext in ['zip', 'rar', '7z'] else \
                   'EXCEL' if file_ext in ['xls', 'xlsx'] else \
                   'WORD' if file_ext in ['doc', 'docx'] else \
                   'PPT' if file_ext in ['ppt', 'pptx'] else \
                   'FILE'
        return file_type, file_ext
    
    return 'FILE', ''

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
                onclick = link.get('onclick', '')
                
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
                
                # 헤더 기반 타입 감지 시도, 실패 시 파일명 기반
                file_type, file_ext = detect_file_type_from_url(full_url, filename)
                
                attachment = {
                    'url': full_url,
                    'text': filename,
                    'type': file_type,
                    'params': {},
                    'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",
                    'display_filename': filename,
                    'original_filename': filename,
                    'file_extension': file_ext
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
                    
                    # 헤더 기반 타입 감지 시도, 실패 시 파일명 기반
                    file_type, file_ext = detect_file_type_from_url(full_url, text)
                    
                    attachment = {
                        'url': full_url,
                        'text': text,
                        'type': file_type,
                        'params': {},
                        'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",
                        'display_filename': text,
                        'original_filename': text,
                        'file_extension': file_ext
                    }
                    
                    # URL 중복 체크
                    if not any(att['url'] == attachment['url'] for att in attachments):
                        attachments.append(attachment)
            
            # 3. content_wrap 영역 내 btn_wrap 찾기 (K-Startup 특정 패턴)
            content_wrap = soup.find('div', class_='content_wrap')
            if content_wrap:
                btn_wraps = content_wrap.find_all('div', class_='btn_wrap')
                for btn_wrap in btn_wraps:
                    btn_links = btn_wrap.find_all('a', href=True)
                    for link in btn_links:
                        href = link.get('href', '')
                        if '/afile/fileDownload/' in href:
                            full_url = urljoin(try_url, href)
                            text = link.get_text(strip=True) or '첨부파일'
                            
                            # 헤더 기반 타입 감지 시도, 실패 시 파일명 기반
                            file_type, file_ext = detect_file_type_from_url(full_url, text)
                            
                            attachment = {
                                'url': full_url,
                                'text': text,
                                'type': file_type,
                                'params': {},
                                'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",
                                'display_filename': text,
                                'original_filename': text,
                                'file_extension': file_ext
                            }
                            
                            if not any(att['url'] == attachment['url'] for att in attachments):
                                attachments.append(attachment)
            
            # 4. 테이블 내 첨부파일 (구형 페이지 대응)
            tables = soup.find_all('table')
            for table in tables:
                if '첨부' in table.get_text() or '파일' in table.get_text():
                    links = table.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        if any(p in href for p in ['/afile/', 'download', 'file']):
                            full_url = urljoin(try_url, href)
                            text = link.get_text(strip=True) or '첨부파일'
                            
                            # 헤더 기반 타입 감지 시도, 실패 시 파일명 기반
                            file_type, file_ext = detect_file_type_from_url(full_url, text)
                            
                            attachment = {
                                'url': full_url,
                                'text': text,
                                'type': file_type,
                                'params': {},
                                'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",
                                'display_filename': text,
                                'original_filename': text,
                                'file_extension': file_ext
                            }
                            
                            if not any(att['url'] == attachment['url'] for att in attachments):
                                attachments.append(attachment)
            
            if attachments:
                all_attachments.extend(attachments)
                # 파일 타입별 카운트
                type_counts = {}
                for att in attachments:
                    file_type = att.get('type', 'FILE')
                    type_counts[file_type] = type_counts.get(file_type, 0) + 1
                
                types_str = ', '.join([f"{k}:{v}" for k, v in type_counts.items()])
                print(f"      ✅ {len(attachments)}개 첨부파일 발견 ({types_str})")
                
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
                    if progress['success'] % 10 == 0:
                        print(f"   ✅ 진행: {progress['success']}/{progress['total']} | 수집된 파일: {progress['new_files']}개")
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
    print("=" * 70)
    print("🎯 K-Startup 첨부파일 정확한 수집 (/afile/fileDownload/ 패턴)")
    print("=" * 70)
    
    # attachment_count가 0인 레코드들
    no_attach = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, detl_pg_url')\
        .eq('attachment_count', 0)\
        .execute()
    
    progress['total'] = len(no_attach.data)
    
    print(f"\n✅ 처리 대상: {progress['total']}개 (첨부파일 없는 레코드)")
    
    if progress['total'] == 0:
        print("🎉 모든 레코드가 첨부파일을 가지고 있습니다!")
        return
    
    # 샘플 테스트
    print(f"\n📌 먼저 10개 샘플 테스트...")
    sample_records = no_attach.data[:10]
    
    for record in sample_records[:3]:
        print(f"\n🔍 {record['announcement_id']}: {record['biz_pbanc_nm'][:30]}...")
        attachments = extract_attachments_correctly(
            record.get('detl_pg_url', ''), 
            record['announcement_id']
        )
        if attachments:
            print(f"   📎 {len(attachments)}개 첨부파일 발견!")
            for att in attachments[:3]:
                print(f"      - {att['text']}: {att['url'][:60]}...")
        else:
            print("   ❌ 첨부파일 없음")
    
    # 자동으로 전체 처리 진행
    print("\n📌 전체 처리를 시작합니다...")
    
    print(f"\n🔥 전체 {progress['total']}개 레코드 처리 시작 (30개 동시 실행)")
    print("-" * 70)
    
    # ThreadPoolExecutor로 병렬 처리
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(process_record, record): record for record in no_attach.data}
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                pass
    
    # 최종 결과
    print("\n" + "=" * 70)
    print("📊 처리 결과")
    print("=" * 70)
    print(f"✅ 성공: {progress['success']}/{progress['total']} ({progress['success']/progress['total']*100:.1f}%)")
    print(f"📎 수집된 첨부파일: {progress['new_files']}개")
    print(f"❌ 실패: {progress['error']}/{progress['total']}")
    
    if progress['new_files'] > 0:
        print(f"\n🎉 {progress['new_files']}개의 첨부파일을 성공적으로 수집했습니다!")

if __name__ == "__main__":
    main()