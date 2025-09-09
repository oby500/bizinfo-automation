#!/usr/bin/env python3
"""
K-Startup 상세페이지 병렬 파싱 및 bsns_sumry 업데이트
ThreadPoolExecutor로 동시 처리
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
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 환경변수 로드
load_dotenv()

# 로깅 설정
log_filename = f'kstartup_parallel_parser_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
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

# 스레드 안전 카운터
lock = threading.Lock()
progress = {'success': 0, 'error': 0, 'total': 0}

def clean_text(text):
    """텍스트 정리"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def parse_detail_page(url, announcement_id):
    """상세페이지 파싱하여 모든 정보 추출"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        parsed_data = {
            'sections': {},
            'tables': [],
            'attachments': [],
            'full_text': '',
            'structured_summary': ''
        }
        
        # 메인 컨텐츠 영역 찾기
        content_area = None
        for selector in ['.content', '.detail', '.view', '#content', 'article', '.board-view', '.board_view']:
            content_area = soup.select_one(selector)
            if content_area:
                break
        
        if not content_area:
            content_area = soup.find('body')
        
        # 전체 텍스트 추출 (빠른 처리)
        full_text = clean_text(content_area.get_text())
        parsed_data['full_text'] = full_text
        
        # 섹션별 추출 (간소화)
        all_text_parts = []
        
        # 제목과 내용 추출
        headings = content_area.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
        for heading in headings[:20]:  # 처음 20개만
            text = clean_text(heading.get_text())
            if text and len(text) > 3:
                all_text_parts.append(f"\n[{text}]")
                # 다음 단락 추출
                next_elem = heading.find_next_sibling()
                if next_elem:
                    content = clean_text(next_elem.get_text())[:500]
                    if content:
                        all_text_parts.append(content)
        
        # 테이블 데이터 추출 (주요 테이블만)
        tables = content_area.find_all('table')[:5]  # 처음 5개 테이블만
        for table in tables:
            rows = table.find_all('tr')[:10]  # 각 테이블당 10행만
            for row in rows:
                cells = row.find_all(['th', 'td'])
                row_text = ' | '.join([clean_text(cell.get_text())[:50] for cell in cells])
                if row_text:
                    all_text_parts.append(row_text)
        
        # 첨부파일 링크 추출
        file_links = content_area.find_all('a', href=True)[:30]  # 처음 30개 링크만
        for link in file_links:
            href = link.get('href', '')
            text = clean_text(link.get_text())
            
            if any(p in href.lower() or p in text.lower() 
                   for p in ['download', 'file', 'attach', '첨부', '.pdf', '.hwp', '.docx']):
                full_url = urljoin(url, href)
                parsed_data['attachments'].append({
                    'name': text or '첨부파일',
                    'url': full_url
                })
        
        # 구조화된 요약 생성 (간소화)
        summary_parts = []
        
        # 전체 내용 요약
        if full_text:
            # 처음 부분
            summary_parts.append(f"[개요]\n{full_text[:1000]}")
            
            # 중간 부분 (있으면)
            if len(full_text) > 2000:
                mid_point = len(full_text) // 2
                summary_parts.append(f"\n[주요 내용]\n{full_text[mid_point:mid_point+1000]}")
            
            # 마지막 부분 (일정/문의처 등)
            if len(full_text) > 1000:
                summary_parts.append(f"\n[추가 정보]\n{full_text[-500:]}")
        
        # 파싱된 구조 정보
        if all_text_parts:
            summary_parts.append(f"\n[세부 사항]\n{' '.join(all_text_parts[:50])}")
        
        # 첨부파일
        if parsed_data['attachments']:
            att_names = [att['name'] for att in parsed_data['attachments'][:10]]
            summary_parts.append(f"\n[첨부파일 {len(parsed_data['attachments'])}개]\n{', '.join(att_names)}")
        
        # 원문 전체 (글자 제한 없음)
        summary_parts.append(f"\n\n[원문 전체 - {len(full_text)}자]\n{full_text}")
        
        parsed_data['structured_summary'] = '\n'.join(summary_parts)
        
        return parsed_data
        
    except Exception as e:
        logging.error(f"파싱 오류 ({announcement_id}): {str(e)[:100]}")
        return None

def process_announcement(ann):
    """단일 공고 처리"""
    announcement_id = ann['announcement_id']
    title = ann['biz_pbanc_nm']
    detail_url = ann['detl_pg_url']
    
    try:
        # 상세페이지 파싱
        parsed_data = parse_detail_page(detail_url, announcement_id)
        
        if parsed_data and parsed_data['structured_summary']:
            # DB 업데이트
            update_data = {
                'bsns_sumry': parsed_data['structured_summary']
            }
            
            # pbanc_ctnt 업데이트 (비어있으면)
            if parsed_data['full_text'] and not ann.get('pbanc_ctnt'):
                update_data['pbanc_ctnt'] = parsed_data['full_text'][:10000]
            
            # 첨부파일 정보
            if parsed_data['attachments']:
                attachment_urls = []
                for idx, att in enumerate(parsed_data['attachments'], 1):
                    attachment_urls.append({
                        'url': att['url'],
                        'text': att['name'],
                        'type': 'FILE',
                        'params': {},
                        'safe_filename': f"KS_{announcement_id}_{idx:02d}",
                        'display_filename': att['name'],
                        'original_filename': att['name']
                    })
                update_data['attachment_urls'] = attachment_urls
                # attachment_count 제거 - attachment_urls 길이로 계산 가능
            
            # DB 업데이트
            result = supabase.table('kstartup_complete')\
                .update(update_data)\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    if progress['success'] % 10 == 0:
                        logging.info(f"✅ 진행: {progress['success']}/{progress['total']} ({progress['success']/progress['total']*100:.1f}%)")
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
    logging.info("K-Startup 병렬 파싱 시작")
    logging.info("=" * 60)
    
    # 처리 제한 확인 (환경변수로 받음)
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '0'))
    
    # 공고 조회
    try:
        if processing_limit > 0:
            # Daily 모드: 최근 50개만
            result = supabase.table('kstartup_complete')\
                .select('announcement_id, biz_pbanc_nm, detl_pg_url, pbanc_ctnt')\
                .not_.is_('detl_pg_url', 'null')\
                .order('created_at', desc=True)\
                .limit(processing_limit)\
                .execute()
            logging.info(f"Daily 모드: 최근 {processing_limit}개만 처리")
        else:
            # Full 모드: 전체
            result = supabase.table('kstartup_complete')\
                .select('announcement_id, biz_pbanc_nm, detl_pg_url, pbanc_ctnt')\
                .not_.is_('detl_pg_url', 'null')\
                .execute()
            logging.info("Full 모드: 전체 처리")
        
        announcements = result.data
        progress['total'] = len(announcements)
        
        logging.info(f"처리 대상: {progress['total']}개")
        logging.info(f"병렬 처리 시작 (최대 20개 동시 실행)")
        
        # ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 모든 작업 제출
            futures = {executor.submit(process_announcement, ann): ann for ann in announcements}
            
            # 완료되는 대로 처리
            for future in as_completed(futures):
                ann = futures[future]
                try:
                    success = future.result()
                    if not success:
                        logging.debug(f"처리 실패: {ann['announcement_id']}")
                except Exception as e:
                    logging.error(f"작업 실행 오류: {str(e)[:100]}")
        
        # 최종 결과
        logging.info("\n" + "=" * 60)
        logging.info("파싱 완료!")
        logging.info(f"✅ 성공: {progress['success']}/{progress['total']}")
        logging.info(f"❌ 실패: {progress['error']}/{progress['total']}")
        logging.info(f"⏱️ 전체 소요 시간: 병렬 처리로 단축")
        logging.info("=" * 60)
        
    except Exception as e:
        logging.error(f"전체 처리 오류: {str(e)}")

if __name__ == "__main__":
    main()