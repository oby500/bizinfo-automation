#!/usr/bin/env python3
"""
K-Startup 첨부파일 정보를 BizInfo 방식으로 업데이트
실제 파일명과 확장자 추출하여 safe_filename/display_filename 생성
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

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_filename = f'kstartup_attachment_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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
progress = {'success': 0, 'error': 0, 'total': 0, 'processed': 0}

def extract_filename_from_disposition(disposition):
    """Content-Disposition 헤더에서 파일명 추출"""
    filename = None
    
    # filename*=UTF-8'' 형식
    if "filename*=" in disposition:
        match = re.search(r"filename\*=UTF-8''([^;]+)", disposition)
        if match:
            filename = unquote(match.group(1))
    
    # filename=" " 형식
    if not filename and 'filename=' in disposition:
        match = re.search(r'filename="?([^";\n]+)"?', disposition)
        if match:
            filename = match.group(1)
            # 인코딩 문제 해결
            try:
                filename = filename.encode('iso-8859-1').decode('utf-8')
            except:
                try:
                    # EUC-KR로 인코딩된 경우
                    filename = filename.encode('iso-8859-1').decode('euc-kr')
                except:
                    pass
    
    return filename

def get_file_extension_from_content(content):
    """파일 내용의 시그니처로 확장자 판별"""
    # 파일 시그니처 매핑
    signatures = {
        b'%PDF': 'pdf',
        b'\xd0\xcf\x11\xe0': 'doc',  # MS Office
        b'PK\x03\x04': 'docx',  # Office Open XML
        b'HWP Document': 'hwp',
        b'\x89PNG': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF8': 'gif',
        b'<?xml': 'xml',
        b'{"': 'json',
        b'[{': 'json',
    }
    
    # 텍스트 파일 체크 (UTF-8 또는 ASCII)
    try:
        content[:1000].decode('utf-8')
        return 'txt'
    except:
        pass
    
    for sig, ext in signatures.items():
        if content.startswith(sig):
            return ext
    
    # ZIP 기반 파일들 추가 확인
    if content.startswith(b'PK'):
        # DOCX, XLSX, PPTX 등
        if b'word/' in content[:1000]:
            return 'docx'
        elif b'xl/' in content[:1000]:
            return 'xlsx'
        elif b'ppt/' in content[:1000]:
            return 'pptx'
    
    return 'unknown'

def fix_encoding(text):
    """잘못된 인코딩 수정"""
    if not text:
        return text
    
    # 깨진 한글 패턴 체크
    if any(c in text for c in ['¿', '½', '°', 'Ç', 'À', 'Ã']):
        try:
            # EUC-KR로 인코딩된 것을 잘못 읽은 경우
            fixed = text.encode('iso-8859-1').decode('euc-kr')
            return fixed
        except:
            try:
                # CP949로 시도
                fixed = text.encode('iso-8859-1').decode('cp949')
                return fixed
            except:
                pass
    return text

def get_real_file_info(url, announcement_id, index):
    """실제 파일 정보 추출 (BizInfo 방식)"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    }
    
    try:
        # 1. HEAD 요청 시도
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
        
        filename = None
        extension = 'unknown'
        file_size = 0
        
        # Content-Disposition에서 파일명 추출
        content_disposition = response.headers.get('Content-Disposition', '')
        if content_disposition:
            filename = extract_filename_from_disposition(content_disposition)
        
        # Content-Type에서 확장자 힌트
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type:
            extension = 'pdf'
        elif 'hwp' in content_type or 'haansoft' in content_type:
            extension = 'hwp'
        elif 'word' in content_type or 'msword' in content_type:
            extension = 'doc'
        elif 'openxmlformats' in content_type and 'word' in content_type:
            extension = 'docx'
        elif 'excel' in content_type or 'spreadsheet' in content_type:
            extension = 'xlsx'
        elif 'powerpoint' in content_type or 'presentation' in content_type:
            extension = 'pptx'
        elif 'zip' in content_type:
            extension = 'zip'
        elif 'text' in content_type or 'plain' in content_type:
            extension = 'txt'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            extension = 'jpg'
        elif 'png' in content_type:
            extension = 'png'
        
        # 파일 크기
        file_size = int(response.headers.get('Content-Length', 0))
        
        # 2. 파일명이 없으면 일부 다운로드해서 확인
        if not filename or filename == '다운로드' or extension == 'unknown':
            # 처음 1KB만 다운로드
            response = requests.get(url, headers=headers, stream=True, timeout=10)
            content = b''
            for chunk in response.iter_content(chunk_size=1024):
                content = chunk
                break
            
            # 파일 시그니처로 확장자 확인
            if content:
                detected_ext = get_file_extension_from_content(content)
                if detected_ext != 'unknown':
                    extension = detected_ext
            
            # Content-Disposition 다시 확인 (GET 요청에서)
            if not filename:
                content_disposition = response.headers.get('Content-Disposition', '')
                if content_disposition:
                    filename = fix_encoding(extract_filename_from_disposition(content_disposition))
        
        # 3. 파일명 생성
        if not filename or filename == '다운로드':
            # 기본 파일명 생성
            filename = f"첨부파일_{index}.{extension}"
        elif '.' not in filename and extension != 'unknown':
            # 확장자 추가
            filename = f"{filename}.{extension}"
        elif '.' in filename:
            # 파일명에서 확장자 추출
            name_ext = filename.split('.')[-1].lower()
            if name_ext in ['pdf', 'hwp', 'doc', 'docx', 'xlsx', 'pptx', 'zip', 'jpg', 'jpeg', 'png', 'gif', 'txt', 'csv', 'xml', 'json']:
                extension = name_ext
        
        # 파일명 인코딩 수정
        filename = fix_encoding(filename)
        
        return {
            'real_name': filename,
            'extension': extension,
            'size': file_size,
            'content_type': content_type
        }
        
    except Exception as e:
        logging.error(f"파일 정보 추출 실패 ({url}): {str(e)[:100]}")
        return {
            'real_name': f"첨부파일_{index}.unknown",
            'extension': 'unknown',
            'size': 0,
            'content_type': ''
        }

