#!/usr/bin/env python3
"""
기업마당 전체 공고 첨부파일 정보 크롤링 - 속도 강화 버전
- 멀티스레딩으로 동시 처리
- 배치 처리 최적화
- 연결 풀 사용
"""
import os
import sys
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, parse_qs, urlparse
import time
import re
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import queue
from supabase import create_client

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'bizinfo_fast_crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

# 성능 설정
MAX_WORKERS = 10  # 동시 처리 스레드 수
BATCH_SIZE = 100  # 배치 크기
REQUEST_TIMEOUT = 10  # 요청 타임아웃 (초)
RETRY_COUNT = 2  # 재시도 횟수

# 세션 풀 관리
session_pool = queue.Queue(maxsize=MAX_WORKERS)
for _ in range(MAX_WORKERS):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive'
    })
    session_pool.put(session)

# 통계 관리
stats_lock = Lock()
stats = {
    'processed': 0,
    'with_attachments': 0,
    'with_hashtags': 0,
    'failed': 0,
    'total': 0
}

def get_session():
    """세션 풀에서 세션 가져오기"""
    return session_pool.get()

def return_session(session):
    """세션 풀에 세션 반환"""
    session_pool.put(session)

def extract_file_type(text):
    """파일명에서 확장자 추측"""
    text_lower = text.lower()
    if '.hwp' in text_lower or '한글' in text_lower:
        return 'HWP'
    elif '.pdf' in text_lower:
        return 'PDF'
    elif '.doc' in text_lower:
        return 'DOCX'
    elif '.xls' in text_lower:
        return 'XLSX'
    elif '.zip' in text_lower:
        return 'ZIP'
    elif '.ppt' in text_lower:
        return 'PPT'
    elif any(ext in text_lower for ext in ['.jpg', '.jpeg', '.png', '.gif']):
        return 'IMAGE'
    else:
        return 'UNKNOWN'

