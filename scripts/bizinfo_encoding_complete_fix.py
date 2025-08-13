#!/usr/bin/env python3
"""
BizInfo 첨부파일 인코딩 문제 완전 해결
- 이중 인코딩 문제 해결
- K-Startup 방식 완전 적용
- 서버 인코딩 자동 감지
"""
import os
import sys
import requests
from bs4 import BeautifulSoup
import json
import time
import re
from supabase import create_client
from dotenv import load_dotenv
import logging
from datetime import datetime
from urllib.parse import unquote, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import chardet

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_filename = f'bizinfo_encoding_complete_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Supabase 연결
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 진행 상황 추적
lock = threading.Lock()
progress = {'success': 0, 'error': 0, 'skip': 0, 'total': 0, 'fixed': 0}

def fix_broken_encoding(text):
    """깨진 인코딩 복구"""
    if not text:
        return text
    
    # 이미 깨진 문자 패턴
    broken_patterns = ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']
    
    # 깨진 문자가 없으면 원본 반환
    if not any(p in text for p in broken_patterns):
        return text
    
    try:
        # 1단계: 이중 인코딩 복구 시도
        # UTF-8 → Latin-1 → UTF-8 (이중 인코딩된 경우)
        if 'Ã' in text and 'Â' in text:
            # 이중 인코딩 복구
            fixed = text.encode('latin-1').decode('utf-8', errors='ignore')
            # 다시 한번 복구 시도
            fixed = fixed.encode('latin-1').decode('utf-8', errors='ignore')
            if '참' in fixed or '신청' in fixed or '공고' in fixed:
                return fixed
        
        # 2단계: 단일 인코딩 복구
        # UTF-8 → Latin-1 변환
        fixed = text.encode('latin-1').decode('utf-8', errors='ignore')
        if '참' in fixed or '신청' in fixed or '공고' in fixed:
            return fixed
        
        # 3단계: CP949/EUC-KR 복구 시도
        # 잘못된 UTF-8을 원래 바이트로 복원 후 CP949로 디코딩
        try:
            # 깨진 UTF-8을 바이트로
            broken_bytes = text.encode('utf-8', errors='ignore')
            # CP949로 디코딩 시도
            fixed = broken_bytes.decode('cp949', errors='ignore')
            if '참' in fixed or '신청' in fixed or '공고' in fixed:
                return fixed
        except:
            pass
        
        # 4단계: 수동 매핑 (자주 나타나는 패턴)
        replacements = {
            'ì°¸ê°ì ì²­ì': '참가신청서',
            'ê³µê³ ': '공고',
            'ì ì²­ì': '신청서',
            'ì¬ì': '사업',
            'ê¸°ì': '기업',
            'ì§ì': '지원',
            'ëª¨ì§': '모집',
            'ì°½ì': '창업',
            'ì¤ìê¸°ì': '중소기업',
            'Ã¬Â°Â¸ÃªÂ°Â': '참가',
            'Ã¬ÂÂÃ¬Â²Â­Ã¬ÂÂ': '신청서',
            'ÃªÂ³ÂµÃªÂ³Â ': '공고',
            'Ã«ÂÂÃªÂµÂ¬': '대구',
            'ÃªÂ²Â½ÃªÂ¸Â°': '경기',
            'Ã¬ÂÂÃ¬ÂÂ¸': '서울',
            'Ã«Â¶ÂÃ¬ÂÂ°': '부산',
        }
        
        result = text
        for broken, fixed in replacements.items():
            result = result.replace(broken, fixed)
        
        if result != text:
            return result
            
    except Exception as e:
        logging.debug(f"인코딩 복구 실패: {e}")
    
    return text

