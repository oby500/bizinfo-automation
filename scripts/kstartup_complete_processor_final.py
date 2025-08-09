#!/usr/bin/env python3
"""
K-Startup 통합 처리 스크립트 (최종 버전)
- 실제 파일명 추출 로직 강화
- 병렬 처리로 속도 개선 (최적화)
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

class KStartupCompleteProcessorFinal:
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
        
        logging.info("=== K-Startup 최종 버전 (속도+파일명 개선) ===")
    
    def extract_real_filename(self, text):
        """실제 파일명 추출 (최적화)"""
        if not text:
            return None
        
        # 불필요한 텍스트 제거
        text = re.sub(r'^\[.*?\]\s*', '', text)  # [첨부파일] 등 제거
        text = text.strip()
        
        # 파일 확장자 패턴 (컴파일된 정규식 - 속도 향상)
        if not hasattr(self, '_file_pattern'):
            self._file_pattern = re.compile(
                r'([^\/\\:*?"<>|\n\r\t]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b',
                re.IGNORECASE
            )
        
        match = self._file_pattern.search(text)
        if match:
            return match.group(1).strip()
        
        # 확장자가 없어도 파일명처럼 보이면 반환
        if 5 < len(text) < 200:
            return text
        
        return None
    
    def get_file_extension_fast(self, filename):
        """파일 확장자 추출 (최적화)"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        # 직접 확장자 매칭 (정규식보다 빠름)
        for ext in ['hwp', 'hwpx', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'jpg', 'jpeg', 'png', 'gif', 'txt', 'rtf']:
            if filename_lower.endswith('.' + ext):
                return ext
        
        # 파일명 힌트로 추론
        if '한글' in filename or 'hwp' in filename_lower:
            return 'hwp'
        elif 'pdf' in filename_lower:
            return 'pdf'
        elif 'excel' in filename_lower or 'xls' in filename_lower:
            return 'xlsx'
        elif 'word' in filename_lower or 'doc' in filename_lower:
            return 'docx'
        elif 'ppt' in filename_lower or '발표' in filename:
            return 'pptx'
        elif 'zip' in filename_lower or '압축' in filename:
            return 'zip'
        
        return 'unknown'
    
    def create_safe_filename(self, announcement_id, index, original_filename):
        """안전한 파일명 생성"""
        ext = self.get_file_extension_fast(original_filename)
        return f"{announcement_id}_{index:02d}.{ext}"
    
    def extract_attachments_fast(self, announcement_id, detail_url):
        """빠른 첨부파일 추출 (파일명 개선 포함)"""
        if not detail_url:
            return [], []
        
        try:
            # K-Startup은 HTTP 사용
            if detail_url.startswith('https://'):
                detail_url = detail_url.replace('https://', 'http://')
            
            response = self.session.get(detail_url, timeout=8)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            attachments = []
            page_hashtags = []
            
            # 해시태그 추출 (간단하게)
            for tag_elem in soup.find_all(class_=re.compile(r'keyword|tag', re.I))[:5]:
                text = tag_elem.get_text(strip=True)
                if text and len(text) < 20:
                    page_hashtags.append(text)
            
            # 첨부파일 추출
            attachment_index = 0
            processed_urls = set()
            
            # content_wrap 내의 다운로드 링크 찾기
            content_area = soup.find('div', class_='content_wrap') or soup
            download_links = content_area.find_all('a', href=re.compile(r'/afile/fileDownload/'))
            
            for link in download_links[:20]:  # 최대 20개만 처리 (속도)
                href = link.get('href', '')
                if not href:
                    continue
                
                full_url = urljoin(detail_url, href)
                if full_url in processed_urls:
                    continue
                processed_urls.add(full_url)
                attachment_index += 1
                
                # 파일명 찾기 (빠른 방법만)
                display_filename = None
                
                # 1. 부모 li 요소에서 찾기
                parent_li = link.find_parent('li')
                if parent_li:
                    # file_bg의 title 속성
                    file_bg = parent_li.find(class_='file_bg')
                    if file_bg and file_bg.get('title'):
                        display_filename = self.extract_real_filename(file_bg.get('title'))
                    
                    # li 텍스트에서
                    if not display_filename:
                        li_text = parent_li.get_text(strip=True).replace('다운로드', '').replace('— 📁', '')
                        display_filename = self.extract_real_filename(li_text)
                
                # 2. 링크 주변 텍스트
                if not display_filename:
                    parent = link.find_parent(['div', 'td'])
                    if parent:
                        parent_text = parent.get_text(strip=True).replace('다운로드', '')
                        display_filename = self.extract_real_filename(parent_text)
                
                # 3. 기본값
                if not display_filename:
                    display_filename = f"첨부파일_{attachment_index}"
                
                # safe_filename 생성
                safe_filename = self.create_safe_filename(announcement_id, attachment_index, display_filename)
                
                # 파일 타입 결정
                file_type = self.get_file_type_fast(display_filename, href)
                
                attachment = {
                    'url': full_url,
                    'text': '다운로드',
                    'type': file_type,
                    'params': {},  # 파라미터 파싱 생략 (속도)
                    'safe_filename': safe_filename,
                    'display_filename': display_filename,
                    'original_filename': display_filename
                }
                
                attachments.append(attachment)
            
            return attachments, page_hashtags
            
        except Exception as e:
            logging.debug(f"첨부파일 크롤링 오류: {e}")
            return [], []
    
    def get_file_type_fast(self, filename, url):
        """파일 타입 추출 (최적화)"""
        text_lower = (filename or '').lower()
        url_lower = url.lower()
        
        # 확장자 기반 빠른 매칭
        if '.hwp' in text_lower or '.hwp' in url_lower:
            return 'HWP'
        elif '.pdf' in text_lower or '.pdf' in url_lower:
            return 'PDF'
        elif '.doc' in text_lower or '.doc' in url_lower:
            return 'DOC'
        elif '.xls' in text_lower or '.xls' in url_lower:
            return 'EXCEL'
        elif '.ppt' in text_lower or '.ppt' in url_lower:
            return 'PPT'
        elif '.zip' in text_lower or '.zip' in url_lower:
            return 'ZIP'
        elif any(ext in text_lower or ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return 'IMAGE'
        
        return 'FILE'
    
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
                hashtags = self.generate_hashtags_fast(item, page_hashtags)
                result['hashtags'] = hashtags
                
                # 요약 생성
                summary = self.create_summary_fast(item, attachments, hashtags)
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
    
    def generate_hashtags_fast(self, item, page_hashtags=None):
        """빠른 해시태그 생성"""
        tags = []
        
        if page_hashtags:
            tags.extend(page_hashtags[:5])
        
        # 주요 필드만 처리
        if item.get('supt_biz_clsfc'):
            tags.extend(item['supt_biz_clsfc'].split(',')[:3])
        
        if item.get('pbanc_ntrp_nm'):
            org = item['pbanc_ntrp_nm'].replace('(주)', '').strip()
            if len(org) <= 10:
                tags.append(org)
        
        # 제목에서 키워드 추출 (간단하게)
        title = item.get('biz_pbanc_nm', '')
        for keyword in ['스타트업', '창업', 'AI', '디지털', '글로벌']:
            if keyword in title:
                tags.append(keyword)
        
        # 중복 제거
        unique_tags = list(dict.fromkeys(tags))[:10]
        return ' '.join([f'#{tag.strip()}' for tag in unique_tags if tag])
    
    def create_summary_fast(self, item, attachments, hashtags):
        """빠른 요약 생성"""
        parts = []
        
        # 제목
        if item.get('biz_pbanc_nm'):
            parts.append(f"📋 {item['biz_pbanc_nm']}")
        
        # 주관기관
        if item.get('pbanc_ntrp_nm'):
            parts.append(f"🏢 주관: {item['pbanc_ntrp_nm']}")
        
        # 기간
        if item.get('pbanc_rcpt_end_dt'):
            end_date = str(item['pbanc_rcpt_end_dt'])
            if len(end_date) == 8:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            parts.append(f"📅 마감: {end_date}")
        
        # 첨부파일
        if attachments:
            file_types = set(a['type'] for a in attachments)
            parts.append(f"📎 첨부: {', '.join(file_types)} ({len(attachments)}개)")
        
        # 해시태그
        if hashtags:
            parts.append(f"🏷️ {hashtags}")
        
        return '\n'.join(parts)
    
    def batch_update_database(self, results: List[Dict]) -> Tuple[int, int]:
        """배치 DB 업데이트"""
        success_count = 0
        error_count = 0
        
        for result in results:
            if not result['success']:
                error_count += 1
                continue
            
            try:
                update_data = {
                    'attachment_urls': result['attachments'] or [],
                    'attachment_count': len(result['attachments']),
                    'hash_tag': result['hashtags'],
                    'bsns_sumry': result['summary'],
                    'attachment_processing_status': {
                        'status': 'completed',
                        'processed_at': datetime.now().isoformat(),
                        'has_safe_filename': True,
                        'version': 'final_fast'
                    }
                }
                
                self.supabase.table('kstartup_complete').update(
                    update_data
                ).eq('id', result['id']).execute()
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                logging.error(f"DB 업데이트 오류: {e}")
        
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
                needs_processing = False
                
                # attachment_urls가 없거나 unknown이 있는 경우
                if not item.get('attachment_urls'):
                    needs_processing = True
                else:
                    urls_str = json.dumps(item['attachment_urls'])
                    if '.unknown' in urls_str or '첨부파일_' in urls_str:
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
        """전체 프로세스 실행 (고속 병렬 처리)"""
        try:
            start_time = time.time()
            
            # Step 1: 처리 대상 조회
            unprocessed = self.get_unprocessed_announcements(limit=200)
            logging.info(f"처리 대상: {len(unprocessed)}개")
            
            if not unprocessed:
                logging.info("처리할 데이터가 없습니다.")
                return
            
            # Step 2: 고속 병렬 처리
            batch_size = 20  # 배치 크기 증가
            all_results = []
            
            with ThreadPoolExecutor(max_workers=5) as executor:  # 워커 증가
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
                            result = future.result(timeout=20)
                            batch_results.append(result)
                            
                            if result['success']:
                                att_count = len(result['attachments'])
                                if result['attachments']:
                                    # 파일명 개선 확인
                                    improved = any(not a['safe_filename'].endswith('.unknown') 
                                                 for a in result['attachments'])
                                    status = "✓✓" if improved else "✓"
                                    logging.info(f"  {status} {result['biz_pbanc_nm'][:30]}... ({att_count}개)")
                            else:
                                logging.warning(f"  ✗ {result['biz_pbanc_nm'][:30]}...")
                                
                        except Exception as e:
                            logging.error(f"  ✗ 처리 실패")
                    
                    all_results.extend(batch_results)
                    
                    # 배치 DB 업데이트
                    if batch_results:
                        success, error = self.batch_update_database(batch_results)
                        logging.info(f"  배치 결과: 성공 {success}개, 실패 {error}개")
                    
                    # 다음 배치 전 짧은 대기
                    if i + batch_size < len(unprocessed):
                        time.sleep(0.5)  # 대기 시간 단축
            
            # 결과 요약
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            total_success = sum(1 for r in all_results if r['success'])
            total_error = len(all_results) - total_success
            total_attachments = sum(len(r['attachments']) for r in all_results if r['success'])
            
            # 파일명 품질 통계
            improved_count = 0
            unknown_count = 0
            for r in all_results:
                if r['success'] and r['attachments']:
                    for att in r['attachments']:
                        if att.get('safe_filename'):
                            if att['safe_filename'].endswith('.unknown'):
                                unknown_count += 1
                            else:
                                improved_count += 1
            
            logging.info("\n" + "="*50)
            logging.info("📊 K-STARTUP 처리 결과")
            logging.info("="*50)
            logging.info(f"✅ 전체: {len(all_results)}개")
            logging.info(f"✅ 성공: {total_success}개")
            logging.info(f"❌ 실패: {total_error}개")
            logging.info(f"📎 첨부파일: {total_attachments}개")
            logging.info(f"   - 정상 파일명: {improved_count}개")
            logging.info(f"   - Unknown: {unknown_count}개")
            logging.info(f"⏱️ 처리 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
            logging.info(f"⚡ 평균 속도: {len(all_results)/elapsed_time:.1f}개/초")
            logging.info("="*50)
            
        except Exception as e:
            logging.error(f"처리 중 오류: {e}")
            raise
        finally:
            # 세션 종료
            self.session.close()

if __name__ == "__main__":
    processor = KStartupCompleteProcessorFinal()
    processor.run()
