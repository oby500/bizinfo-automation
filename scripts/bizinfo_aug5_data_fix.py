#!/usr/bin/env python3
"""
BizInfo 8월 5일 데이터 완전 재처리
- type="getImageFile" → 실제 파일 타입으로 변환
- 파일명 "다운로드" → 실제 파일명 추출
- 깨진 인코딩 복구
"""
import os
import sys
import requests
import json
import time
import re
from supabase import create_client
from dotenv import load_dotenv
import logging
from datetime import datetime
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_filename = f'bizinfo_aug5_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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

def get_file_type_from_extension(filename):
    """파일명에서 확장자 추출하여 타입 결정"""
    if not filename:
        return 'HWP'
    
    filename = filename.lower()
    if '.hwp' in filename:
        return 'HWP'
    elif '.pdf' in filename:
        return 'PDF'
    elif '.doc' in filename:
        return 'DOC'
    elif '.docx' in filename:
        return 'DOCX'
    elif '.xls' in filename:
        return 'XLS'
    elif '.xlsx' in filename:
        return 'XLSX'
    elif '.ppt' in filename:
        return 'PPT'
    elif '.pptx' in filename:
        return 'PPTX'
    elif '.zip' in filename:
        return 'ZIP'
    elif '.jpg' in filename or '.jpeg' in filename:
        return 'JPG'
    elif '.png' in filename:
        return 'PNG'
    elif '.gif' in filename:
        return 'GIF'
    elif '.txt' in filename:
        return 'TXT'
    else:
        # 한국 정부 사이트 특성상 대부분 HWP
        return 'HWP'

def fix_broken_encoding(text):
    """깨진 인코딩 복구"""
    if not text or text == '다운로드':
        return None
    
    # 깨진 문자 패턴이 없으면 원본 반환
    broken_patterns = ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']
    if not any(p in text for p in broken_patterns):
        return text
    
    try:
        # 이중 인코딩 복구
        if 'Ã' in text and 'Â' in text:
            fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
            fixed = fixed.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
            if any(k in fixed for k in ['참', '신청', '공고', '년']):
                return fixed
        
        # 단일 인코딩 복구
        fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
        if any(k in fixed for k in ['참', '신청', '공고', '년']):
            return fixed
    except:
        pass
    
    return text

