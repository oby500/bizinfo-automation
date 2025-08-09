#!/usr/bin/env python3
"""
기업마당 통합 처리 스크립트 (고속 버전)
- 병렬 처리로 속도 개선
- 배치 업데이트로 DB 부하 감소
"""
import os
import sys
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, parse_qs, urlparse
import re
from supabase import create_client, Client
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class BizInfoCompleteProcessorFast:
    def __init__(self):
        """초기화"""
        # Supabase 연결
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            logging.error("환경변수가 설정되지 않았습니다.")
            sys.exit(1)
            
        self.supabase: Client = create_client(url, key)
        
        # 헤더 설정
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.bizinfo.go.kr/'
        }
        
        # 세션 재사용 (연결 재사용으로 속도 향상)
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logging.info("=== 기업마당 고속 처리 시작 ===")
    
    def clean_filename(self, text):
        """파일명 정리"""
        if not text:
            return None
        
        patterns = [
            r'([^\/\\:*?"<>|\n\r\t]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b',
            r'([^\s]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                filename = match.group(1).strip()
                filename = re.sub(r'^(첨부파일\s*|다운로드\s*)', '', filename)
                filename = re.sub(r'\s*(다운로드|첨부파일)\s*$', '', filename)
                return filename
        
        return None
    
    def create_safe_filename(self, pblanc_id, index, original_filename):
        """안전한 파일명 생성"""
        if original_filename:
            ext = ''
            if '.' in original_filename:
                ext = original_filename.split('.')[-1].lower()
                if len(ext) > 10:
                    ext = 'unknown'
            else:
                ext = 'unknown'
            
            return f"{pblanc_id}_{index:02d}.{ext}"
        
        return f"{pblanc_id}_{index:02d}.unknown"
    
    def extract_hashtags_from_page(self, soup):
        """페이지에서 해시태그 추출"""
        hashtags = []
        
        try:
            tag_list = soup.find('ul', class_='tag_ul_list')
            if tag_list:
                tag_items = tag_list.find_all('li', class_=re.compile(r'tag_li_list\d'))
                for item in tag_items:
                    link = item.find('a')
                    if link:
                        tag_text = link.get_text(strip=True)
                        if tag_text and tag_text not in hashtags:
                            hashtags.append(tag_text)
        except:
            pass
        
        return hashtags
    
    def process_single_item(self, item: Dict) -> Dict:
        """단일 항목 처리 (병렬 처리용)"""
        try:
            result = {
                'id': item['id'],
                'pblanc_id': item['pblanc_id'],
                'pblanc_nm': item['pblanc_nm'],
                'success': False,
                'attachments': [],
                'hashtags': '',
                'summary': '',
                'error': None
            }
            
            # 첨부파일 크롤링
            if item.get('dtl_url'):
                attachments, page_hashtags = self.extract_attachments_fast(
                    item['pblanc_id'], 
                    item['dtl_url']
                )
                result['attachments'] = attachments
                
                # 해시태그 생성
                hashtags = self.generate_hashtags(item, page_hashtags)
                result['hashtags'] = hashtags
                
                # 요약 생성
                summary = self.create_summary(item, attachments, hashtags)
                result['summary'] = summary
                
                result['success'] = True
            
            return result
            
        except Exception as e:
            return {
                'id': item['id'],
                'pblanc_id': item.get('pblanc_id', 'unknown'),
                'pblanc_nm': item.get('pblanc_nm', ''),
                'success': False,
                'attachments': [],
                'hashtags': '',
                'summary': '',
                'error': str(e)
            }
    
    def extract_attachments_fast(self, pblanc_id, detail_url):
        """빠른 첨부파일 추출 (HEAD 요청 생략)"""
        if not detail_url:
            return [], []
        
        try:
            # 세션 사용으로 연결 재사용
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            attachments = []
            
            # 해시태그 추출
            page_hashtags = self.extract_hashtags_from_page(soup)
            
            # 첨부파일 패턴
            patterns = [
                {'regex': r'getImageFile\.do', 'type': 'getImageFile'},
                {'regex': r'FileDownload\.do', 'type': 'FileDownload'},
                {'regex': r'downloadFile', 'type': 'downloadFile'},
                {'regex': r'download\.do', 'type': 'download'},
                {'regex': r'/cmm/fms/', 'type': 'fms'}
            ]
            
            # 모든 링크 검사 (최적화)
            all_links = soup.find_all('a', href=True)
            attachment_index = 0
            processed_urls = set()  # 중복 체크용
            
            for link in all_links:
                href = link.get('href', '')
                if not href:
                    continue
                    
                # 패턴 매칭
                matched = False
                for pattern in patterns:
                    if re.search(pattern['regex'], href):
                        matched = True
                        break
                
                if not matched:
                    continue
                
                text = link.get_text(strip=True)
                onclick = link.get('onclick', '')
                title = link.get('title', '')
                
                # onclick에서 URL 추출
                if onclick and not href:
                    url_match = re.search(r"['\"]([^'\"]*" + pattern['regex'] + r"[^'\"]*)['\"]", onclick)
                    if url_match:
                        href = url_match.group(1)
                
                if href:
                    full_url = urljoin(detail_url, href)
                    
                    # 중복 체크
                    if full_url in processed_urls:
                        continue
                    processed_urls.add(full_url)
                    
                    attachment_index += 1
                    
                    # 파일명 찾기 (HEAD 요청 생략)
                    display_filename = None
                    original_filename = text or '첨부파일'
                    
                    # 링크 텍스트에서 파일명 찾기
                    if text and text != '다운로드':
                        display_filename = self.clean_filename(text)
                        if display_filename:
                            original_filename = display_filename
                    
                    # title 속성에서 찾기
                    if not display_filename and title:
                        display_filename = self.clean_filename(title)
                        if display_filename:
                            original_filename = display_filename
                    
                    # display_filename이 없으면 기본값
                    if not display_filename:
                        display_filename = f"첨부파일_{attachment_index}"
                    
                    # safe_filename 생성
                    safe_filename = self.create_safe_filename(pblanc_id, attachment_index, display_filename)
                    
                    # 파일 타입 결정
                    file_type = self.get_file_type(display_filename, href)
                    
                    # URL 파라미터 추출
                    parsed = urlparse(full_url)
                    params = parse_qs(parsed.query)
                    
                    attachment = {
                        'url': full_url,
                        'text': '다운로드',
                        'type': file_type,
                        'params': {k: v[0] if len(v) == 1 else v for k, v in params.items()},
                        'safe_filename': safe_filename,
                        'display_filename': display_filename,
                        'original_filename': original_filename
                    }
                    
                    attachments.append(attachment)
            
            return attachments, page_hashtags
            
        except Exception as e:
            logging.debug(f"첨부파일 크롤링 오류: {e}")
            return [], []
    
    def get_file_type(self, filename, url):
        """파일 타입 추출"""
        text_lower = filename.lower() if filename else ''
        url_lower = url.lower()
        
        if any(ext in text_lower + url_lower for ext in ['.hwp', 'hwp']):
            return 'HWP'
        elif any(ext in text_lower + url_lower for ext in ['.pdf', 'pdf']):
            return 'PDF'
        elif any(ext in text_lower + url_lower for ext in ['.doc', '.docx', 'word']):
            return 'DOC'
        elif any(ext in text_lower + url_lower for ext in ['.xls', '.xlsx', 'excel']):
            return 'EXCEL'
        elif any(ext in text_lower + url_lower for ext in ['.ppt', '.pptx']):
            return 'PPT'
        elif any(ext in text_lower + url_lower for ext in ['.zip', '.rar']):
            return 'ZIP'
        elif any(ext in text_lower + url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return 'IMAGE'
        else:
            return 'FILE'
    
    def generate_hashtags(self, item, page_hashtags=None):
        """해시태그 생성"""
        tags = []
        
        if page_hashtags:
            tags.extend(page_hashtags[:5])
        
        if item.get('sprt_realm_nm'):
            field = item['sprt_realm_nm']
            field_tags = [t.strip() for t in field.split(',') if t.strip()]
            tags.extend(field_tags[:3])
        
        if item.get('spnsr_organ_nm'):
            org = item['spnsr_organ_nm'].replace('(주)', '').strip()
            if len(org) <= 10:
                tags.append(org)
        
        if item.get('pblanc_nm'):
            title = item['pblanc_nm']
            title_keywords = ['R&D', 'AI', '인공지능', '빅데이터', '바이오', '환경', '그린',
                            '디지털', '혁신', '글로벌', '수출', '기술개발', '사업화', '투자',
                            '스타트업', '중소기업', '소상공인', '창업']
            for keyword in title_keywords:
                if keyword.lower() in title.lower():
                    tags.append(keyword)
        
        unique_tags = list(dict.fromkeys(tags))
        hashtags = ' '.join([f'#{tag.strip()}' for tag in unique_tags[:10]])
        
        return hashtags
    
    def create_summary(self, item, attachments, hashtags):
        """요약 생성"""
        summary_parts = []
        
        if item.get('pblanc_nm'):
            summary_parts.append(f"📋 {item['pblanc_nm']}")
        
        if item.get('spnsr_organ_nm'):
            summary_parts.append(f"🏢 주관: {item['spnsr_organ_nm']}")
        elif item.get('exctv_organ_nm'):
            summary_parts.append(f"🏢 수행: {item['exctv_organ_nm']}")
        
        if item.get('reqst_begin_ymd') and item.get('reqst_end_ymd'):
            start_date = item['reqst_begin_ymd']
            end_date = item['reqst_end_ymd']
            summary_parts.append(f"📅 기간: {start_date} ~ {end_date}")
            
            try:
                if end_date:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d') if '-' in end_date else datetime.strptime(end_date, '%Y%m%d')
                    days_left = (end_dt - datetime.now()).days
                    
                    if 0 <= days_left <= 3:
                        summary_parts.append(f"🚨 마감임박 D-{days_left}")
                    elif 4 <= days_left <= 7:
                        summary_parts.append(f"⏰ D-{days_left}")
                    elif days_left > 0:
                        summary_parts.append(f"📆 D-{days_left}")
            except:
                pass
        
        if attachments:
            file_types = list(set([a['type'] for a in attachments]))
            summary_parts.append(f"📎 첨부: {', '.join(file_types)} ({len(attachments)}개)")
        
        if hashtags:
            summary_parts.append(f"🏷️ {hashtags}")
        
        return '\n'.join(summary_parts)
    
    def batch_update_database(self, results: List[Dict]) -> Tuple[int, int]:
        """배치 DB 업데이트"""
        success_count = 0
        error_count = 0
        
        for result in results:
            if not result['success']:
                error_count += 1
                if result['error']:
                    logging.error(f"처리 실패 [{result['pblanc_id']}]: {result['error']}")
                continue
            
            try:
                update_data = {
                    'attachment_urls': result['attachments'] if result['attachments'] else [],
                    'hash_tag': result['hashtags'],
                    'bsns_sumry': result['summary'],
                    'attachment_processing_status': 'completed',
                    'updt_dt': datetime.now().isoformat()
                }
                
                self.supabase.table('bizinfo_complete').update(
                    update_data
                ).eq('id', result['id']).execute()
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                logging.error(f"DB 업데이트 오류 [{result['pblanc_id']}]: {e}")
        
        return success_count, error_count
    
    def get_unprocessed_announcements(self, limit=None):
        """처리 안 된 공고 조회"""
        try:
            query = self.supabase.table('bizinfo_complete').select(
                'id', 'pblanc_id', 'pblanc_nm', 'dtl_url',
                'spnsr_organ_nm', 'exctv_organ_nm', 'sprt_realm_nm',
                'reqst_begin_ymd', 'reqst_end_ymd', 'attachment_urls'
            ).order('created_at', desc=True).limit(500)
            
            result = query.execute()
            
            unprocessed = []
            for item in result.data:
                if not item.get('attachment_urls'):
                    item.pop('attachment_urls', None)
                    unprocessed.append(item)
                else:
                    urls_str = json.dumps(item['attachment_urls'])
                    if 'safe_filename' not in urls_str:
                        item.pop('attachment_urls', None)
                        unprocessed.append(item)
                
                if limit and len(unprocessed) >= limit:
                    break
            
            return unprocessed[:limit] if limit else unprocessed[:200]  # 최대 200개
            
        except Exception as e:
            logging.error(f"데이터 조회 오류: {e}")
            return []
    
    def run(self):
        """전체 프로세스 실행 (병렬 처리)"""
        try:
            # Step 1: 처리 대상 조회
            unprocessed = self.get_unprocessed_announcements(limit=200)  # 한 번에 200개
            logging.info(f"처리 대상: {len(unprocessed)}개")
            
            if not unprocessed:
                logging.info("처리할 데이터가 없습니다.")
                return
            
            # Step 2: 병렬 처리
            batch_size = 20  # 동시 처리 개수
            all_results = []
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                # 배치 단위로 처리
                for i in range(0, len(unprocessed), batch_size):
                    batch = unprocessed[i:i+batch_size]
                    logging.info(f"\n배치 {i//batch_size + 1}/{(len(unprocessed)-1)//batch_size + 1} 처리 중...")
                    
                    # 병렬 작업 시작
                    futures = {
                        executor.submit(self.process_single_item, item): item 
                        for item in batch
                    }
                    
                    # 결과 수집
                    batch_results = []
                    for future in as_completed(futures):
                        try:
                            result = future.result(timeout=30)
                            batch_results.append(result)
                            
                            # 진행 상황 로깅
                            if result['success']:
                                att_count = len(result['attachments'])
                                logging.info(f"  ✓ {result['pblanc_nm'][:30]}... ({att_count}개 첨부)")
                            else:
                                logging.warning(f"  ✗ {result['pblanc_nm'][:30]}...")
                                
                        except Exception as e:
                            item = futures[future]
                            logging.error(f"  ✗ 처리 실패: {item.get('pblanc_nm', 'unknown')[:30]}...")
                    
                    all_results.extend(batch_results)
                    
                    # 배치 DB 업데이트
                    if batch_results:
                        success, error = self.batch_update_database(batch_results)
                        logging.info(f"  배치 결과: 성공 {success}개, 실패 {error}개")
                    
                    # 다음 배치 전 짧은 대기 (API 부하 방지)
                    if i + batch_size < len(unprocessed):
                        time.sleep(1)
            
            # 결과 요약
            total_success = sum(1 for r in all_results if r['success'])
            total_error = len(all_results) - total_success
            total_attachments = sum(len(r['attachments']) for r in all_results if r['success'])
            
            logging.info("\n" + "="*50)
            logging.info("📊 처리 결과")
            logging.info(f"  전체: {len(all_results)}개")
            logging.info(f"  성공: {total_success}개")
            logging.info(f"  실패: {total_error}개")
            logging.info(f"  첨부파일: {total_attachments}개")
            logging.info(f"  처리 시간: 약 {len(unprocessed)//batch_size + 1}분")
            logging.info("="*50)
            
        except Exception as e:
            logging.error(f"처리 중 오류: {e}")
            raise
        finally:
            # 세션 종료
            self.session.close()

if __name__ == "__main__":
    processor = BizInfoCompleteProcessorFast()
    processor.run()
