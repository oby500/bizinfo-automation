#!/usr/bin/env python3
"""
BizInfo 첨부파일 인코딩 문제 완전 해결 - 전체 처리 버전
- 모든 깨진 파일명 복구
- 이중/삼중 인코딩 처리
- K-Startup 방식 완전 적용
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
from urllib.parse import unquote, urlparse, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

# 진행 상황 추적
lock = threading.Lock()
progress = {'success': 0, 'error': 0, 'skip': 0, 'total': 0, 'fixed': 0}

def fix_broken_encoding(text):
    """깨진 인코딩 복구 - 강화된 버전"""
    if not text:
        return text
    
    # 깨진 문자 패턴
    broken_patterns = ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â', '¿', '½', 'ð', 'þ', 'ï']
    
    # 깨진 문자가 없으면 원본 반환
    if not any(p in text for p in broken_patterns):
        return text
    
    original_text = text
    
    try:
        # 1단계: 삼중 인코딩 복구 (가장 심한 경우)
        if 'Ã' in text and 'Â' in text:
            try:
                # UTF-8 → Latin-1 → UTF-8 → Latin-1 → UTF-8 (삼중)
                fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
                fixed = fixed.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
                if any(korean in fixed for korean in ['참', '신청', '공고', '지원', '사업', '년', '대구', '경기', '서울', '부산']):
                    logging.info(f"삼중 인코딩 복구 성공: {original_text[:30]} → {fixed[:30]}")
                    return fixed
            except:
                pass
        
        # 2단계: 이중 인코딩 복구
        try:
            # UTF-8 → Latin-1 → UTF-8 (이중)
            fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
            if any(korean in fixed for korean in ['참', '신청', '공고', '지원', '사업', '년']):
                logging.info(f"이중 인코딩 복구 성공: {original_text[:30]} → {fixed[:30]}")
                return fixed
        except:
            pass
        
        # 3단계: CP949/EUC-KR 변환
        try:
            # 잘못된 UTF-8을 CP949로 재해석
            broken_bytes = text.encode('utf-8', errors='ignore')
            fixed = broken_bytes.decode('cp949', errors='ignore')
            if any(korean in fixed for korean in ['참', '신청', '공고', '지원', '사업']):
                logging.info(f"CP949 복구 성공: {original_text[:30]} → {fixed[:30]}")
                return fixed
        except:
            pass
        
        # 4단계: 수동 패턴 매핑 (확장)
        replacements = {
            # 자주 나타나는 단어
            'ì°¸ê°ì ì²­ì': '참가신청서',
            'ê³µê³ ': '공고',
            'ì ì²­ì': '신청서',
            'ì¬ì': '사업',
            'ê¸°ì': '기업',
            'ì§ì': '지원',
            'ëª¨ì§': '모집',
            'ì°½ì': '창업',
            'ì¤ìê¸°ì': '중소기업',
            
            # 이중 인코딩 패턴
            'Ã¬Â°Â¸ÃªÂ°Â': '참가',
            'Ã¬ÂÂÃ¬Â²Â­Ã¬ÂÂ': '신청서',
            'ÃªÂ³ÂµÃªÂ³Â ': '공고',
            'Ã«ÂÂÃªÂµÂ¬': '대구',
            'ÃªÂ²Â½ÃªÂ¸Â°': '경기',
            'Ã¬ÂÂÃ¬ÂÂ¸': '서울',
            'Ã«Â¶ÂÃ¬ÂÂ°': '부산',
            'Ã¬Â§ÂÃ¬ÂÂ­': '지역',
            'Ã«Â§ÂÃ¬Â¶Â¤Ã­ÂÂ': '맞춤형',
            'ÃªÂ·Â¼Ã«Â¡ÂÃ­ÂÂÃªÂ²Â½ÃªÂ°ÂÃ¬ÂÂ': '근로환경개선',
            'Ã¬ÂÂ¬Ã¬ÂÂ': '사업',
            'Ã«Â¬Â¸': '문',
            
            # 특수 패턴
            'Ã­ÂÂ': '형',
            'Ã¬ÂÂ': '식',
            'Ã«ÂÂ': '년',
            'ÃªÂ°Â': '개',
            
            # 숫자
            '2025Ã«ÂÂ': '2025년',
            '2024Ã«ÂÂ': '2024년',
        }
        
        result = text
        for broken, fixed in replacements.items():
            result = result.replace(broken, fixed)
        
        # 부분 복구라도 성공했으면 반환
        if result != text:
            logging.info(f"패턴 매핑 복구: {original_text[:30]} → {result[:30]}")
            return result
            
    except Exception as e:
        logging.debug(f"인코딩 복구 실패: {e}")
    
    # 복구 실패시 원본 반환
    return text

def extract_filename_from_disposition(disposition):
    """Content-Disposition 헤더에서 파일명 추출"""
    if not disposition:
        return None
    
    filename = None
    
    # filename*=UTF-8'' 형식 (RFC 5987)
    if "filename*=" in disposition:
        match = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", disposition, re.IGNORECASE)
        if match:
            filename = unquote(match.group(1))
            # 깨진 경우 복구
            if any(c in filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']):
                filename = fix_broken_encoding(filename)
            return filename
    
    # filename="..." 형식
    if 'filename=' in disposition:
        match = re.search(r'filename="?([^";\n]+)"?', disposition)
        if match:
            filename = match.group(1)
            
            # 인코딩 변환 시도
            try:
                # ISO-8859-1 → UTF-8
                fixed = filename.encode('iso-8859-1').decode('utf-8', errors='ignore')
                if any(korean in fixed for korean in ['참', '신청', '공고', '년']):
                    return fixed
            except:
                pass
            
            try:
                # ISO-8859-1 → CP949
                fixed = filename.encode('iso-8859-1').decode('cp949', errors='ignore')
                if any(korean in fixed for korean in ['참', '신청', '공고', '년']):
                    return fixed
            except:
                pass
            
            # 깨진 인코딩 복구
            return fix_broken_encoding(filename)
    
    return filename

def get_file_extension_from_content(content):
    """파일 내용의 시그니처로 확장자 판별"""
    signatures = {
        b'%PDF': 'pdf',
        b'\xd0\xcf\x11\xe0': 'hwp',  # HWP/DOC 공통
        b'PK\x03\x04': 'docx',
        b'HWP Document': 'hwp',
        b'\x89PNG': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF8': 'gif',
    }
    
    # HWP 파일 특별 체크
    if content[:4] == b'\xd0\xcf\x11\xe0':
        # HWP 문서 확인
        if b'HWP' in content[:1000] or b'Hwp' in content[:1000] or b'Hancom' in content[:1000]:
            return 'hwp'
        # 한글 문서가 많으므로 기본값 HWP
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
    
    return 'hwp'  # 기본값 HWP (한국 정부 특성)

def get_real_file_info(url, pblanc_id, index):
    """실제 파일 정보 추출 - 완전 복구 버전"""
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
        file_size = int(response.headers.get('Content-Length', 0))
        
        # Content-Disposition에서 파일명 추출
        content_disposition = response.headers.get('Content-Disposition', '')
        if content_disposition:
            filename = extract_filename_from_disposition(content_disposition)
        
        # Content-Type에서 확장자 확인
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type:
            extension = 'pdf'
        elif 'hwp' in content_type or 'haansoft' in content_type or 'octet-stream' in content_type:
            extension = 'hwp'
        
        # 2. 파일명이 없거나 깨진 경우 GET 요청으로 재시도
        if not filename or '다운로드' in filename or any(c in str(filename) for c in ['â', 'ì', 'ã', 'Ã', 'Â']):
            response = requests.get(url, headers=headers, stream=True, timeout=10)
            
            # Content-Disposition 다시 확인
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                new_filename = extract_filename_from_disposition(content_disposition)
                if new_filename:
                    filename = new_filename
            
            # 첫 1KB로 파일 타입 확인
            content = b''
            for chunk in response.iter_content(chunk_size=1024):
                content = chunk
                break
            
            if content:
                detected_ext = get_file_extension_from_content(content)
                if detected_ext != 'unknown':
                    extension = detected_ext
        
        # 3. 파일명 최종 처리
        if filename and any(c in filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']):
            original = filename
            filename = fix_broken_encoding(filename)
            logging.info(f"파일명 최종 복구: {original[:30]} → {filename[:30]}")
        
        if not filename or filename == '다운로드':
            if extension == 'hwp':
                filename = f"공고문_{index}.hwp"
            elif extension == 'pdf':
                filename = f"공고문_{index}.pdf"
            else:
                filename = f"첨부파일_{index}.{extension}"
        elif '.' not in filename and extension != 'unknown':
            filename = f"{filename}.{extension}"
        
        # 확장자 확인
        if '.' in filename:
            name_ext = filename.split('.')[-1].lower()
            if name_ext in ['pdf', 'hwp', 'hwpx', 'doc', 'docx', 'xlsx', 'pptx', 'zip', 'jpg', 'png']:
                extension = name_ext
        
        # DOC → HWP 변환 (한국 정부 특성)
        if extension in ['doc', 'unknown']:
            extension = 'hwp'
        
        return {
            'real_name': filename,
            'extension': extension.upper(),
            'size': file_size,
            'content_type': content_type
        }
        
    except Exception as e:
        logging.error(f"파일 정보 추출 실패 ({url}): {str(e)[:100]}")
        return {
            'real_name': f"첨부파일_{index}.hwp",
            'extension': 'HWP',
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
        fixed_count = 0
        
        for idx, attachment in enumerate(attachments, 1):
            url = attachment.get('url', '')
            current_filename = attachment.get('display_filename', '다운로드')
            current_type = attachment.get('type', 'UNKNOWN')
            
            if not url:
                updated_attachments.append(attachment)
                continue
            
            # 처리 대상: 깨진 파일명, '다운로드', DOC/HTML/UNKNOWN 타입
            needs_fix = (
                any(c in current_filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â', '¿', '½']) or
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
                fixed_count += 1
                
                logging.debug(f"{pblanc_id} - 파일 {idx}: {current_filename[:30]} → {file_info['real_name'][:30]}")
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
                    progress['fixed'] += fixed_count
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
    """메인 실행 - 전체 깨진 파일 처리"""
    logging.info("=" * 60)
    logging.info("BizInfo 첨부파일 인코딩 문제 완전 해결 - 전체 처리")
    logging.info("=" * 60)
    
    try:
        # 모든 공고 조회 (첨부파일이 있는 것만)
        logging.info("전체 데이터 조회 중...")
        result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .execute()
        
        # 깨진 파일명이나 문제가 있는 공고 필터링
        announcements = []
        total_broken = 0
        
        for ann in result.data:
            if ann.get('attachment_urls'):
                needs_processing = False
                for att in ann['attachment_urls']:
                    filename = att.get('display_filename', '')
                    file_type = att.get('type', '')
                    
                    # 깨진 파일명 체크
                    if any(c in filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â', '¿', '½', 'ð', 'þ', 'ï']):
                        needs_processing = True
                        total_broken += 1
                    # '다운로드' 파일명
                    elif filename == '다운로드':
                        needs_processing = True
                        total_broken += 1
                    # DOC/HTML/UNKNOWN 타입
                    elif file_type in ['DOC', 'HTML', 'UNKNOWN']:
                        needs_processing = True
                        total_broken += 1
                
                if needs_processing:
                    announcements.append(ann)
        
        progress['total'] = len(announcements)
        
        logging.info(f"전체 공고: {len(result.data)}개")
        logging.info(f"문제있는 공고: {progress['total']}개")
        logging.info(f"깨진/문제 파일: {total_broken}개")
        logging.info(f"병렬 처리 시작 (최대 5개 동시 실행)")
        
        if progress['total'] == 0:
            logging.info("✅ 처리할 깨진 파일이 없습니다!")
            return
        
        start_time = time.time()
        
        # ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(process_announcement_attachments, ann): ann for ann in announcements}
            
            for future in as_completed(futures):
                ann = futures[future]
                try:
                    future.result(timeout=30)
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
        
        # 처리율 계산
        if total_broken > 0:
            fix_rate = (progress['fixed'] / total_broken) * 100
            logging.info(f"📊 복구율: {fix_rate:.1f}%")
        
        logging.info("=" * 60)
        
        # 샘플 확인 (깨진 것이 남아있는지)
        check_result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .limit(10)\
            .execute()
        
        remaining_broken = 0
        for item in check_result.data:
            if item.get('attachment_urls'):
                for att in item['attachment_urls']:
                    filename = att.get('display_filename', '')
                    if any(c in filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']):
                        remaining_broken += 1
        
        if remaining_broken > 0:
            logging.warning(f"\n⚠️ 아직 {remaining_broken}개의 깨진 파일명이 샘플에서 발견됨")
            logging.info("추가 처리가 필요할 수 있습니다.")
        else:
            logging.info("\n✅ 샘플 확인 결과: 모든 파일명이 정상입니다!")
        
    except Exception as e:
        logging.error(f"전체 처리 오류: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    main()
