#!/usr/bin/env python3
"""
K-Startup 통합 처리 스크립트 (고속 버전)
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

class KStartupCompleteProcessorFast:
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
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 세션 재사용 (연결 재사용으로 속도 향상)
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logging.info("=== K-Startup 고속 처리 시작 ===")
    
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
    
    def create_safe_filename(self, announcement_id, index, original_filename):
        """안전한 파일명 생성"""
        if original_filename:
            ext = ''
            if '.' in original_filename:
                ext = original_filename.split('.')[-1].lower()
                if len(ext) > 10:
                    ext = 'unknown'
            else:
                ext = 'unknown'
            
            return f"{announcement_id}_{index:02d}.{ext}"
        
        return f"{announcement_id}_{index:02d}.unknown"
    
    def extract_hashtags_from_page(self, soup):
        """페이지에서 해시태그 추출"""
        hashtags = []
        
        try:
            # K-Startup 페이지의 태그 구조 찾기
            keyword_areas = soup.find_all(['div', 'span', 'p'], class_=re.compile(r'keyword|tag|field', re.I))
            for area in keyword_areas:
                text = area.get_text(strip=True)
                if text and len(text) < 20:
                    hashtags.append(text)
            
            # 테이블에서 분야 정보 찾기
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        header = th.get_text(strip=True)
                        if '분야' in header or '업종' in header or '키워드' in header:
                            value = td.get_text(strip=True)
                            if value and len(value) < 30:
                                tags = [t.strip() for t in value.split(',')]
                                hashtags.extend(tags[:3])
        except:
            pass
        
        return hashtags
    
    def process_single_item(self, item: Dict) -> Dict:
        """단일 항목 처리 (병렬 처리용)"""
        try:
            result = {
                'id': item['id'],
                'announcement_id': item['announcement_id'],
                'biz_pbanc_nm': item['biz_pbanc_nm'],
                'success': False,
                'attachments': [],
                'hashtags': '',
                'summary': '',
                'error': None
            }
            
            # 첨부파일 크롤링
            if item.get('detl_pg_url'):
                attachments, page_hashtags = self.extract_attachments_fast(
                    item['announcement_id'], 
                    item['detl_pg_url']
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
                'announcement_id': item.get('announcement_id', 'unknown'),
                'biz_pbanc_nm': item.get('biz_pbanc_nm', ''),
                'success': False,
                'attachments': [],
                'hashtags': '',
                'summary': '',
                'error': str(e)
            }
    
    def extract_attachments_fast(self, announcement_id, detail_url):
        """빠른 첨부파일 추출 (HEAD 요청 생략)"""
        if not detail_url:
            return [], []
        
        try:
            # K-Startup은 HTTP 사용
            if detail_url.startswith('https://'):
                detail_url = detail_url.replace('https://', 'http://')
            
            # 세션 사용으로 연결 재사용
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            attachments = []
            
            # 해시태그 추출
            page_hashtags = self.extract_hashtags_from_page(soup)
            
            # 첨부파일 패턴 (K-Startup 특화)
            patterns = [
                r'download',
                r'file',
                r'attach',
                r'atch',
                r'\.pdf|\.hwp|\.docx|\.xlsx|\.pptx'
            ]
            
            # 패턴 컴파일 (성능 향상)
            compiled_pattern = re.compile('|'.join(patterns), re.IGNORECASE)
            
            # 모든 링크 검사 (최적화)
            all_links = soup.find_all('a', href=True)
            attachment_index = 0
            processed_urls = set()  # 중복 체크용
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                onclick = link.get('onclick', '')
                
                # 빠른 패턴 체크
                combined_text = f"{href} {text} {onclick}".lower()
                if not compiled_pattern.search(combined_text):
                    continue
                
                # onclick에서 URL 추출
                if onclick and not href:
                    url_match = re.search(r"['\"]([^'\"]+)['\"]", onclick)
                    if url_match:
                        href = url_match.group(1)
                
                if href and href != '#' and 'javascript:' not in href.lower():
                    # 전체 URL 생성
                    if not href.startswith('http'):
                        base_url = detail_url.replace('https://', 'http://')
                        full_url = urljoin(base_url, href)
                    else:
                        full_url = href
                    
                    # 중복 체크
                    if full_url in processed_urls:
                        continue
                    processed_urls.add(full_url)
                    
                    attachment_index += 1
                    
                    # 파일명 찾기 (HEAD 요청 생략)
                    display_filename = None
                    original_filename = text or '첨부파일'
                    
                    # 링크 텍스트에서 파일명 찾기
                    if text and text not in ['다운로드', '첨부파일']:
                        display_filename = self.clean_filename(text)
                        if display_filename:
                            original_filename = display_filename
                    
                    # title 속성에서 찾기
                    title = link.get('title', '')
                    if not display_filename and title:
                        display_filename = self.clean_filename(title)
                        if display_filename:
                            original_filename = display_filename
                    
                    # href에서 파일명 추출
                    if not display_filename:
                        parsed = urlparse(full_url)
                        path_parts = parsed.path.split('/')
                        for part in reversed(path_parts):
                            if '.' in part:
                                display_filename = part
                                original_filename = part
                                break
                    
                    # display_filename이 없으면 기본값
                    if not display_filename:
                        display_filename = f"첨부파일_{attachment_index}"
                    
                    # safe_filename 생성
                    safe_filename = self.create_safe_filename(announcement_id, attachment_index, display_filename)
                    
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
            
            # 첨부파일 영역 특별 처리
            file_areas = soup.find_all(['div', 'td', 'ul'], class_=re.compile(r'attach|file|down', re.I))
            for area in file_areas[:5]:  # 최대 5개 영역만 체크 (속도 향상)
                area_links = area.find_all('a', href=True)
                for link in area_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    if href and href != '#' and 'javascript:' not in href.lower():
                        if not href.startswith('http'):
                            base_url = detail_url.replace('https://', 'http://')
                            full_url = urljoin(base_url, href)
                        else:
                            full_url = href
                        
                        if full_url not in processed_urls:
                            processed_urls.add(full_url)
                            attachment_index += 1
                            
                            display_filename = self.clean_filename(text) or f"첨부파일_{attachment_index}"
                            safe_filename = self.create_safe_filename(announcement_id, attachment_index, display_filename)
                            
                            parsed = urlparse(full_url)
                            params = parse_qs(parsed.query)
                            
                            attachment = {
                                'url': full_url,
                                'text': '다운로드',
                                'type': self.get_file_type(display_filename, href),
                                'params': {k: v[0] if len(v) == 1 else v for k, v in params.items()},
                                'safe_filename': safe_filename,
                                'display_filename': display_filename,
                                'original_filename': text or display_filename
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
        combined = text_lower + url_lower
        
        # 순서대로 체크 (자주 나오는 순)
        if '.hwp' in combined or 'hwp' in combined:
            return 'HWP'
        elif '.pdf' in combined or 'pdf' in combined:
            return 'PDF'
        elif '.doc' in combined or '.docx' in combined or 'word' in combined:
            return 'DOC'
        elif '.xls' in combined or '.xlsx' in combined or 'excel' in combined:
            return 'EXCEL'
        elif '.ppt' in combined or '.pptx' in combined:
            return 'PPT'
        elif '.zip' in combined or '.rar' in combined:
            return 'ZIP'
        elif any(ext in combined for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return 'IMAGE'
        else:
            return 'FILE'
    
    def generate_hashtags(self, item, page_hashtags=None):
        """해시태그 생성"""
        tags = []
        
        if page_hashtags:
            tags.extend(page_hashtags[:5])
        
        if item.get('supt_biz_clsfc'):
            field = item['supt_biz_clsfc']
            field_tags = [t.strip() for t in field.split(',') if t.strip()]
            tags.extend(field_tags[:3])
        
        if item.get('aply_trgt_ctnt'):
            target = item['aply_trgt_ctnt']
            if '스타트업' in target:
                tags.append('스타트업')
            if '중소기업' in target:
                tags.append('중소기업')
            if '창업' in target:
                tags.append('창업')
        
        if item.get('pbanc_ntrp_nm'):
            org = item['pbanc_ntrp_nm'].replace('(주)', '').strip()
            if len(org) <= 10:
                tags.append(org)
        
        if item.get('biz_pbanc_nm'):
            title = item['biz_pbanc_nm']
            title_keywords = ['R&D', 'AI', '인공지능', '빅데이터', '바이오', '환경', '그린',
                            '디지털', '혁신', '글로벌', '수출', '기술개발', '사업화', '투자',
                            '액셀러레이팅', '멘토링', 'IR', '데모데이', '엑셀러레이터']
            for keyword in title_keywords:
                if keyword.lower() in title.lower():
                    tags.append(keyword)
        
        unique_tags = list(dict.fromkeys(tags))
        hashtags = ' '.join([f'#{tag.strip()}' for tag in unique_tags[:10]])
        
        return hashtags
    
    def create_summary(self, item, attachments, hashtags):
        """요약 생성"""
        summary_parts = []
        
        if item.get('biz_pbanc_nm'):
            summary_parts.append(f"📋 {item['biz_pbanc_nm']}")
        
        if item.get('pbanc_ntrp_nm'):
            summary_parts.append(f"🏢 주관: {item['pbanc_ntrp_nm']}")
        
        if item.get('pbanc_rcpt_bgng_dt') and item.get('pbanc_rcpt_end_dt'):
            start_date = item['pbanc_rcpt_bgng_dt']
            end_date = item['pbanc_rcpt_end_dt']
            
            # 날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)
            if start_date and len(start_date) == 8:
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            if end_date and len(end_date) == 8:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            
            summary_parts.append(f"📅 기간: {start_date} ~ {end_date}")
            
            # D-Day 계산
            try:
                if end_date:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    days_left = (end_dt - datetime.now()).days
                    
                    if 0 <= days_left <= 3:
                        summary_parts.append(f"🚨 마감임박 D-{days_left}")
                    elif 4 <= days_left <= 7:
                        summary_parts.append(f"⏰ D-{days_left}")
                    elif days_left > 0:
                        summary_parts.append(f"📆 D-{days_left}")
            except:
                pass
        
        if item.get('supt_biz_clsfc'):
            summary_parts.append(f"🎯 분야: {item['supt_biz_clsfc']}")
        
        if item.get('aply_trgt_ctnt'):
            target = item['aply_trgt_ctnt'][:100]
            summary_parts.append(f"👥 대상: {target}...")
        
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
                    logging.error(f"처리 실패 [{result['announcement_id']}]: {result['error']}")
                continue
            
            try:
                update_data = {
                    'attachment_urls': result['attachments'] if result['attachments'] else [],
                    'attachment_count': len(result['attachments']) if result['attachments'] else 0,
                    'hash_tag': result['hashtags'],
                    'bsns_sumry': result['summary'],
                    'attachment_processing_status': {
                        'status': 'completed',
                        'processed_at': datetime.now().isoformat(),
                        'has_safe_filename': True
                    }
                }
                
                self.supabase.table('kstartup_complete').update(
                    update_data
                ).eq('id', result['id']).execute()
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                logging.error(f"DB 업데이트 오류 [{result['announcement_id']}]: {e}")
        
        return success_count, error_count
    
    def get_unprocessed_announcements(self, limit=None):
        """처리 안 된 공고 조회"""
        try:
            query = self.supabase.table('kstartup_complete').select(
                'id', 'announcement_id', 'biz_pbanc_nm', 'detl_pg_url',
                'pbanc_ntrp_nm', 'supt_biz_clsfc', 'aply_trgt_ctnt',
                'pbanc_rcpt_bgng_dt', 'pbanc_rcpt_end_dt', 'attachment_urls'
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
            start_time = time.time()
            
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
                                logging.info(f"  ✓ {result['biz_pbanc_nm'][:30]}... ({att_count}개 첨부)")
                            else:
                                logging.warning(f"  ✗ {result['biz_pbanc_nm'][:30]}...")
                                
                        except Exception as e:
                            item = futures[future]
                            logging.error(f"  ✗ 처리 실패: {item.get('biz_pbanc_nm', 'unknown')[:30]}...")
                    
                    all_results.extend(batch_results)
                    
                    # 배치 DB 업데이트
                    if batch_results:
                        success, error = self.batch_update_database(batch_results)
                        logging.info(f"  배치 결과: 성공 {success}개, 실패 {error}개")
                    
                    # 다음 배치 전 짧은 대기 (API 부하 방지)
                    if i + batch_size < len(unprocessed):
                        time.sleep(1)
            
            # 결과 요약
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            total_success = sum(1 for r in all_results if r['success'])
            total_error = len(all_results) - total_success
            total_attachments = sum(len(r['attachments']) for r in all_results if r['success'])
            
            logging.info("\n" + "="*50)
            logging.info("📊 처리 결과")
            logging.info(f"  전체: {len(all_results)}개")
            logging.info(f"  성공: {total_success}개")
            logging.info(f"  실패: {total_error}개")
            logging.info(f"  첨부파일: {total_attachments}개")
            logging.info(f"  처리 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
            logging.info(f"  평균 속도: {len(all_results)/elapsed_time:.1f}개/초")
            logging.info("="*50)
            
        except Exception as e:
            logging.error(f"처리 중 오류: {e}")
            raise
        finally:
            # 세션 종료
            self.session.close()

if __name__ == "__main__":
    processor = KStartupCompleteProcessorFast()
    processor.run()