def process_announcement_attachments(ann):
    """단일 공고의 첨부파일 처리"""
    announcement_id = ann['announcement_id']
    attachments = ann.get('attachment_urls', [])
    
    if not attachments:
        return False
    
    try:
        updated_attachments = []
        
        for idx, attachment in enumerate(attachments, 1):
            url = attachment.get('url', '')
            if not url:
                continue
            
            # 실제 파일 정보 가져오기
            file_info = get_real_file_info(url, announcement_id, idx)
            
            # BizInfo 형식으로 변환
            updated_attachment = {
                'url': url,
                'text': '다운로드',
                'type': file_info['extension'].upper(),
                'params': {},
                'safe_filename': f"{'KS_' if not announcement_id.startswith('KS_') else ''}{announcement_id}_{idx:02d}.{file_info['extension']}",
                'display_filename': file_info['real_name'],
                'original_filename': file_info['real_name']
            }
            
            updated_attachments.append(updated_attachment)
            
            logging.debug(f"{announcement_id} - 파일 {idx}: {file_info['real_name']}")
        
        # DB 업데이트
        if updated_attachments:
            result = supabase.table('kstartup_complete')\
                .update({
                    'attachment_urls': updated_attachments,
                    'attachment_count': len(updated_attachments),
                    'attachment_processing_status': {
                        'file_info_extracted': True,
                        'extraction_date': datetime.now().isoformat(),
                        'method': 'bizinfo_style'
                    }
                })\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['processed'] += len(updated_attachments)
                    if progress['success'] % 10 == 0:
                        logging.info(f"✅ 진행: {progress['success']}/{progress['total']} 공고, {progress['processed']}개 파일 처리")
                return True
        
        with lock:
            progress['error'] += 1
        return False
        
    except Exception as e:
        logging.error(f"처리 오류 ({announcement_id}): {str(e)[:100]}")
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행 - 병렬 처리"""
    logging.info("=" * 60)
    logging.info("K-Startup 첨부파일 정보 업데이트 (BizInfo 방식)")
    logging.info("=" * 60)
    
    try:
        # 첨부파일이 있는 모든 공고 조회
        result = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .execute()
        
        # 빈 배열 제외
        announcements = [ann for ann in result.data if ann.get('attachment_urls')]
        progress['total'] = len(announcements)
        
        logging.info(f"처리 대상: {progress['total']}개 공고")
        logging.info(f"병렬 처리 시작 (최대 20개 동시 실행)")
        
        start_time = time.time()
        
        # ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 모든 작업 제출
            futures = {executor.submit(process_announcement_attachments, ann): ann for ann in announcements}
            
            # 완료되는 대로 처리
            for future in as_completed(futures):
                ann = futures[future]
                try:
                    success = future.result()
                    if not success:
                        logging.debug(f"처리 실패: {ann['announcement_id']}")
                except Exception as e:
                    logging.error(f"작업 실행 오류: {str(e)[:100]}")
        
        elapsed_time = time.time() - start_time
        
        # 최종 결과
        logging.info("\n" + "=" * 60)
        logging.info("첨부파일 정보 업데이트 완료!")
        logging.info(f"✅ 성공: {progress['success']}/{progress['total']} 공고")
        logging.info(f"📎 처리된 파일: {progress['processed']}개")
        logging.info(f"❌ 실패: {progress['error']}/{progress['total']} 공고")
        logging.info(f"⏱️ 소요 시간: {elapsed_time:.1f}초")
        logging.info("=" * 60)
        
        # 샘플 확인
        sample = supabase.table('kstartup_complete')\
            .select('announcement_id, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .limit(3)\
            .execute()
        
        logging.info("\n📋 업데이트된 샘플:")
        for s in sample.data:
            logging.info(f"\n공고: {s['announcement_id']}")
            for att in s.get('attachment_urls', []):
                logging.info(f"  - safe: {att.get('safe_filename')}")
                logging.info(f"    display: {att.get('display_filename')}")
        
    except Exception as e:
        logging.error(f"전체 처리 오류: {str(e)}")

if __name__ == "__main__":
    main()