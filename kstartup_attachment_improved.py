#!/usr/bin/env python3
"""
K-Startup 첨부파일 수집 개선판 (기업마당 방식 적용)
- 파일 시그니처로 실제 타입 감지
- 15가지 파일 타입 구분
- Range 헤더로 효율적 다운로드
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client
from dotenv import load_dotenv
from urllib.parse import urljoin, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

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
    'HWP': {'ext': 'hwp', 'mime': 'application/x-hwp', 'icon': '📄'},
    'HWPX': {'ext': 'hwpx', 'mime': 'application/x-hwpx', 'icon': '📄'},
    'PDF': {'ext': 'pdf', 'mime': 'application/pdf', 'icon': '📕'},
    'DOCX': {'ext': 'docx', 'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'icon': '📘'},
    'DOC': {'ext': 'doc', 'mime': 'application/msword', 'icon': '📘'},
    'XLSX': {'ext': 'xlsx', 'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'icon': '📊'},
    'XLS': {'ext': 'xls', 'mime': 'application/vnd.ms-excel', 'icon': '📊'},
    'PPTX': {'ext': 'pptx', 'mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'icon': '📑'},
    'PPT': {'ext': 'ppt', 'mime': 'application/vnd.ms-powerpoint', 'icon': '📑'},
    'ZIP': {'ext': 'zip', 'mime': 'application/zip', 'icon': '📦'},
    'JPG': {'ext': 'jpg', 'mime': 'image/jpeg', 'icon': '🖼️'},
    'PNG': {'ext': 'png', 'mime': 'image/png', 'icon': '🖼️'},
    'GIF': {'ext': 'gif', 'mime': 'image/gif', 'icon': '🖼️'},
    'TXT': {'ext': 'txt', 'mime': 'text/plain', 'icon': '📝'},
    'RTF': {'ext': 'rtf', 'mime': 'application/rtf', 'icon': '📝'},
    'FILE': {'ext': 'bin', 'mime': 'application/octet-stream', 'icon': '📎'}
}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.k-startup.go.kr/'
})

def get_file_type_by_signature(url, text_hint=None):
    """파일 시그니처로 실제 타입 감지 (기업마당 방식)"""
    try:
        # 1단계: Range 헤더로 처음 1KB만 다운로드
        headers = {'Range': 'bytes=0-1024'}
        response = session.get(url, headers=headers, timeout=10, stream=True)
        
        # Range를 지원하지 않는 경우 전체 다운로드
        if response.status_code == 200:
            content = response.content[:1024]
        elif response.status_code == 206:  # Partial Content
            content = response.content
        else:
            return 'FILE'
        
        # 2단계: 바이너리 시그니처로 타입 판단
        if len(content) >= 4:
            # PDF
            if content[:4] == b'%PDF':
                return 'PDF'
            
            # ZIP 기반 (Office 2007+, HWP 5.0+)
            elif content[:2] == b'PK':
                # 더 자세한 판단을 위해 전체 다운로드
                full_response = session.get(url, timeout=15)
                full_content = full_response.content[:5000]
                
                # HWPX (한글 2014+)
                if b'hwpml' in full_content or b'HWP' in full_content:
                    return 'HWPX'
                # DOCX
                elif b'word/' in full_content:
                    return 'DOCX'
                # XLSX
                elif b'xl/' in full_content or b'worksheet' in full_content:
                    return 'XLSX'
                # PPTX
                elif b'ppt/' in full_content or b'presentation' in full_content:
                    return 'PPTX'
                else:
                    return 'ZIP'
            
            # MS Office 97-2003
            elif content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                # 텍스트 힌트로 구분
                if text_hint:
                    text_lower = text_hint.lower()
                    if 'xls' in text_lower or '엑셀' in text_lower:
                        return 'XLS'
                    elif 'ppt' in text_lower or '파워' in text_lower:
                        return 'PPT'
                    elif 'doc' in text_lower or '워드' in text_lower:
                        return 'DOC'
                return 'DOC'  # 기본값
            
            # HWP 5.0
            elif content[:4] == b'\xd0\xcf\x11\xe0' or b'HWP Document' in content[:32]:
                return 'HWP'
            
            # HWP 3.0
            elif len(content) >= 32 and b'HWP' in content[:32]:
                return 'HWP'
            
            # 이미지 파일들
            elif content[:3] == b'\xff\xd8\xff':
                return 'JPG'
            elif content[:8] == b'\x89PNG\r\n\x1a\n':
                return 'PNG'
            elif content[:6] in [b'GIF87a', b'GIF89a']:
                return 'GIF'
            
            # 텍스트 파일
            elif content[:5] == b'{\\rtf':
                return 'RTF'
            elif content[:3] == b'\xef\xbb\xbf':  # UTF-8 BOM
                return 'TXT'
        
        # 3단계: Content-Disposition 헤더에서 파일명 추출
        if 'content-disposition' in response.headers.lower():
            disposition = response.headers.get('Content-Disposition', '')
            filename = extract_filename_from_header(disposition)
            if filename:
                return guess_type_from_filename(filename)
        
        # 4단계: URL에서 파일명 추출
        url_parts = url.split('/')
        if url_parts:
            last_part = unquote(url_parts[-1])
            if '.' in last_part:
                return guess_type_from_filename(last_part)
        
        # 5단계: 텍스트 힌트 사용
        if text_hint:
            return guess_type_from_text(text_hint)
        
        return 'FILE'
        
    except Exception as e:
        print(f"      ⚠️ 타입 감지 실패: {str(e)[:50]}")
        return 'FILE'

def extract_filename_from_header(disposition):
    """Content-Disposition 헤더에서 파일명 추출"""
    if not disposition:
        return None
    
    # filename*= (RFC 5987) 또는 filename= 패턴
    patterns = [
        r"filename\*=UTF-8''([^;]+)",
        r'filename="([^"]+)"',
        r"filename='([^']+)'",
        r'filename=([^;]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, disposition, re.IGNORECASE)
        if match:
            filename = match.group(1).strip()
            # URL 디코딩
            return unquote(filename)
    
    return None

def guess_type_from_filename(filename):
    """파일명에서 확장자로 타입 추측"""
    if not filename:
        return 'FILE'
    
    filename_lower = filename.lower()
    
    # 확장자 매핑
    ext_map = {
        '.hwp': 'HWP', '.hwpx': 'HWPX',
        '.pdf': 'PDF',
        '.docx': 'DOCX', '.doc': 'DOC',
        '.xlsx': 'XLSX', '.xls': 'XLS',
        '.pptx': 'PPTX', '.ppt': 'PPT',
        '.zip': 'ZIP', '.rar': 'ZIP', '.7z': 'ZIP',
        '.jpg': 'JPG', '.jpeg': 'JPG',
        '.png': 'PNG',
        '.gif': 'GIF',
        '.txt': 'TXT',
        '.rtf': 'RTF'
    }
    
    for ext, file_type in ext_map.items():
        if filename_lower.endswith(ext):
            return file_type
    
    return 'FILE'

def guess_type_from_text(text):
    """링크 텍스트에서 파일 타입 힌트 추출"""
    if not text:
        return 'FILE'
    
    text_lower = text.lower()
    
    # 키워드 매핑
    keyword_map = {
        'hwp': 'HWP', '한글': 'HWP', '한컴': 'HWP',
        'pdf': 'PDF',
        'word': 'DOCX', '워드': 'DOCX', 'docx': 'DOCX', 'doc': 'DOC',
        'excel': 'XLSX', '엑셀': 'XLSX', 'xlsx': 'XLSX', 'xls': 'XLS',
        'ppt': 'PPTX', '파워포인트': 'PPTX', 'powerpoint': 'PPTX',
        'zip': 'ZIP', '압축': 'ZIP',
        '이미지': 'JPG', 'image': 'JPG', '사진': 'JPG',
        '양식': 'HWP', '서식': 'HWP', '신청서': 'HWP', '계획서': 'HWP'
    }
    
    for keyword, file_type in keyword_map.items():
        if keyword in text_lower:
            return file_type
    
    # 파일명 패턴 찾기
    pattern = r'([가-힣a-zA-Z0-9\s\-\_]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return guess_type_from_filename(match.group(1))
    
    return 'FILE'

def extract_attachments_improved(page_url, announcement_id, announcement_title=None):
    """개선된 K-Startup 첨부파일 추출 (기업마당 방식)"""
    all_attachments = []
    
    # pbanc_sn 추출
    if 'pbancSn=' in page_url:
        pbanc_sn = re.search(r'pbancSn=(\d+)', page_url).group(1)
    else:
        pbanc_sn = announcement_id.replace('KS_', '') if announcement_id.startswith('KS_') else announcement_id
    
    # 공고명을 안전한 파일명으로 변환
    def make_safe_title(title):
        if not title:
            return ""
        # 특수문자 제거, 공백을 언더스코어로
        safe = re.sub(r'[^\w\s가-힣-]', '', title)
        safe = re.sub(r'\s+', '_', safe)
        # 길이 제한 (30자)
        return safe[:30] if len(safe) > 30 else safe
    
    safe_title = make_safe_title(announcement_title) if announcement_title else ""
    
    # ongoing과 deadline 모두 시도
    urls_to_try = [
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}',
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?schM=view&pbancSn={pbanc_sn}'
    ]
    
    for try_url in urls_to_try:
        try:
            response = session.get(try_url, timeout=15)
            if response.status_code != 200:
                continue
                
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            attachments = []
            
            # 1. /afile/fileDownload/ 패턴
            download_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
            
            for idx, link in enumerate(download_links, 1):
                href = link.get('href', '')
                text = link.get_text(strip=True) or ''
                
                # 전체 URL 생성
                full_url = urljoin(try_url, href)
                
                # 파일 타입 감지 (기업마당 방식)
                file_type = get_file_type_by_signature(full_url, text)
                
                # 파일 정보 구성
                type_info = FILE_TYPE_INFO.get(file_type, FILE_TYPE_INFO['FILE'])
                
                # 파일명 결정
                if text and text != '다운로드':
                    display_filename = text
                    original_filename = text
                    # 확장자가 없으면 추가
                    if not any(text.lower().endswith(f".{info['ext']}") for info in FILE_TYPE_INFO.values()):
                        display_filename = f"{text}.{type_info['ext']}"
                else:
                    display_filename = f"첨부파일_{idx}.{type_info['ext']}"
                    original_filename = f"첨부파일_{idx}"
                
                # safe_filename: 공고명_번호_원본파일명.확장자 형식
                if safe_title:
                    # 원본 파일명에서 확장자 제거
                    base_name = re.sub(r'\.[^.]+$', '', original_filename)
                    # 파일명 길이 조정
                    if len(base_name) > 20:
                        base_name = base_name[:20]
                    safe_filename = f"{safe_title}_{idx:02d}_{base_name}.{type_info['ext']}"
                else:
                    safe_filename = f"KS_{announcement_id}_{idx:02d}.{type_info['ext']}"
                
                attachment = {
                    'url': full_url,
                    'type': file_type,
                    'text': text or f'첨부파일_{idx}',
                    'original_filename': original_filename,
                    'display_filename': display_filename,
                    'safe_filename': safe_filename,
                    'mime_type': type_info['mime'],
                    'icon': type_info['icon'],
                    'detected_by': 'signature',
                    'params': {}
                }
                
                attachments.append(attachment)
                
                # 통계 업데이트
                with lock:
                    progress['type_stats'][file_type] = progress['type_stats'].get(file_type, 0) + 1
                    if file_type != 'FILE':
                        progress['type_detected'] += 1
            
            # 2. JavaScript onclick 패턴
            elements_with_onclick = soup.find_all(attrs={'onclick': re.compile(r'fileDownload|fnFileDown|fnDownload')})
            
            for elem in elements_with_onclick:
                onclick = elem.get('onclick', '')
                text = elem.get_text(strip=True) or ''
                
                # fileDownload('파일ID') 패턴
                matches = re.findall(r"(?:fileDownload|fnFileDown|fnDownload)\s*\(\s*['\"]([^'\"]+)['\"]", onclick)
                for file_id in matches:
                    full_url = f'https://www.k-startup.go.kr/afile/fileDownload/{file_id}'
                    
                    # 중복 체크
                    if any(att['url'] == full_url for att in attachments):
                        continue
                    
                    # 파일 타입 감지
                    file_type = get_file_type_by_signature(full_url, text)
                    type_info = FILE_TYPE_INFO.get(file_type, FILE_TYPE_INFO['FILE'])
                    
                    idx = len(attachments) + 1
                    original_filename = text or f'첨부파일_{idx}'
                    display_filename = f"{original_filename}.{type_info['ext']}" if not original_filename.endswith(f".{type_info['ext']}") else original_filename
                    
                    # safe_filename: 공고명_번호_원본파일명.확장자 형식
                    if safe_title:
                        base_name = re.sub(r'\.[^.]+$', '', original_filename)
                        if len(base_name) > 20:
                            base_name = base_name[:20]
                        safe_filename = f"{safe_title}_{idx:02d}_{base_name}.{type_info['ext']}"
                    else:
                        safe_filename = f"KS_{announcement_id}_{idx:02d}.{type_info['ext']}"
                    
                    attachment = {
                        'url': full_url,
                        'type': file_type,
                        'text': text or f'첨부파일_{idx}',
                        'original_filename': original_filename,
                        'display_filename': display_filename,
                        'safe_filename': safe_filename,
                        'mime_type': type_info['mime'],
                        'icon': type_info['icon'],
                        'detected_by': 'onclick',
                        'params': {'file_id': file_id}
                    }
                    
                    attachments.append(attachment)
                    
                    with lock:
                        progress['type_stats'][file_type] = progress['type_stats'].get(file_type, 0) + 1
                        if file_type != 'FILE':
                            progress['type_detected'] += 1
            
            if attachments:
                all_attachments.extend(attachments)
                print(f"      ✅ {len(attachments)}개 첨부파일 발견")
                for att in attachments[:3]:  # 처음 3개만 표시
                    print(f"         {att['icon']} {att['type']}: {att['display_filename']}")
                
        except Exception as e:
            print(f"      ❌ 오류: {str(e)[:50]}")
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
    full_title = record.get('biz_pbanc_nm', '')
    title = full_title[:50] + "..." if len(full_title) > 50 else full_title
    
    if not detl_pg_url:
        pbanc_sn = announcement_id.replace('KS_', '') if announcement_id.startswith('KS_') else announcement_id
        detl_pg_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}'
    
    print(f"\n🔍 {announcement_id}: {title}")
    
    try:
        # 공고명을 함께 전달
        attachments = extract_attachments_improved(detl_pg_url, announcement_id, full_title)
        
        if attachments:
            update_data = {
                'attachment_urls': attachments,
                'attachment_count': len(attachments)
                # attachment_metadata 필드는 없으므로 제거
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
        else:
            print(f"      ℹ️ 첨부파일 없음")
        
        with lock:
            progress['error'] += 1
        return False
        
    except Exception as e:
        print(f"      ❌ 처리 오류: {str(e)[:50]}")
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행"""
    print("="*70)
    print("🚀 K-Startup 첨부파일 수집 개선판 (기업마당 방식)")
    print("="*70)
    print("✅ 개선 사항:")
    print("   - 파일 시그니처로 정확한 타입 감지")
    print("   - 15가지 파일 타입 구분 (HWP, PDF, DOCX 등)")
    print("   - Range 헤더로 효율적 다운로드")
    print("   - MIME 타입 및 아이콘 정보 추가")
    print("="*70)
    
    # 처리 대상 조회
    print("\n📊 처리 대상 확인 중...")
    
    # attachment_count가 0이거나 attachment_urls의 type이 모두 FILE인 레코드
    all_records = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, detl_pg_url, attachment_urls, attachment_count')\
        .execute()
    
    needs_processing = []
    
    for record in all_records.data:
        # 첨부파일이 없는 경우
        if record.get('attachment_count', 0) == 0:
            needs_processing.append(record)
        # 첨부파일이 있지만 모두 FILE 타입인 경우
        elif record.get('attachment_urls'):
            all_file_type = all(
                att.get('type') == 'FILE' 
                for att in record['attachment_urls'] 
                if isinstance(att, dict)
            )
            if all_file_type:
                needs_processing.append(record)
    
    progress['total'] = len(needs_processing)
    
    print(f"✅ 전체 레코드: {len(all_records.data)}개")
    print(f"📎 처리 필요: {progress['total']}개")
    
    if progress['total'] == 0:
        print("\n🎉 모든 레코드가 이미 처리되었습니다!")
        return
    
    # 샘플 테스트
    print(f"\n📌 먼저 5개 샘플 테스트...")
    sample_records = needs_processing[:5]
    
    for record in sample_records:
        process_record(record)
    
    # 통계 출력
    if progress['type_stats']:
        print(f"\n📊 감지된 파일 타입:")
        for file_type, count in sorted(progress['type_stats'].items(), key=lambda x: x[1], reverse=True):
            type_info = FILE_TYPE_INFO.get(file_type, FILE_TYPE_INFO['FILE'])
            print(f"   {type_info['icon']} {file_type}: {count}개")
    
    # 자동으로 전체 처리 진행
    print(f"\n📌 샘플 테스트 완료. 전체 처리를 시작합니다.")
    print(f"\n🔥 전체 {len(needs_processing)}개 처리 시작 (20 workers)...")
    
    # 병렬 처리
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_record, record): record for record in needs_processing}
        
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                if i % 50 == 0:
                    print(f"\n   진행: {i}/{len(needs_processing)} ({i*100//len(needs_processing)}%)")
                    if progress['type_stats']:
                        top_types = sorted(progress['type_stats'].items(), key=lambda x: x[1], reverse=True)[:5]
                        print(f"   타입: {', '.join([f'{t}:{c}' for t, c in top_types])}")
            except:
                pass
    
    # 최종 결과
    print("\n" + "="*70)
    print("📊 처리 완료")
    print("="*70)
    print(f"✅ 성공: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 첨부파일: {progress['new_files']}개")
    print(f"🎯 타입 감지 성공: {progress['type_detected']}개")
    print(f"❌ 실패: {progress['error']}/{progress['total']}")
    
    if progress['type_stats']:
        print(f"\n📊 파일 타입 분포:")
        for file_type, count in sorted(progress['type_stats'].items(), key=lambda x: x[1], reverse=True):
            type_info = FILE_TYPE_INFO.get(file_type, FILE_TYPE_INFO['FILE'])
            percentage = count * 100 / progress['new_files'] if progress['new_files'] > 0 else 0
            print(f"   {type_info['icon']} {file_type}: {count}개 ({percentage:.1f}%)")
    
    print("="*70)

if __name__ == "__main__":
    main()