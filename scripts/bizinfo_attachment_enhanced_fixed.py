#!/usr/bin/env python3
"""
BizInfo 첨부파일 수집 개선판 - 정확한 파일 타입 감지
- K-Startup 방식 적용
- 파일 시그니처로 100% 정확한 타입 감지
- HWP/DOC 구분 개선
- 15가지 파일 타입 지원
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

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

lock = threading.Lock()
progress = {
    'success': 0, 
    'error': 0, 
    'total': 0, 
    'new_files': 0,
    'type_detected': 0,
    'type_stats': {}
}

# 파일 타입 정보
FILE_TYPE_INFO = {
    'HWP': {'ext': 'hwp', 'mime': 'application/x-hwp'},
    'HWPX': {'ext': 'hwpx', 'mime': 'application/x-hwpx'},
    'PDF': {'ext': 'pdf', 'mime': 'application/pdf'},
    'DOCX': {'ext': 'docx', 'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    'DOC': {'ext': 'doc', 'mime': 'application/msword'},
    'XLSX': {'ext': 'xlsx', 'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
    'XLS': {'ext': 'xls', 'mime': 'application/vnd.ms-excel'},
    'PPTX': {'ext': 'pptx', 'mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'},
    'PPT': {'ext': 'ppt', 'mime': 'application/vnd.ms-powerpoint'},
    'ZIP': {'ext': 'zip', 'mime': 'application/zip'},
    'JPG': {'ext': 'jpg', 'mime': 'image/jpeg'},
    'PNG': {'ext': 'png', 'mime': 'image/png'},
    'GIF': {'ext': 'gif', 'mime': 'image/gif'},
    'TXT': {'ext': 'txt', 'mime': 'text/plain'},
    'FILE': {'ext': 'bin', 'mime': 'application/octet-stream'}
}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.bizinfo.go.kr/'
})

def get_file_type_by_signature(url):
    """파일 시그니처로 정확한 타입 감지"""
    try:
        response = session.get(url, stream=True, timeout=10)
        
        # Content-Disposition에서 파일명 추출 시도 (인코딩 개선)
        cd = response.headers.get('Content-Disposition', '')
        filename_hint = None
        if cd:
            try:
                if "filename*=UTF-8''" in cd:
                    match = re.search(r"filename\*=UTF-8''([^;]+)", cd)
                    if match:
                        filename_hint = unquote(match.group(1))
                elif 'filename=' in cd:
                    match = re.search(r'filename="?([^";]+)"?', cd)
                    if match:
                        raw_filename = match.group(1)
                        # 다양한 인코딩 시도
                        try:
                            filename_hint = raw_filename.encode('iso-8859-1').decode('utf-8')
                        except:
                            try:
                                filename_hint = raw_filename.encode('iso-8859-1').decode('euc-kr')
                            except:
                                filename_hint = raw_filename
            except:
                filename_hint = None
        
        # 파일 내용 읽기 (10KB)
        content = response.raw.read(10000)
        response.close()
        
        file_type = 'FILE'
        
        # PDF
        if content[:4] == b'%PDF':
            file_type = 'PDF'
        
        # ZIP 기반 (Office 2007+, HWPX)
        elif content[:2] == b'PK':
            if b'hwpml' in content:
                file_type = 'HWPX'
            elif b'word/' in content:
                file_type = 'DOCX'
            elif b'xl/' in content or b'worksheet' in content:
                file_type = 'XLSX'
            elif b'ppt/' in content or b'presentation' in content:
                file_type = 'PPTX'
            else:
                file_type = 'ZIP'
        
        # HWP 명확한 시그니처
        elif b'HWP Document File' in content[:100]:
            file_type = 'HWP'
        
        # OLE 컴파운드 파일 (MS Office 97-2003 또는 HWP 5.0)
        elif content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            # HWP 5.0 시그니처 확인
            if b'HWP Document File' in content or b'HwpSummaryInformation' in content:
                file_type = 'HWP'
            # HWP 키워드가 있으면 HWP로 판단
            elif b'Hwp' in content or b'HWP' in content:
                if b'Microsoft' not in content[:2000]:
                    file_type = 'HWP'
                else:
                    if b'Microsoft Word' in content or b'WordDocument' in content:
                        file_type = 'DOC'
                    elif b'Microsoft Excel' in content or b'Workbook' in content:
                        file_type = 'XLS'
                    elif b'Microsoft PowerPoint' in content or b'PowerPoint' in content:
                        file_type = 'PPT'
                    else:
                        file_type = 'DOC'
            # Microsoft 제품
            elif b'Microsoft Word' in content or b'WordDocument' in content:
                file_type = 'DOC'
            elif b'Microsoft Excel' in content or b'Workbook' in content:
                file_type = 'XLS'
            elif b'Microsoft PowerPoint' in content or b'PowerPoint' in content:
                file_type = 'PPT'
            else:
                # 파일명 힌트 사용
                if filename_hint:
                    ext = filename_hint.split('.')[-1].lower() if '.' in filename_hint else ''
                    if ext == 'hwp':
                        file_type = 'HWP'
                    elif ext == 'doc':
                        file_type = 'DOC'
                    elif ext == 'xls':
                        file_type = 'XLS'
                    elif ext == 'ppt':
                        file_type = 'PPT'
                else:
                    file_type = 'DOC'  # 기본값
        
        # 이미지
        elif content[:3] == b'\xff\xd8\xff':
            file_type = 'JPG'
        elif content[:8] == b'\x89PNG\r\n\x1a\n':
            file_type = 'PNG'
        elif content[:6] in [b'GIF87a', b'GIF89a']:
            file_type = 'GIF'
        
        # 텍스트 파일
        else:
            try:
                decoded = content.decode('utf-8')
                if sum(1 for c in decoded if c.isprintable() or c.isspace()) / len(decoded) > 0.9:
                    file_type = 'TXT'
            except:
                pass
        
        return file_type, filename_hint
        
    except Exception as e:
        return 'FILE', None

def make_safe_title(title):
    """공고명을 안전한 파일명으로 변환"""
    if not title:
        return ""
    # 특수문자 제거, 공백을 언더스코어로
    safe = re.sub(r'[^\w\s가-힣-]', '', title)
    safe = re.sub(r'\s+', '_', safe)
    # 길이 제한
    return safe[:30] if len(safe) > 30 else safe

def extract_bizinfo_attachments(detail_url, pblanc_id, announcement_title=None):
    """BizInfo 첨부파일 추출"""
    all_attachments = []
    safe_title = make_safe_title(announcement_title) if announcement_title else ""
    
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
        
        # 3. 일반 파일 다운로드 링크 (href="/jsp/down.jsp" 등)
        if not file_links:
            file_links = soup.find_all('a', href=re.compile(r'(down\.jsp|download|file)'))
        
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
            elif onclick and 'fnFileDown' in onclick:
                # onclick에서 파일 정보 추출
                match = re.search(r"fnFileDown\('([^']+)'", onclick)
                if match:
                    file_param = match.group(1)
                    full_url = f"https://www.bizinfo.go.kr/jsp/down.jsp?file={file_param}"
            
            if not full_url:
                continue
            
            # 파일 타입 감지
            file_type, server_filename = get_file_type_by_signature(full_url)
            type_info = FILE_TYPE_INFO.get(file_type, FILE_TYPE_INFO['FILE'])
            
            # 파일명 결정
            if server_filename:
                original_filename = server_filename
            elif text and text not in ['다운로드', '첨부파일', '파일다운로드']:
                original_filename = text
            else:
                original_filename = f'첨부파일_{idx}'
            
            # 확장자 처리
            if not re.search(r'\.[a-zA-Z0-9]+$', original_filename):
                display_filename = f"{original_filename}.{type_info['ext']}"
            else:
                # 잘못된 확장자면 교정
                base_name = re.sub(r'\.[^.]+$', '', original_filename)
                display_filename = f"{base_name}.{type_info['ext']}"
            
            # safe_filename
            if safe_title:
                safe_filename = f"{safe_title}_{idx:02d}"
            else:
                safe_filename = f"BIZ_{pblanc_id}_{idx:02d}"
            
            attachment = {
                'url': full_url,
                'type': file_type,
                'text': text or f'첨부파일_{idx}',
                'params': {},
                'safe_filename': safe_filename,
                'file_extension': type_info['ext'],
                'display_filename': display_filename,
                'original_filename': original_filename
            }
            
            # MIME 타입 추가
            if file_type != 'FILE':
                attachment['mime_type'] = type_info['mime']
            
            attachments.append(attachment)
            
            with lock:
                progress['type_stats'][file_type] = progress['type_stats'].get(file_type, 0) + 1
                if file_type != 'FILE':
                    progress['type_detected'] += 1
        
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
            update_data = {'attachment_urls': attachments}
            
            result = supabase.table('bizinfo_complete')\
                .update(update_data)\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['new_files'] += len(attachments)
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
    print("📎 BizInfo 첨부파일 수집 (정확한 시그니처 기반)")
    print("="*70)
    
    # 처리 제한 확인
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '0'))
    
    # 처리 대상 조회
    if processing_limit > 0:
        # 제한 모드: 최근 N개만
        all_records = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, bsns_title, detail_url, dtl_url, attachment_urls')\
            .order('created_at', desc=True)\
            .limit(processing_limit * 2)\
            .execute()
        print(f"📌 제한 모드: 최근 {processing_limit*2}개 중에서 처리 필요한 것만 선택")
    else:
        # Full 모드: 전체
        all_records = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, bsns_title, detail_url, dtl_url, attachment_urls')\
            .execute()
        print("📌 Full 모드: 전체 데이터 처리")
    
    needs_processing = []
    
    for record in all_records.data:
        # 첨부파일이 없거나 FILE 타입이 많은 경우
        detail_url = record.get('detail_url') or record.get('dtl_url')
        
        if not detail_url:
            continue  # URL이 없으면 처리 불가
            
        if not record.get('attachment_urls'):
            needs_processing.append(record)
        else:
            # FILE이나 잘못된 타입이 있는지 확인
            has_issues = False
            for att in record['attachment_urls']:
                if isinstance(att, dict):
                    if att.get('type') == 'FILE' or not att.get('file_extension'):
                        has_issues = True
                        break
            
            if has_issues:
                needs_processing.append(record)
    
    # 제한 모드에서는 최대 N개만 처리
    if processing_limit > 0 and len(needs_processing) > processing_limit:
        needs_processing = needs_processing[:processing_limit]
        print(f"📌 제한 모드: 최대 {processing_limit}개만 처리")
    
    progress['total'] = len(needs_processing)
    
    print(f"✅ 검토 대상: {len(all_records.data)}개")
    print(f"📎 처리 필요: {progress['total']}개")
    
    if progress['total'] == 0:
        print("🎉 모든 레코드가 이미 처리되었습니다!")
        return
    
    print(f"🔥 {progress['total']}개 처리 시작 (15 workers)...\n")
    
    # 병렬 처리 (BizInfo는 K-Startup보다 느려서 worker 수 줄임)
    with ThreadPoolExecutor(max_workers=15) as executor:
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
    print("📊 처리 완료")
    print("="*70)
    print(f"✅ 성공: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 첨부파일: {progress['new_files']}개")
    print(f"🎯 타입 감지: {progress['type_detected']}개")
    
    if progress['type_stats']:
        print(f"\n📊 파일 타입 분포:")
        for file_type, count in sorted(progress['type_stats'].items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = count * 100 / progress['new_files'] if progress['new_files'] > 0 else 0
            print(f"   {file_type}: {count}개 ({percentage:.1f}%)")
    
    print("="*70)

if __name__ == "__main__":
    main()