def extract_filename_from_disposition(disposition):
    """Content-Disposition 헤더에서 파일명 추출 - K-Startup 방식"""
    if not disposition:
        return None
    
    filename = None
    
    # filename*=UTF-8'' 형식 (RFC 5987)
    if "filename*=" in disposition:
        match = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", disposition, re.IGNORECASE)
        if match:
            filename = unquote(match.group(1))
            return filename
    
    # filename="..." 형식
    if 'filename=' in disposition:
        match = re.search(r'filename="?([^";\n]+)"?', disposition)
        if match:
            filename = match.group(1)
            
            # 인코딩 감지 및 변환
            try:
                # 1. 먼저 원본 그대로 시도
                filename.encode('utf-8')
                if not any(c in filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã']):
                    return filename
            except:
                pass
            
            # 2. ISO-8859-1로 인코딩된 경우 (서버가 잘못 보낸 경우)
            try:
                fixed = filename.encode('iso-8859-1').decode('utf-8')
                if '참' in fixed or '신청' in fixed or '공고' in fixed:
                    return fixed
            except:
                pass
            
            # 3. CP949/EUC-KR로 인코딩된 경우
            try:
                fixed = filename.encode('iso-8859-1').decode('cp949')
                if '참' in fixed or '신청' in fixed or '공고' in fixed:
                    return fixed
            except:
                pass
            
            # 4. 깨진 인코딩 복구
            return fix_broken_encoding(filename)
    
    return filename

def get_file_extension_from_content(content):
    """파일 내용의 시그니처로 확장자 판별"""
    signatures = {
        b'%PDF': 'pdf',
        b'\xd0\xcf\x11\xe0': 'doc',
        b'PK\x03\x04': 'docx',
        b'HWP Document': 'hwp',
        b'\x89PNG': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF8': 'gif',
    }
    
    # HWP 파일 추가 체크
    if content[:4] == b'\xd0\xcf\x11\xe0':
        if b'HWP' in content[:1000] or b'Hwp' in content[:1000]:
            return 'hwp'
    
    for sig, ext in signatures.items():
        if content.startswith(sig):
            return ext
    
    # ZIP 기반 파일들
    if content.startswith(b'PK'):
        if b'word/' in content[:1000]:
            return 'docx'
        elif b'xl/' in content[:1000]:
            return 'xlsx'
        elif b'ppt/' in content[:1000]:
            return 'pptx'
        elif b'hwp' in content[:1000].lower():
            return 'hwpx'
    
    return 'unknown'

def get_real_file_info(url, pblanc_id, index):
    """실제 파일 정보 추출 - K-Startup 방식 + 인코딩 자동 감지"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://www.bizinfo.go.kr/'
    }
    
    try:
        # 1. HEAD 요청으로 헤더 정보 가져오기
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
        
        filename = None
        extension = 'unknown'
        file_size = 0
        
        # Content-Disposition에서 파일명 추출
        content_disposition = response.headers.get('Content-Disposition', '')
        if content_disposition:
            # 원본 헤더 로깅 (디버깅용)
            logging.debug(f"Content-Disposition 원본: {content_disposition}")
            filename = extract_filename_from_disposition(content_disposition)
            
            if filename:
                logging.debug(f"추출된 파일명: {filename}")
        
        # Content-Type에서 확장자 힌트
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type:
            extension = 'pdf'
        elif 'hwp' in content_type or 'haansoft' in content_type:
            extension = 'hwp'
        elif 'octet-stream' in content_type:
            extension = 'hwp'  # BizInfo 특성상 대부분 HWP
        
        # 파일 크기
        file_size = int(response.headers.get('Content-Length', 0))
        
        # 2. 파일명이 없거나 깨진 경우 GET 요청으로 다시 시도
        if not filename or '다운로드' in filename or any(c in str(filename) for c in ['â', 'ì', 'ã', 'Ã']):
            response = requests.get(url, headers=headers, stream=True, timeout=10)
            
            # 응답 인코딩 자동 감지
            if response.encoding == 'ISO-8859-1' and response.apparent_encoding:
                response.encoding = response.apparent_encoding
            
            # Content-Disposition 다시 확인
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                filename = extract_filename_from_disposition(content_disposition)
            
            # 첫 1KB로 파일 타입 확인
            content = b''
            for chunk in response.iter_content(chunk_size=1024):
                content = chunk
                break
            
            if content:
                detected_ext = get_file_extension_from_content(content)
                if detected_ext != 'unknown':
                    extension = detected_ext
        
        # 3. 파일명 최종 생성
        if not filename or filename == '다운로드':
            if extension == 'hwp':
                filename = f"공고문_{index}.hwp"
            elif extension == 'pdf':
                filename = f"공고문_{index}.pdf"
            else:
                filename = f"첨부파일_{index}.{extension}"
        elif '.' not in filename and extension != 'unknown':
            filename = f"{filename}.{extension}"
        elif '.' in filename:
            # 파일명에서 확장자 추출
            name_ext = filename.split('.')[-1].lower()
            if name_ext in ['pdf', 'hwp', 'hwpx', 'doc', 'docx', 'xlsx', 'pptx', 'zip']:
                extension = name_ext
        
        # 4. 깨진 파일명 복구
        if any(c in filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']):
            original = filename
            filename = fix_broken_encoding(filename)
            logging.info(f"파일명 복구: {original} → {filename}")
        
        return {
            'real_name': filename,
            'extension': extension.upper(),
            'size': file_size,
            'content_type': content_type
        }
        
    except Exception as e:
        logging.error(f"파일 정보 추출 실패 ({url}): {str(e)[:100]}")
        return {
            'real_name': f"첨부파일_{index}.unknown",
            'extension': 'UNKNOWN',
            'size': 0,
            'content_type': ''
        }

def process_announcement_attachments(ann):
    """단일 공고의 첨부파일 처리"""
    pblanc_id = ann['pblanc_id']
    attachments = ann.get('attachment_urls', [])
    
    if not attachments:
        return False
    
    try:
        updated_attachments = []
        has_changes = False
        
        for idx, attachment in enumerate(attachments, 1):
            url = attachment.get('url', '')
            current_filename = attachment.get('display_filename', '다운로드')
            current_type = attachment.get('type', 'UNKNOWN')
            
            if not url:
                updated_attachments.append(attachment)
                continue
            
            # 깨진 파일명이거나 DOC/HTML 타입인 경우 처리
            needs_fix = (
                any(c in current_filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']) or
                current_filename == '다운로드' or
                current_type in ['DOC', 'HTML', 'UNKNOWN']
            )
            
            if needs_fix:
                # 실제 파일 정보 가져오기
                file_info = get_real_file_info(url, pblanc_id, idx)
                
                # 업데이트된 첨부파일 정보
                updated_attachment = {
                    'url': url,
                    'text': '다운로드',
                    'type': file_info['extension'],
                    'params': attachment.get('params', {}),
                    'safe_filename': f"{pblanc_id}_{idx:02d}.{file_info['extension'].lower()}",
                    'display_filename': file_info['real_name'],
                    'original_filename': file_info['real_name']
                }
                
                updated_attachments.append(updated_attachment)
                has_changes = True
                
                logging.debug(f"{pblanc_id} - 파일 {idx}: {current_filename} → {file_info['real_name']}")
            else:
                # 정상적인 파일은 그대로 유지
                updated_attachments.append(attachment)
        
        # DB 업데이트 (변경사항이 있을 때만)
        if has_changes:
            result = supabase.table('bizinfo_complete')\
                .update({
                    'attachment_urls': updated_attachments
                })\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['fixed'] += sum(1 for a in updated_attachments 
                                           if not any(c in a.get('display_filename', '') 
                                                    for c in ['â', 'ì', 'ã', 'Ã']))
                    if progress['success'] % 10 == 0:
                        logging.info(f"✅ 진행: {progress['success']}/{progress['total']} 공고, {progress['fixed']}개 파일 수정")
                return True
        else:
            with lock:
                progress['skip'] += 1
        
        return False
        
    except Exception as e:
        logging.error(f"처리 오류 ({pblanc_id}): {str(e)[:100]}")
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행"""
    logging.info("=" * 60)
    logging.info("BizInfo 첨부파일 인코딩 문제 완전 해결")
    logging.info("=" * 60)
    
    try:
        # 깨진 파일명이 있는 공고 조회
        result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .execute()
        
        # 깨진 파일명이 있는 공고만 필터링
        announcements = []
        for ann in result.data:
            if ann.get('attachment_urls'):
                urls_str = json.dumps(ann['attachment_urls'])
                if any(pattern in urls_str for pattern in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â', 'DOC', 'HTML', '다운로드']):
                    announcements.append(ann)
        
        progress['total'] = len(announcements)
        
        logging.info(f"처리 대상: {progress['total']}개 공고 (깨진 파일명 + DOC/HTML 타입)")
        logging.info(f"병렬 처리 시작 (최대 5개 동시 실행)")
        
        start_time = time.time()
        
        # ThreadPoolExecutor로 병렬 처리 (안정성 위해 5개로 제한)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(process_announcement_attachments, ann): ann for ann in announcements}
            
            for future in as_completed(futures):
                ann = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"작업 실행 오류: {str(e)[:100]}")
                
                # 서버 부하 방지
                time.sleep(0.2)
        
        elapsed_time = time.time() - start_time
        
        # 최종 결과
        logging.info("\n" + "=" * 60)
        logging.info("인코딩 문제 완전 해결 완료!")
        logging.info(f"✅ 성공: {progress['success']}/{progress['total']} 공고")
        logging.info(f"⏭️ 스킵: {progress['skip']}/{progress['total']} 공고")
        logging.info(f"❌ 실패: {progress['error']}/{progress['total']} 공고")
        logging.info(f"🔧 복구된 파일: {progress['fixed']}개")
        logging.info(f"⏱️ 소요 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
        logging.info("=" * 60)
        
        # 샘플 확인
        sample = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .limit(3)\
            .execute()
        
        logging.info("\n📋 수정된 샘플:")
        for s in sample.data:
            logging.info(f"\n공고: {s['pblanc_id']} - {s['pblanc_nm'][:30]}...")
            for att in s.get('attachment_urls', [])[:2]:
                logging.info(f"  - Type: {att.get('type')}")
                logging.info(f"    File: {att.get('display_filename')}")
        
    except Exception as e:
        logging.error(f"전체 처리 오류: {str(e)}")

if __name__ == "__main__":
    main()
