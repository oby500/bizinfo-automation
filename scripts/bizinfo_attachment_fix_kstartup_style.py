#!/usr/bin/env python3
"""
BizInfo 첨부파일 정보를 K-Startup 방식으로 업데이트
실제 파일을 HEAD 요청 및 부분 다운로드로 확인하여 정확한 파일명과 타입 추출
인코딩 문제 수정 버전
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
log_filename = f'bizinfo_attachment_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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
progress = {'success': 0, 'error': 0, 'skip': 0, 'total': 0, 'processed': 0}

def extract_filename_from_disposition(disposition):
    """Content-Disposition 헤더에서 파일명 추출 - 인코딩 수정 없이"""
    filename = None
    
    # filename*=UTF-8'' 형식
    if "filename*=" in disposition:
        match = re.search(r"filename\*=UTF-8''([^;]+)", disposition)
        if match:
            filename = unquote(match.group(1))
    
    # filename=" " 형식
    if not filename and 'filename=' in disposition:
        match = re.search(r'filename="?([^";\\n]+)"?', disposition)
        if match:
            filename = match.group(1)
            # UTF-8로 디코딩 시도
            try:
                # 이미 UTF-8인 경우 그대로 사용
                filename.encode('utf-8')
            except:
                # UTF-8이 아닌 경우만 변환 시도
                try:
                    filename = filename.encode('latin-1').decode('utf-8')
                except:
                    pass
    
    return filename

def get_file_extension_from_content(content):
    """파일 내용의 시그니처로 확장자 판별"""
    # 파일 시그니처 매핑
    signatures = {
        b'%PDF': 'pdf',
        b'\xd0\xcf\x11\xe0': 'doc',  # MS Office
        b'PK\x03\x04': 'docx',  # Office Open XML (DOCX, XLSX, PPTX)
        b'HWP Document': 'hwp',
        b'\x89PNG': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF8': 'gif',
        b'<?xml': 'xml',
        b'{"': 'json',
        b'[{': 'json',
    }
    
    # 한글 HWP 파일 시그니처 추가 체크
    if content[:4] == b'\xd0\xcf\x11\xe0':
        # HWP 5.0 이상
        if b'HWP' in content[:1000] or b'Hwp' in content[:1000]:
            return 'hwp'
    
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
        else:
            # 한글 HWPX 파일인 경우
            if b'hwp' in content[:1000].lower():
                return 'hwpx'
    
    return 'unknown'

def get_real_file_info(url, pblanc_id, index, current_type):
    """실제 파일 정보 추출 (K-Startup 방식) - 인코딩 수정 없이"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://www.bizinfo.go.kr/'
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
        elif 'octet-stream' in content_type:
            # 바이너리 스트림인 경우 - 대부분 HWP
            extension = 'hwp'
        
        # 파일 크기
        file_size = int(response.headers.get('Content-Length', 0))
        
        # 2. 파일명이 없거나 확장자가 불명확하면 일부 다운로드해서 확인
        if not filename or filename == '다운로드' or extension == 'unknown' or current_type == 'DOC':
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
                # DOC로 표시되었지만 실제로는 HWP일 가능성이 높음
                elif current_type == 'DOC' and detected_ext == 'unknown':
                    # 한국 정부 사이트의 DOC는 대부분 HWP
                    extension = 'hwp'
            
            # Content-Disposition 다시 확인 (GET 요청에서)
            if not filename or filename == '다운로드':
                content_disposition = response.headers.get('Content-Disposition', '')
                if content_disposition:
                    filename = extract_filename_from_disposition(content_disposition)
        
        # 3. 파일명 생성
        if not filename or filename == '다운로드':
            # 공고 제목 기반으로 파일명 생성
            if extension == 'hwp':
                filename = f"공고문_{index}.hwp"
            elif extension == 'pdf':
                filename = f"공고문_{index}.pdf"
            else:
                filename = f"첨부파일_{index}.{extension}"
        elif '.' not in filename and extension != 'unknown':
            # 확장자 추가
            filename = f"{filename}.{extension}"
        elif '.' in filename:
            # 파일명에서 확장자 추출
            name_ext = filename.split('.')[-1].lower()
            if name_ext in ['pdf', 'hwp', 'hwpx', 'doc', 'docx', 'xlsx', 'pptx', 'zip', 'jpg', 'jpeg', 'png', 'gif', 'txt', 'csv', 'xml', 'json']:
                extension = name_ext
        
        # DOC → HWP 변환 (한국 정부 사이트 특성)
        if extension == 'doc' and ('공고' in filename or '신청' in filename or '양식' in filename):
            extension = 'hwp'
        
        return {
            'real_name': filename,
            'extension': extension.upper(),
            'size': file_size,
            'content_type': content_type
        }
        
    except Exception as e:
        logging.error(f"파일 정보 추출 실패 ({url}): {str(e)[:100]}")
        # 에러 시에도 현재 타입이 DOC면 HWP로 추정
        if current_type == 'DOC':
            return {
                'real_name': f"공고문_{index}.hwp",
                'extension': 'HWP',
                'size': 0,
                'content_type': ''
            }
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
            current_type = attachment.get('type', 'UNKNOWN')
            current_filename = attachment.get('display_filename', '다운로드')
            
            if not url:
                updated_attachments.append(attachment)
                continue
            
            # DOC 타입이거나 파일명이 '다운로드'인 경우만 처리
            if current_type == 'DOC' or current_filename == '다운로드' or current_type == 'HTML':
                # 실제 파일 정보 가져오기
                file_info = get_real_file_info(url, pblanc_id, idx, current_type)
                
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
                
                logging.debug(f"{pblanc_id} - 파일 {idx}: {current_type} → {file_info['extension']}, {file_info['real_name']}")
            else:
                # 이미 정상적인 파일은 그대로 유지
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
                    progress['processed'] += len([a for a in attachments if a.get('type') == 'DOC' or a.get('display_filename') == '다운로드'])
                    if progress['success'] % 10 == 0:
                        logging.info(f"✅ 진행: {progress['success']}/{progress['total']} 공고, {progress['processed']}개 파일 수정")
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
    """메인 실행 - DOC 타입 우선 처리"""
    logging.info("=" * 60)
    logging.info("BizInfo 첨부파일 정보 업데이트 (K-Startup 방식)")
    logging.info("=" * 60)
    
    try:
        # DOC 타입이나 파일명이 '다운로드'인 공고만 조회
        result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .execute()
        
        # DOC 타입이나 '다운로드' 파일명이 있는 공고만 필터링
        announcements = []
        for ann in result.data:
            if ann.get('attachment_urls'):
                has_doc = any(
                    att.get('type') == 'DOC' or 
                    att.get('type') == 'HTML' or
                    att.get('display_filename') == '다운로드' 
                    for att in ann['attachment_urls']
                )
                if has_doc:
                    announcements.append(ann)
        
        progress['total'] = len(announcements)
        
        logging.info(f"처리 대상: {progress['total']}개 공고 (DOC/HTML 타입 또는 '다운로드' 파일명)")
        logging.info(f"병렬 처리 시작 (최대 10개 동시 실행)")
        
        start_time = time.time()
        
        # ThreadPoolExecutor로 병렬 처리 (BizInfo 서버 부하 고려하여 10개로 제한)
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 모든 작업 제출
            futures = {executor.submit(process_announcement_attachments, ann): ann for ann in announcements}
            
            # 완료되는 대로 처리
            for future in as_completed(futures):
                ann = futures[future]
                try:
                    success = future.result()
                    if not success:
                        logging.debug(f"처리 실패 또는 스킵: {ann['pblanc_id']}")
                except Exception as e:
                    logging.error(f"작업 실행 오류: {str(e)[:100]}")
                
                # 서버 부하 방지를 위한 짧은 대기
                time.sleep(0.1)
        
        elapsed_time = time.time() - start_time
        
        # 최종 결과
        logging.info("\n" + "=" * 60)
        logging.info("첨부파일 정보 업데이트 완료!")
        logging.info(f"✅ 성공: {progress['success']}/{progress['total']} 공고")
        logging.info(f"⏭️ 스킵: {progress['skip']}/{progress['total']} 공고 (이미 정상)")
        logging.info(f"❌ 실패: {progress['error']}/{progress['total']} 공고")
        logging.info(f"📎 수정된 파일: {progress['processed']}개")
        logging.info(f"⏱️ 소요 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
        logging.info(f"📊 처리 속도: {progress['processed']/elapsed_time:.1f}개/초")
        logging.info("=" * 60)
        
        # 샘플 확인
        sample = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .eq('pblanc_id', 'PBLN_000000000113616')\
            .execute()
        
        if not sample.data:
            # 다른 샘플 시도
            sample = supabase.table('bizinfo_complete')\
                .select('pblanc_id, pblanc_nm, attachment_urls')\
                .not_.is_('attachment_urls', 'null')\
                .limit(3)\
                .execute()
        
        logging.info("\n📋 업데이트된 샘플:")
        for s in sample.data[:3]:
            logging.info(f"\n공고: {s['pblanc_id']} - {s['pblanc_nm'][:30]}...")
            for att in s.get('attachment_urls', [])[:2]:
                logging.info(f"  - Type: {att.get('type')}")
                logging.info(f"    File: {att.get('display_filename')}")
        
    except Exception as e:
        logging.error(f"전체 처리 오류: {str(e)}")

if __name__ == "__main__":
    main()
