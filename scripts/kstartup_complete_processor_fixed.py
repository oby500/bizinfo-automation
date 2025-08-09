#!/usr/bin/env python3
"""
K-Startup 통합 처리 스크립트 (개선된 파일명 추출)
- 실제 파일명 추출 로직 강화
- 병렬 처리로 속도 개선
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

class KStartupCompleteProcessorFixed:
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
        
        # 세션 재사용
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logging.info("=== K-Startup 파일명 개선 처리 시작 ===")
    
    def extract_real_filename(self, text):
        """실제 파일명 추출 (개선된 버전)"""
        if not text:
            return None
        
        # [첨부파일] 제거
        text = re.sub(r'^\[첨부파일\]\s*', '', text)
        text = re.sub(r'^\[.*?\]\s*', '', text)  # 모든 대괄호 제거
        
        # 파일 확장자 패턴
        patterns = [
            r'([^\/\\:*?"<>|\n\r\t]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b',
            r'([^\s]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                filename = match.group(1).strip()
                return filename
        
        # 확장자가 없어도 파일명처럼 보이면 반환
        if len(text) > 5 and len(text) < 200:
            return text.strip()
        
        return None
    
    def get_file_extension(self, filename):
        """파일 확장자 추출"""
        if not filename:
            return 'unknown'
        
        # 확장자 찾기
        if '.' in filename:
            ext = filename.split('.')[-1].lower()
            if ext in ['hwp', 'hwpx', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'jpg', 'jpeg', 'png', 'gif', 'txt', 'rtf']:
                return ext
        
        # URL에서 확장자 힌트 찾기
        filename_lower = filename.lower()
        if '한글' in filename or 'hwp' in filename_lower:
            return 'hwp'
        elif 'pdf' in filename_lower:
            return 'pdf'
        elif 'word' in filename_lower or 'doc' in filename_lower:
            return 'doc'
        elif 'excel' in filename_lower or 'xls' in filename_lower:
            return 'xlsx'
        elif 'ppt' in filename_lower or '발표' in filename:
            return 'pptx'
        elif 'zip' in filename_lower or '압축' in filename:
            return 'zip'
        
        return 'unknown'
    
    def create_safe_filename(self, announcement_id, index, original_filename):
        """안전한 파일명 생성 (개선)"""
        ext = self.get_file_extension(original_filename)
        return f"{announcement_id}_{index:02d}.{ext}"
    
    def extract_attachments_improved(self, announcement_id, detail_url):
        """개선된 첨부파일 추출 (실제 파일명 포함)"""
        if not detail_url:
            return [], []
        
        try:
            # K-Startup은 HTTP 사용
            if detail_url.startswith('https://'):
                detail_url = detail_url.replace('https://', 'http://')
            
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            attachments = []
            page_hashtags = []
            
            # 해시태그 추출
            hashtag_areas = soup.find_all(['div', 'span', 'p'], class_=re.compile(r'keyword|tag|field', re.I))
            for area in hashtag_areas:
                text = area.get_text(strip=True)
                if text and len(text) < 20:
                    page_hashtags.append(text)
            
            # 첨부파일 영역 찾기
            attachment_index = 0
            processed_urls = set()
            
            # 방법 1: content_wrap 내의 파일 링크
            content_wrap = soup.find('div', class_='content_wrap')
            if content_wrap:
                # btn_wrap 내의 다운로드 링크들
                btn_wraps = content_wrap.find_all('div', class_='btn_wrap')
                for btn_wrap in btn_wraps:
                    download_links = btn_wrap.find_all('a', href=re.compile(r'/afile/fileDownload/'))
                    for link in download_links:
                        href = link.get('href', '')
                        if not href:
                            continue
                        
                        full_url = urljoin(detail_url, href)
                        if full_url in processed_urls:
                            continue
                        processed_urls.add(full_url)
                        
                        # 실제 파일명 찾기 (여러 방법 시도)
                        display_filename = None
                        
                        # 1. 같은 ul/li 구조 내에서 파일명 찾기
                        parent_li = link.find_parent('li')
                        if parent_li:
                            # file_bg 클래스를 가진 요소의 title 속성
                            file_bg = parent_li.find(class_='file_bg')
                            if file_bg and file_bg.get('title'):
                                display_filename = self.extract_real_filename(file_bg.get('title'))
                            
                            # 텍스트에서 파일명 찾기
                            if not display_filename:
                                li_text = parent_li.get_text(strip=True)
                                display_filename = self.extract_real_filename(li_text)
                        
                        # 2. 근처 텍스트에서 파일명 찾기
                        if not display_filename:
                            # 이전/다음 형제 요소 확인
                            prev_sibling = link.find_previous_sibling()
                            if prev_sibling:
                                prev_text = prev_sibling.get_text(strip=True) if hasattr(prev_sibling, 'get_text') else str(prev_sibling)
                                display_filename = self.extract_real_filename(prev_text)
                            
                            if not display_filename:
                                next_sibling = link.find_next_sibling()
                                if next_sibling:
                                    next_text = next_sibling.get_text(strip=True) if hasattr(next_sibling, 'get_text') else str(next_sibling)
                                    display_filename = self.extract_real_filename(next_text)
                        
                        # 3. 부모 요소의 텍스트 확인
                        if not display_filename:
                            parent = link.find_parent(['div', 'td', 'li'])
                            if parent:
                                parent_text = parent.get_text(strip=True)
                                # 다운로드 링크 텍스트 제거 후 파일명 추출
                                parent_text = parent_text.replace('다운로드', '').replace('— 📁', '').strip()
                                display_filename = self.extract_real_filename(parent_text)
                        
                        # 4. 링크 자체의 텍스트나 title
                        if not display_filename:
                            link_text = link.get_text(strip=True)
                            if link_text and link_text != '다운로드':
                                display_filename = self.extract_real_filename(link_text)
                            
                            if not display_filename and link.get('title'):
                                display_filename = self.extract_real_filename(link.get('title'))
                        
                        # 5. 실제 다운로드 시도 (최후의 수단)
                        if not display_filename:
                            try:
                                head_response = self.session.head(full_url, allow_redirects=True, timeout=3)
                                content_disposition = head_response.headers.get('Content-Disposition', '')
                                if content_disposition:
                                    # filename*=UTF-8'' 패턴
                                    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
                                    if match:
                                        display_filename = requests.utils.unquote(match.group(1))
                                    else:
                                        # filename= 패턴
                                        match = re.search(r'filename="?([^"\;]+)"?', content_disposition)
                                        if match:
                                            display_filename = match.group(1)
                                            try:
                                                display_filename = display_filename.encode('iso-8859-1').decode('utf-8')
                                            except:
                                                pass
                            except:
                                pass
                        
                        # 파일명이 없으면 기본값
                        if not display_filename:
                            display_filename = f"첨부파일_{attachment_index + 1}"
                        
                        attachment_index += 1
                        
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
                            'original_filename': display_filename
                        }
                        
                        attachments.append(attachment)
                        logging.debug(f"    파일 발견: {display_filename} -> {safe_filename}")
            
            # 방법 2: 모든 파일 다운로드 링크 검색 (백업)
            if not attachments:
                all_download_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
                for link in all_download_links:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    full_url = urljoin(detail_url, href)
                    if full_url in processed_urls:
                        continue
                    processed_urls.add(full_url)
                    
                    attachment_index += 1
                    display_filename = f"첨부파일_{attachment_index}"
                    safe_filename = self.create_safe_filename(announcement_id, attachment_index, display_filename)
                    
                    attachment = {
                        'url': full_url,
                        'text': '다운로드',
                        'type': 'FILE',
                        'params': {},
                        'safe_filename': safe_filename,
                        'display_filename': display_filename,
                        'original_filename': display_filename
                    }
                    
                    attachments.append(attachment)
            
            return attachments, page_hashtags
            
        except Exception as e:
            logging.error(f"첨부파일 크롤링 오류: {e}")
            return [], []
    
    def get_file_type(self, filename, url):
        """파일 타입 추출"""
        text_lower = filename.lower() if filename else ''
        url_lower = url.lower()
        combined = text_lower + url_lower
        
        if '.hwp' in combined or 'hwp' in combined or '한글' in text_lower:
            return 'HWP'
        elif '.pdf' in combined or 'pdf' in combined:
            return 'PDF'
        elif '.doc' in combined or '.docx' in combined or 'word' in combined:
            return 'DOC'
        elif '.xls' in combined or '.xlsx' in combined or 'excel' in combined:
            return 'EXCEL'
        elif '.ppt' in combined or '.pptx' in combined or '발표' in text_lower:
            return 'PPT'
        elif '.zip' in combined or '.rar' in combined or '압축' in text_lower:
            return 'ZIP'
        elif any(ext in combined for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return 'IMAGE'
        else:
            return 'FILE'
    
    def process_single_item(self, item: Dict) -> Dict:
        """단일 항목 처리"""
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
            
            # 첨부파일 크롤링 (개선된 버전)
            if item.get('detl_pg_url'):
                attachments, page_hashtags = self.extract_attachments_improved(
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
            
            if start_date and len(str(start_date)) == 8:
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            if end_date and len(str(end_date)) == 8:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            
            summary_parts.append(f"📅 기간: {start_date} ~ {end_date}")
            
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
                        'has_safe_filename': True,
                        'version': 'v2_improved'
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
        """처리 안 된 공고 조회 (unknown 확장자 포함)"""
        try:
            # 모든 데이터 조회
            query = self.supabase.table('kstartup_complete').select(
                'id', 'announcement_id', 'biz_pbanc_nm', 'detl_pg_url',
                'pbanc_ntrp_nm', 'supt_biz_clsfc', 'aply_trgt_ctnt',
                'pbanc_rcpt_bgng_dt', 'pbanc_rcpt_end_dt', 'attachment_urls'
            ).order('created_at', desc=True).limit(500)
            
            result = query.execute()
            
            unprocessed = []
            for item in result.data:
                needs_processing = False
                
                # 1. attachment_urls가 없는 경우
                if not item.get('attachment_urls'):
                    needs_processing = True
                else:
                    # 2. unknown 확장자가 있는 경우
                    urls_str = json.dumps(item['attachment_urls'])
                    if '.unknown' in urls_str:
                        needs_processing = True
                    # 3. display_filename이 "첨부파일_"로 시작하는 경우
                    elif '첨부파일_' in urls_str:
                        needs_processing = True
                
                if needs_processing:
                    item.pop('attachment_urls', None)
                    unprocessed.append(item)
                
                if limit and len(unprocessed) >= limit:
                    break
            
            return unprocessed[:limit] if limit else unprocessed[:200]
            
        except Exception as e:
            logging.error(f"데이터 조회 오류: {e}")
            return []
    
    def run(self):
        """전체 프로세스 실행"""
        try:
            start_time = time.time()
            
            # Step 1: 처리 대상 조회
            unprocessed = self.get_unprocessed_announcements(limit=200)
            logging.info(f"처리 대상: {len(unprocessed)}개 (unknown 확장자 재처리 포함)")
            
            if not unprocessed:
                logging.info("처리할 데이터가 없습니다.")
                return
            
            # Step 2: 병렬 처리
            batch_size = 10  # 파일명 추출이 복잡하므로 배치 크기 줄임
            all_results = []
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                for i in range(0, len(unprocessed), batch_size):
                    batch = unprocessed[i:i+batch_size]
                    logging.info(f"\n배치 {i//batch_size + 1}/{(len(unprocessed)-1)//batch_size + 1} 처리 중...")
                    
                    futures = {
                        executor.submit(self.process_single_item, item): item 
                        for item in batch
                    }
                    
                    batch_results = []
                    for future in as_completed(futures):
                        try:
                            result = future.result(timeout=30)
                            batch_results.append(result)
                            
                            if result['success']:
                                att_count = len(result['attachments'])
                                if result['attachments']:
                                    # 파일명 개선 확인
                                    improved = any(a['safe_filename'] and not a['safe_filename'].endswith('.unknown') 
                                                 for a in result['attachments'])
                                    if improved:
                                        logging.info(f"  ✓ {result['biz_pbanc_nm'][:30]}... ({att_count}개 첨부 - 파일명 개선됨)")
                                    else:
                                        logging.info(f"  ✓ {result['biz_pbanc_nm'][:30]}... ({att_count}개 첨부)")
                            else:
                                logging.warning(f"  ✗ {result['biz_pbanc_nm'][:30]}...")
                                
                        except Exception as e:
                            item = futures[future]
                            logging.error(f"  ✗ 처리 실패: {item.get('biz_pbanc_nm', 'unknown')[:30]}...")
                    
                    all_results.extend(batch_results)
                    
                    if batch_results:
                        success, error = self.batch_update_database(batch_results)
                        logging.info(f"  배치 결과: 성공 {success}개, 실패 {error}개")
                    
                    if i + batch_size < len(unprocessed):
                        time.sleep(1)
            
            # 결과 요약
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            total_success = sum(1 for r in all_results if r['success'])
            total_error = len(all_results) - total_success
            total_attachments = sum(len(r['attachments']) for r in all_results if r['success'])
            
            # 개선된 파일명 통계
            improved_count = 0
            for r in all_results:
                if r['success'] and r['attachments']:
                    for att in r['attachments']:
                        if att.get('safe_filename') and not att['safe_filename'].endswith('.unknown'):
                            improved_count += 1
            
            logging.info("\n" + "="*50)
            logging.info("📊 처리 결과")
            logging.info(f"  전체: {len(all_results)}개")
            logging.info(f"  성공: {total_success}개")
            logging.info(f"  실패: {total_error}개")
            logging.info(f"  첨부파일: {total_attachments}개")
            logging.info(f"  파일명 개선: {improved_count}개")
            logging.info(f"  처리 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
            logging.info(f"  평균 속도: {len(all_results)/elapsed_time:.1f}개/초")
            logging.info("="*50)
            
        except Exception as e:
            logging.error(f"처리 중 오류: {e}")
            raise
        finally:
            self.session.close()

if __name__ == "__main__":
    processor = KStartupCompleteProcessorFixed()
    processor.run()