def process_announcement(ann):
    """단일 공고 처리"""
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
            current_type = attachment.get('type', '')
            current_filename = attachment.get('display_filename', '')
            
            needs_fix = False
            new_type = current_type
            new_filename = current_filename
            
            # 1. type이 getImageFile인 경우 -> 파일명에서 타입 추출
            if current_type == 'getImageFile':
                new_type = get_file_type_from_extension(current_filename)
                needs_fix = True
            
            # 2. type이 DOC, HTML, UNKNOWN인 경우 -> HWP로 변경
            elif current_type in ['DOC', 'HTML', 'UNKNOWN']:
                # 파일명 확인 후 적절한 타입 설정
                if current_filename:
                    new_type = get_file_type_from_extension(current_filename)
                else:
                    new_type = 'HWP'
                needs_fix = True
            
            # 3. 파일명이 "다운로드"이거나 깨진 경우
            if current_filename == '다운로드' or any(c in current_filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']):
                # safe_filename에서 확장자 추출
                safe_filename = attachment.get('safe_filename', '')
                if safe_filename and '.' in safe_filename:
                    ext = safe_filename.split('.')[-1].upper()
                    if not current_filename or current_filename == '다운로드':
                        new_filename = f"첨부파일_{idx}.{ext.lower()}"
                    else:
                        # 깨진 파일명 복구 시도
                        fixed = fix_broken_encoding(current_filename)
                        if fixed:
                            new_filename = fixed
                        else:
                            new_filename = f"첨부파일_{idx}.{ext.lower()}"
                    needs_fix = True
            
            if needs_fix:
                # 업데이트된 첨부파일 정보
                updated_attachment = {
                    'url': url,
                    'text': '다운로드',
                    'type': new_type,
                    'params': attachment.get('params', {}),
                    'safe_filename': attachment.get('safe_filename', f"{pblanc_id}_{idx:02d}.{new_type.lower()}"),
                    'display_filename': new_filename,
                    'original_filename': new_filename
                }
                updated_attachments.append(updated_attachment)
                has_changes = True
                fixed_count += 1
                logging.debug(f"{pblanc_id} - 파일 {idx}: type={current_type}→{new_type}, name={current_filename[:20]}→{new_filename[:20]}")
            else:
                updated_attachments.append(attachment)
        
        # DB 업데이트
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
                    if progress['success'] % 50 == 0:
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
    logging.info("BizInfo 8월 5일 데이터 완전 재처리")
    logging.info("=" * 60)
    
    try:
        # 문제가 있는 데이터 조회
        logging.info("문제 데이터 조회 중...")
        
        # type이 getImageFile, DOC, HTML, UNKNOWN이거나 파일명이 "다운로드"인 경우
        result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .execute()
        
        # 문제 데이터 필터링
        announcements = []
        total_problem_files = 0
        
        for ann in result.data:
            if ann.get('attachment_urls'):
                needs_processing = False
                problem_count = 0
                
                for att in ann['attachment_urls']:
                    file_type = att.get('type', '')
                    filename = att.get('display_filename', '')
                    
                    # 문제 케이스 체크
                    if file_type in ['getImageFile', 'DOC', 'HTML', 'UNKNOWN']:
                        needs_processing = True
                        problem_count += 1
                    elif filename == '다운로드' or any(c in filename for c in ['â', 'ì', 'ë', 'í', 'ê', 'ã', 'Ã', 'Â']):
                        needs_processing = True
                        problem_count += 1
                
                if needs_processing:
                    announcements.append(ann)
                    total_problem_files += problem_count
        
        progress['total'] = len(announcements)
        
        logging.info(f"전체 공고: {len(result.data)}개")
        logging.info(f"문제 공고: {progress['total']}개")
        logging.info(f"문제 파일: {total_problem_files}개")
        
        if progress['total'] == 0:
            logging.info("✅ 처리할 문제 데이터가 없습니다!")
            return
        
        logging.info(f"병렬 처리 시작 (최대 10개 동시 실행)")
        
        start_time = time.time()
        
        # ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_announcement, ann): ann for ann in announcements}
            
            for future in as_completed(futures):
                try:
                    future.result(timeout=30)
                except Exception as e:
                    logging.error(f"작업 실행 오류: {str(e)[:100]}")
                
                # 서버 부하 방지
                time.sleep(0.1)
        
        elapsed_time = time.time() - start_time
        
        # 최종 결과
        logging.info("\n" + "=" * 60)
        logging.info("8월 5일 데이터 재처리 완료!")
        logging.info(f"✅ 성공: {progress['success']}/{progress['total']} 공고")
        logging.info(f"⏭️ 스킵: {progress['skip']}/{progress['total']} 공고")
        logging.info(f"❌ 실패: {progress['error']}/{progress['total']} 공고")
        logging.info(f"🔧 수정된 파일: {progress['fixed']}개")
        logging.info(f"⏱️ 소요 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
        
        if total_problem_files > 0:
            fix_rate = (progress['fixed'] / total_problem_files) * 100
            logging.info(f"📊 수정률: {fix_rate:.1f}%")
        
        logging.info("=" * 60)
        
        # 최종 확인
        check_result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, attachment_urls')\
            .limit(100)\
            .execute()
        
        remaining_problems = 0
        for item in check_result.data:
            if item.get('attachment_urls'):
                for att in item['attachment_urls']:
                    if att.get('type') in ['getImageFile', 'DOC', 'HTML', 'UNKNOWN']:
                        remaining_problems += 1
                    elif att.get('display_filename') == '다운로드':
                        remaining_problems += 1
        
        if remaining_problems > 0:
            logging.warning(f"\n⚠️ 샘플 100개 중 {remaining_problems}개 문제 파일 발견")
        else:
            logging.info("\n✅ 샘플 확인 결과: 모든 파일이 정상입니다!")
        
    except Exception as e:
        logging.error(f"전체 처리 오류: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    main()