def clean_filename(text):
    """파일명 정리"""
    if not text:
        return None
    
    # 파일명 패턴 매칭
    patterns = [
        r'([^\/\\:*?"<>|\n\r\t]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            filename = match.group(1).strip()
            filename = re.sub(r'^(첨부파일\s*|다운로드\s*)', '', filename)
            filename = re.sub(r'\s*(다운로드|첨부파일)\s*$', '', filename)
            return filename
    
    return None

def process_single_announcement(data):
    """단일 공고 처리 (스레드에서 실행)"""
    pblanc_id = data['pblanc_id']
    pblanc_nm = data['pblanc_nm']
    dtl_url = data.get('dtl_url')
    
    if not dtl_url:
        return pblanc_id, [], [], "NO_URL"
    
    session = get_session()
    try:
        # 재시도 로직
        for attempt in range(RETRY_COUNT):
            try:
                response = session.get(dtl_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                break
            except Exception as e:
                if attempt == RETRY_COUNT - 1:
                    raise e
                time.sleep(1)
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 첨부파일 추출
        attachments = []
        unique_files = {}
        
        # 모든 링크에서 첨부파일 패턴 찾기
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # atchFileId 패턴 찾기
            if 'atchFileId=' in href:
                # URL 파라미터 추출
                atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                file_sn = '0'
                if 'fileSn=' in href:
                    file_sn = href.split('fileSn=')[1].split('&')[0]
                
                unique_key = f"{atch_file_id}_{file_sn}"
                
                if unique_key not in unique_files:
                    # 직접 URL 구성
                    direct_url = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                    
                    file_type = extract_file_type(text)
                    display_filename = clean_filename(text) or text
                    
                    attachment = {
                        'url': direct_url,
                        'type': file_type,
                        'safe_filename': f"{pblanc_id}_{len(attachments)+1:02d}.{file_type.lower()}",
                        'display_filename': display_filename,
                        'original_filename': display_filename,
                        'text': text,
                        'params': {
                            'atchFileId': atch_file_id,
                            'fileSn': file_sn
                        }
                    }
                    
                    unique_files[unique_key] = attachment
                    attachments.append(attachment)
        
        # 해시태그 추출
        hashtags = []
        tag_list = soup.find('ul', class_='tag_ul_list')
        if tag_list:
            tag_items = tag_list.find_all('li', class_=re.compile(r'tag_li_list\d'))
            for item in tag_items:
                link = item.find('a')
                if link:
                    tag_text = link.get_text(strip=True)
                    if tag_text and tag_text not in hashtags:
                        hashtags.append(tag_text)
        
        return pblanc_id, attachments, hashtags, "SUCCESS"
        
    except requests.exceptions.Timeout:
        return pblanc_id, [], [], "TIMEOUT"
    except Exception as e:
        logging.debug(f"크롤링 오류 ({pblanc_id}): {e}")
        return pblanc_id, [], [], f"ERROR: {str(e)[:50]}"
    finally:
        return_session(session)

def update_batch_to_db(supabase, results):
    """배치 결과를 DB에 업데이트"""
    try:
        for pblanc_id, attachments, hashtags, status in results:
            if status == "SUCCESS" or (status == "NO_URL"):
                update_data = {
                    'attachment_urls': attachments,
                    'attachment_processing_status': {
                        'processed': True,
                        'count': len(attachments),
                        'hashtag_count': len(hashtags),
                        'processed_at': datetime.now().isoformat(),
                        'status': status
                    }
                }
                
                if hashtags:
                    update_data['hash_tag'] = ', '.join(hashtags)
                
                # Supabase 업데이트
                supabase.table('bizinfo_complete').update(
                    update_data
                ).eq('pblanc_id', pblanc_id).execute()
                
                # 통계 업데이트
                with stats_lock:
                    stats['processed'] += 1
                    if attachments:
                        stats['with_attachments'] += 1
                    if hashtags:
                        stats['with_hashtags'] += 1
            else:
                with stats_lock:
                    stats['failed'] += 1
        
        return True
        
    except Exception as e:
        logging.error(f"DB 업데이트 오류: {e}")
        return False

def process_batch_parallel(batch):
    """배치를 병렬로 처리"""
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 모든 작업 제출
        future_to_data = {
            executor.submit(process_single_announcement, data): data 
            for data in batch
        }
        
        # 완료된 작업 수집
        for future in as_completed(future_to_data):
            data = future_to_data[future]
            try:
                result = future.result(timeout=REQUEST_TIMEOUT * 2)
                results.append(result)
                
                # 진행 상황 출력
                pblanc_id = result[0]
                attachments = result[1]
                hashtags = result[2]
                status = result[3]
                
                with stats_lock:
                    current = stats['processed'] + stats['failed'] + 1
                    total = stats['total']
                
                if status == "SUCCESS":
                    logging.info(f"[{current}/{total}] {pblanc_id}: 첨부 {len(attachments)}개, 태그 {len(hashtags)}개")
                elif status == "NO_URL":
                    logging.info(f"[{current}/{total}] {pblanc_id}: URL 없음")
                else:
                    logging.warning(f"[{current}/{total}] {pblanc_id}: {status}")
                    
            except Exception as e:
                logging.error(f"작업 실행 오류: {e}")
                results.append((data['pblanc_id'], [], [], f"EXCEPTION: {str(e)[:50]}"))
    
    return results

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print(" 기업마당 첨부파일 고속 크롤링")
    print("=" * 60)
    print(f"동시 처리 스레드: {MAX_WORKERS}개")
    print(f"배치 크기: {BATCH_SIZE}개")
    print("=" * 60)
    
    # Supabase 연결
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ 환경변수가 설정되지 않았습니다.")
        print("SUPABASE_URL과 SUPABASE_KEY를 설정하세요.")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    logging.info("✅ Supabase 연결 성공")
    
    # 처리 대상 조회
    print("\n1. 처리 대상 조회 중...")
    try:
        # attachment_urls가 null이거나 빈 배열인 데이터 우선 처리
        response = supabase.table('bizinfo_complete').select(
            'id', 'pblanc_id', 'pblanc_nm', 'dtl_url'
        ).or_(
            'attachment_urls.is.null',
            'attachment_urls.eq.[]'
        ).execute()
        
        unprocessed = response.data
        
        # 전체 데이터도 가져오기 (재처리용)
        response_all = supabase.table('bizinfo_complete').select(
            'id', 'pblanc_id', 'pblanc_nm', 'dtl_url'
        ).execute()
        
        all_data = response_all.data
        
        print(f"✅ 전체 데이터: {len(all_data)}개")
        print(f"✅ 미처리 데이터: {len(unprocessed)}개")
        
        # 미처리 데이터 우선, 그 다음 전체 재처리
        targets = unprocessed + [d for d in all_data if d not in unprocessed]
        
    except Exception as e:
        print(f"❌ 데이터 조회 오류: {e}")
        sys.exit(1)
    
    if not targets:
        print("처리할 데이터가 없습니다.")
        return
    
    # 통계 초기화
    stats['total'] = len(targets)
    
    print(f"\n2. 크롤링 시작 (총 {len(targets)}개)")
    print("-" * 60)
    
    start_time = time.time()
    
    try:
        # 배치 단위로 처리
        for i in range(0, len(targets), BATCH_SIZE):
            batch = targets[i:i+BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(targets) + BATCH_SIZE - 1) // BATCH_SIZE
            
            logging.info(f"\n배치 {batch_num}/{total_batches} 처리 중...")
            
            # 배치 병렬 처리
            results = process_batch_parallel(batch)
            
            # DB 업데이트
            if results:
                update_batch_to_db(supabase, results)
            
            # 진행 상황 출력
            with stats_lock:
                print(f"\n진행 상황: {stats['processed']}/{stats['total']} 완료")
                print(f"  - 첨부파일 있음: {stats['with_attachments']}개")
                print(f"  - 해시태그 있음: {stats['with_hashtags']}개")
                print(f"  - 실패: {stats['failed']}개")
            
            # 다음 배치 전 잠시 대기 (서버 부하 방지)
            if i + BATCH_SIZE < len(targets):
                time.sleep(2)
                
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단됨")
    except Exception as e:
        logging.error(f"예상치 못한 오류: {e}")
    
    # 최종 결과
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print(" 크롤링 완료")
    print("=" * 60)
    print(f"✅ 처리 완료: {stats['processed']}개")
    print(f"📎 첨부파일 있음: {stats['with_attachments']}개")
    print(f"🏷️ 해시태그 있음: {stats['with_hashtags']}개")
    print(f"❌ 실패: {stats['failed']}개")
    print(f"⏱️ 소요 시간: {elapsed_time:.1f}초")
    print(f"📊 처리 속도: {stats['processed']/elapsed_time:.1f}개/초")
    print("=" * 60)

if __name__ == "__main__":
    main()