#!/usr/bin/env python3
"""
K-Startup 첨부파일 수집 개선판 - 파일명 추출 개선
워크플로우 호환 버전
- 파일 시그니처로 실제 타입 감지
- 15가지 파일 타입 구분
- 실제 파일명 추출 개선 (Content-Disposition 헤더 활용)
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
    'Referer': 'https://www.k-startup.go.kr/'
})

def extract_filename_from_header(content_disposition):
    """Content-Disposition 헤더에서 파일명 추출"""
    if not content_disposition:
        return None
    
    # filename*=UTF-8''encodedfilename 패턴
    if "filename*=UTF-8''" in content_disposition:
        try:
            encoded_filename = content_disposition.split("filename*=UTF-8''")[1].split(';')[0]
            return unquote(encoded_filename)
        except:
            pass
    
    # filename="filename" 패턴
    if 'filename=' in content_disposition:
        try:
            filename = content_disposition.split('filename=')[1].split(';')[0].strip('"\'')
            return filename
        except:
            pass
    
    return None

def get_real_filename(url, link_text):
    """실제 파일명 추출 (HEAD 요청으로 Content-Disposition 헤더 확인)"""
    try:
        # HEAD 요청으로 헤더만 가져오기
        response = session.head(url, timeout=10, allow_redirects=True)
        
        # Content-Disposition 헤더에서 파일명 추출
        if 'content-disposition' in response.headers:
            filename = extract_filename_from_header(response.headers['content-disposition'])
            if filename and filename != 'attachment':
                return filename
        
        # URL에서 파일명 추출 시도
        if '/' in url:
            url_filename = url.split('/')[-1].split('?')[0]
            if '.' in url_filename and len(url_filename) > 1:
                return unquote(url_filename)
        
        # 링크 텍스트가 의미있는 경우 사용
        if link_text and link_text != '다운로드' and len(link_text.strip()) > 0:
            # 특수문자를 적절히 처리
            clean_text = re.sub(r'[<>:"/\\|?*]', '_', link_text.strip())
            if clean_text and clean_text != '_':
                return clean_text
        
        return None
        
    except Exception as e:
        print(f"    ⚠️ 파일명 추출 실패: {str(e)}")
        return None

def get_file_type_by_signature(url, text_hint=None):
    """파일 시그니처로 실제 타입 감지"""
    try:
        # Range 헤더로 처음 1KB만 다운로드
        headers = {'Range': 'bytes=0-1024'}
        response = session.get(url, headers=headers, timeout=10, stream=True)
        
        if response.status_code in [200, 206]:
            content = response.content[:1024]
        else:
            return 'FILE'
        
        # 바이너리 시그니처로 타입 판단
        if len(content) >= 4:
            # PDF
            if content[:4] == b'%PDF':
                return 'PDF'
            
            # ZIP 기반 (Office 2007+, HWP 5.0+)
            elif content[:2] == b'PK':
                # 더 자세한 판단을 위해 전체 다운로드
                full_response = session.get(url, timeout=15)
                full_content = full_response.content[:5000]
                
                # HWPX
                if b'hwpml' in full_content or b'HWP' in full_content:
                    return 'HWPX'
                elif b'word/' in full_content:
                    return 'DOCX'
                elif b'xl/' in full_content or b'worksheet' in full_content:
                    return 'XLSX'
                elif b'ppt/' in full_content or b'presentation' in full_content:
                    return 'PPTX'
                else:
                    return 'ZIP'
            
            # MS Office 97-2003
            elif content[:8] == b'\\xd0\\xcf\\x11\\xe0\\xa1\\xb1\\x1a\\xe1':
                if text_hint:
                    text_lower = text_hint.lower()
                    if 'xls' in text_lower or '엑셀' in text_lower:
                        return 'XLS'
                    elif 'ppt' in text_lower or '파워' in text_lower:
                        return 'PPT'
                    elif 'doc' in text_lower or '워드' in text_lower:
                        return 'DOC'
                return 'DOC'
            
            # HWP
            elif b'HWP Document' in content[:32] or b'HWP' in content[:32]:
                return 'HWP'
            
            # 이미지
            elif content[:3] == b'\\xff\\xd8\\xff':
                return 'JPG'
            elif content[:8] == b'\\x89PNG\\r\\n\\x1a\\n':
                return 'PNG'
            elif content[:6] in [b'GIF87a', b'GIF89a']:
                return 'GIF'
        
        # 텍스트 힌트 사용
        if text_hint:
            return guess_type_from_text(text_hint)
        
        return 'FILE'
        
    except Exception:
        return 'FILE'

def guess_type_from_text(text):
    """텍스트에서 파일 타입 추측"""
    if not text:
        return 'FILE'
    
    text_lower = text.lower()
    
    # 확장자 패턴
    ext_patterns = {
        '.hwp': 'HWP', '.hwpx': 'HWPX', '.pdf': 'PDF',
        '.docx': 'DOCX', '.doc': 'DOC',
        '.xlsx': 'XLSX', '.xls': 'XLS',
        '.pptx': 'PPTX', '.ppt': 'PPT',
        '.zip': 'ZIP', '.jpg': 'JPG', '.png': 'PNG'
    }
    
    for ext, file_type in ext_patterns.items():
        if ext in text_lower:
            return file_type
    
    # 키워드 매핑
    if any(kw in text_lower for kw in ['한글', '한컴', '양식', '서식', '신청서']):
        return 'HWP'
    elif 'pdf' in text_lower:
        return 'PDF'
    elif any(kw in text_lower for kw in ['excel', '엑셀']):
        return 'XLSX'
    elif any(kw in text_lower for kw in ['word', '워드']):
        return 'DOCX'
    
    return 'FILE'

def make_safe_title(title):
    """공고명을 안전한 파일명으로 변환"""
    if not title:
        return ""
    # 특수문자 제거, 공백을 언더스코어로
    safe = re.sub(r'[^\w\s가-힣-]', '', title)
    safe = re.sub(r'\s+', '_', safe)
    # 길이 제한
    return safe[:30] if len(safe) > 30 else safe

def extract_attachments_enhanced(page_url, announcement_id, announcement_title=None):
    """개선된 K-Startup 첨부파일 추출 - 실제 파일명 추출 강화"""
    all_attachments = []
    safe_title = make_safe_title(announcement_title) if announcement_title else ""
    
    # pbanc_sn 추출
    if 'pbancSn=' in page_url:
        match = re.search(r'pbancSn=(\d+)', page_url)
        if match:
            pbanc_sn = match.group(1)
        else:
            pbanc_sn = announcement_id.replace('KS_', '')
    else:
        pbanc_sn = announcement_id.replace('KS_', '')
    
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
                
            soup = BeautifulSoup(response.text, 'html.parser')
            attachments = []
            
            # /afile/fileDownload/ 패턴
            download_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
            
            for idx, link in enumerate(download_links, 1):
                href = link.get('href', '')
                text = link.get_text(strip=True) or ''
                
                # URL 생성
                full_url = urljoin(try_url, href)
                
                print(f"    🔍 파일 {idx}: {text} -> URL 확인 중...")
                
                # 실제 파일명 추출 (개선된 로직)
                real_filename = get_real_filename(full_url, text)
                
                if real_filename:
                    original_filename = real_filename
                    print(f"    ✅ 실제 파일명 발견: {original_filename}")
                else:
                    # 폴백: 기본 명명
                    original_filename = f'첨부파일_{idx}'
                    print(f"    ⚠️ 실제 파일명 추출 실패, 기본명 사용: {original_filename}")
                
                # 파일 타입 감지
                file_type = get_file_type_by_signature(full_url, original_filename)
                type_info = FILE_TYPE_INFO.get(file_type, FILE_TYPE_INFO['FILE'])
                
                # display_filename: 확장자 확보
                if '.' in original_filename:
                    display_filename = original_filename
                else:
                    display_filename = f"{original_filename}.{type_info['ext']}"
                
                # safe_filename: KS_ID_번호_원본파일명.확장자
                base_name = re.sub(r'\.[^.]+$', '', original_filename)
                clean_base = re.sub(r'[^\w가-힣\s-]', '_', base_name)[:30]
                
                # KS_ 접두사 확보
                if not announcement_id.startswith('KS_'):
                    announcement_id = f"KS_{announcement_id}"
                
                safe_filename = f"{announcement_id}_{idx:02d}_{clean_base}.{type_info['ext']}"
                
                attachment = {
                    'url': full_url,
                    'type': file_type,
                    'text': text or f'첨부파일_{idx}',
                    'original_filename': original_filename,
                    'display_filename': display_filename,
                    'safe_filename': safe_filename,
                    'mime_type': type_info['mime'],
                    'params': {}
                }
                
                attachments.append(attachment)
                
                with lock:
                    progress['type_stats'][file_type] = progress['type_stats'].get(file_type, 0) + 1
                    if file_type != 'FILE':
                        progress['type_detected'] += 1
            
            if attachments:
                all_attachments.extend(attachments)
                
        except Exception as e:
            print(f"    ❌ URL 처리 실패: {try_url} - {str(e)}")
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
    
    if not detl_pg_url:
        pbanc_sn = announcement_id.replace('KS_', '')
        detl_pg_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}'
    
    try:
        attachments = extract_attachments_enhanced(detl_pg_url, announcement_id, full_title)
        
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
                print(f"  ✅ 저장 완료: {announcement_id} ({len(attachments)}개 파일)")
                return True
        
        with lock:
            progress['error'] += 1
        print(f"  ❌ 첨부파일 없음: {announcement_id}")
        return False
        
    except Exception as e:
        with lock:
            progress['error'] += 1
        print(f"  ❌ 처리 실패: {announcement_id} - {str(e)}")
        return False

def main():
    """메인 실행"""
    print("="*70)
    print("📎 K-Startup 첨부파일 수집 개선 (실제 파일명 추출)")
    print("="*70)
    
    # 최근 레코드만 테스트 (174xxx 번대)
    test_records = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, detl_pg_url, attachment_urls, attachment_count')\
        .like('announcement_id', '174%')\
        .limit(5)\
        .execute()
    
    progress['total'] = len(test_records.data)
    
    print(f"✅ 테스트 대상: {progress['total']}개")
    print(f"🔥 처리 시작...\n")
    
    # 순차 처리 (디버깅용)
    for i, record in enumerate(test_records.data, 1):
        print(f"\n[{i}/{progress['total']}] 처리 중: {record['announcement_id']}")
        process_record(record)
    
    # 결과 출력
    print("\n" + "="*70)
    print("📊 처리 완료")
    print("="*70)
    print(f"✅ 성공: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 첨부파일: {progress['new_files']}개")
    print(f"🎯 타입 감지: {progress['type_detected']}개")
    
    if progress['type_stats']:
        print(f"\n📊 파일 타입 분포:")
        for file_type, count in sorted(progress['type_stats'].items(), key=lambda x: x[1], reverse=True):
            percentage = count * 100 / progress['new_files'] if progress['new_files'] > 0 else 0
            print(f"   {file_type}: {count}개 ({percentage:.1f}%)")
    
    print("="*70)

if __name__ == "__main__":
    main()