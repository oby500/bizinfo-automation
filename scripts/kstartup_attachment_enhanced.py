#!/usr/bin/env python3
"""
K-Startup 첨부파일 수집 개선판 (기업마당 방식 적용)
워크플로우 호환 버전
- 파일 시그니처로 실제 타입 감지
- 15가지 파일 타입 구분
- 공고명을 파일명에 포함
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
    'PPTX': {'ext': 'pptx', 'mime': 'application/vnd.openxmlformats-officedocument.presentationml.document'},
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
            elif content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
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
            elif content[:3] == b'\xff\xd8\xff':
                return 'JPG'
            elif content[:8] == b'\x89PNG\r\n\x1a\n':
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
    """개선된 K-Startup 첨부파일 추출"""
    all_attachments = []
    safe_title = make_safe_title(announcement_title) if announcement_title else ""
    
    # pbanc_sn 추출
    if 'pbancSn=' in page_url:
        pbanc_sn = re.search(r'pbancSn=(\d+)', page_url).group(1)
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
                
                # 파일 타입 감지
                file_type = get_file_type_by_signature(full_url, text)
                type_info = FILE_TYPE_INFO.get(file_type, FILE_TYPE_INFO['FILE'])
                
                # 파일명 결정
                original_filename = text if text and text != '다운로드' else f'첨부파일_{idx}'
                display_filename = f"{original_filename}.{type_info['ext']}" if not original_filename.endswith(f".{type_info['ext']}") else original_filename
                
                # safe_filename: 공고명_번호_원본파일명.확장자
                if safe_title:
                    base_name = re.sub(r'\.[^.]+$', '', original_filename)[:20]
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
                    'params': {}
                }
                
                attachments.append(attachment)
                
                with lock:
                    progress['type_stats'][file_type] = progress['type_stats'].get(file_type, 0) + 1
                    if file_type != 'FILE':
                        progress['type_detected'] += 1
            
            if attachments:
                all_attachments.extend(attachments)
                
        except Exception:
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
    print("📎 K-Startup 첨부파일 수집 개선 (기업마당 방식)")
    print("="*70)
    
    # 처리 제한 확인 (환경변수로 받음)
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '0'))
    
    # 처리 대상 조회
    if processing_limit > 0:
        # Daily 모드: 최근 N개만
        all_records = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm, detl_pg_url, attachment_urls, attachment_count')\
            .order('created_at', desc=True)\
            .limit(processing_limit * 2)\
            .execute()
        print(f"📌 Daily 모드: 최근 {processing_limit*2}개 중에서 처리 필요한 것만 선택")
    else:
        # Full 모드: 전체
        all_records = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm, detl_pg_url, attachment_urls, attachment_count')\
            .execute()
        print("📌 Full 모드: 전체 데이터 처리")
    
    needs_processing = []
    
    for record in all_records.data:
        # 첨부파일이 없거나 모두 FILE 타입인 경우
        if record.get('attachment_count', 0) == 0:
            needs_processing.append(record)
        elif record.get('attachment_urls'):
            all_file_type = all(
                att.get('type') == 'FILE' 
                for att in record['attachment_urls'] 
                if isinstance(att, dict)
            )
            if all_file_type:
                needs_processing.append(record)
    
    # Daily 모드에서는 최대 50개만 처리
    if processing_limit > 0 and len(needs_processing) > processing_limit:
        needs_processing = needs_processing[:processing_limit]
        print(f"📌 Daily 모드 제한: 최대 {processing_limit}개만 처리")
    
    progress['total'] = len(needs_processing)
    
    print(f"✅ 검토 대상: {len(all_records.data)}개")
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