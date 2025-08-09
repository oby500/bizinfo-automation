#!/usr/bin/env python3
"""
K-Startup 데이터 품질 개선 스크립트
- 상세 페이지 크롤링으로 첨부파일 수집
- AI 기반 요약 재생성
- 해시태그 자동 생성
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
from supabase import create_client
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)

class KStartupEnhancer:
    def __init__(self):
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
        
        if not url or not key:
            logging.error("환경변수 설정 필요")
            sys.exit(1)
            
        self.supabase = create_client(url, key)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_poor_quality_data(self, limit=100):
        """품질이 낮은 데이터 조회"""
        logging.info("품질 개선 필요 데이터 조회 중...")
        
        # 1. 첨부파일 없는 데이터
        no_attach = self.supabase.table('kstartup_complete')\
            .select('id,announcement_id,biz_pbanc_nm,detl_pg_url')\
            .or_('attachment_urls.is.null,attachment_urls.eq.[]')\
            .limit(limit)\
            .execute()
        
        # 2. 요약이 부실한 데이터
        poor_summary = self.supabase.table('kstartup_complete')\
            .select('id,announcement_id,biz_pbanc_nm,detl_pg_url,bsns_sumry')\
            .or_('bsns_sumry.is.null,bsns_sumry.eq.')\
            .limit(limit)\
            .execute()
        
        # 중복 제거하여 병합
        all_ids = set()
        items_to_process = []
        
        for item in (no_attach.data or []) + (poor_summary.data or []):
            if item['id'] not in all_ids:
                all_ids.add(item['id'])
                items_to_process.append(item)
        
        logging.info(f"개선 대상: {len(items_to_process)}개")
        return items_to_process[:limit]
    
    def crawl_detail_page(self, item):
        """상세 페이지 크롤링"""
        try:
            url = item.get('detl_pg_url')
            if not url:
                return None
            
            # URL 정리
            if not url.startswith('http'):
                url = f"https://www.k-startup.go.kr{url}"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = {
                'id': item['id'],
                'attachments': [],
                'content': '',
                'details': {}
            }
            
            # 1. 첨부파일 추출
            file_areas = soup.find_all(['div', 'ul', 'dl'], class_=['file', 'attach', 'download'])
            for area in file_areas:
                links = area.find_all('a')
                for idx, link in enumerate(links, 1):
                    href = link.get('href', '')
                    filename = link.get_text(strip=True) or f"attachment_{idx}"
                    
                    if href and not href.startswith('#'):
                        # K-Startup 특수 다운로드 URL 처리
                        if 'fileDown' in href or 'download' in href:
                            file_id = self.extract_file_id(href)
                            if file_id:
                                result['attachments'].append({
                                    'url': f"https://www.k-startup.go.kr/web/module/download.do?fileName={file_id}",
                                    'filename': filename,
                                    'safe_filename': f"KS_{item['announcement_id']}_{idx:02d}.{self.get_extension(filename)}",
                                    'display_filename': filename
                                })
            
            # 2. 상세 내용 추출
            content_area = soup.find(['div', 'section'], class_=['content', 'detail', 'view'])
            if content_area:
                # 테이블 데이터 추출
                tables = content_area.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        th = row.find('th')
                        td = row.find('td')
                        if th and td:
                            key = th.get_text(strip=True)
                            value = td.get_text(strip=True)
                            if key and value:
                                result['details'][key] = value
                
                # 본문 텍스트
                result['content'] = content_area.get_text(strip=True)[:2000]
            
            return result
            
        except Exception as e:
            logging.error(f"크롤링 오류 (ID: {item['id']}): {e}")
            return None
    
    def extract_file_id(self, url):
        """파일 ID 추출"""
        import re
        
        patterns = [
            r'fileName=([^&]+)',
            r'fileId=([^&]+)',
            r'atchFileId=([^&]+)',
            r'file/([^/]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_extension(self, filename):
        """확장자 추출"""
        if '.' in filename:
            ext = filename.split('.')[-1].lower()
            if ext in ['pdf', 'hwp', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip']:
                return ext
        return 'unknown'
    
    def generate_enhanced_summary(self, item, crawled_data):
        """개선된 요약 생성"""
        title = item.get('biz_pbanc_nm', '')
        content = crawled_data.get('content', '') if crawled_data else ''
        details = crawled_data.get('details', {}) if crawled_data else {}
        
        # 핵심 정보 추출
        summary_parts = []
        
        # 제목에서 핵심 추출
        if title and title not in ['모집중', 'URL복사', '홈페이지 바로가기']:
            summary_parts.append(f"📋 {title}")
        
        # 지원 대상
        if '지원대상' in details:
            summary_parts.append(f"👥 대상: {details['지원대상'][:100]}")
        
        # 지원 내용
        if '지원내용' in details:
            summary_parts.append(f"💰 지원: {details['지원내용'][:100]}")
        elif '사업내용' in details:
            summary_parts.append(f"💰 내용: {details['사업내용'][:100]}")
        
        # 신청 기간
        if '신청기간' in details:
            summary_parts.append(f"📅 기간: {details['신청기간']}")
        elif '접수기간' in details:
            summary_parts.append(f"📅 접수: {details['접수기간']}")
        
        # 내용이 너무 짧으면 본문에서 추출
        if len(summary_parts) < 2 and content:
            summary_parts.append(content[:200] + "...")
        
        return '\n'.join(summary_parts) if summary_parts else f"📋 {title}"
    
    def generate_hashtags(self, item, crawled_data):
        """해시태그 자동 생성"""
        title = item.get('biz_pbanc_nm', '')
        content = (crawled_data.get('content', '') if crawled_data else '')[:500]
        
        hashtags = []
        
        # 키워드 기반 해시태그
        keywords = {
            '창업': '#창업지원',
            '스타트업': '#스타트업',
            'R&D': '#연구개발',
            '기술': '#기술개발',
            '투자': '#투자유치',
            '수출': '#수출지원',
            '마케팅': '#마케팅지원',
            '교육': '#교육프로그램',
            '멘토링': '#멘토링',
            '사업화': '#사업화지원',
            '시제품': '#시제품제작',
            '특허': '#특허지원',
            '인증': '#인증지원',
            '컨설팅': '#컨설팅',
            '자금': '#자금지원',
            '보증': '#보증지원',
            '대출': '#정책자금'
        }
        
        text = (title + ' ' + content).lower()
        
        for keyword, tag in keywords.items():
            if keyword.lower() in text:
                hashtags.append(tag)
        
        # 기본 태그
        if not hashtags:
            hashtags = ['#정부지원', '#K스타트업']
        
        # 최대 5개로 제한
        return hashtags[:5]
    
    def process_batch(self, items):
        """배치 처리"""
        logging.info(f"배치 처리 시작: {len(items)}개")
        
        processed = 0
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.crawl_detail_page, item): item 
                      for item in items}
            
            for future in as_completed(futures):
                item = futures[future]
                try:
                    crawled = future.result(timeout=15)
                    
                    # 업데이트할 데이터 준비
                    update_data = {}
                    
                    # 첨부파일 업데이트
                    if crawled and crawled.get('attachments'):
                        update_data['attachment_urls'] = crawled['attachments']
                        update_data['attachment_count'] = len(crawled['attachments'])
                    
                    # 요약 개선
                    enhanced_summary = self.generate_enhanced_summary(item, crawled)
                    if enhanced_summary and len(enhanced_summary) > 20:
                        update_data['bsns_sumry'] = enhanced_summary
                    
                    # 해시태그 생성
                    hashtags = self.generate_hashtags(item, crawled)
                    if hashtags:
                        update_data['hash_tag'] = hashtags
                    
                    # 상세 내용 업데이트
                    if crawled and crawled.get('content'):
                        update_data['pbanc_ctnt'] = crawled['content']
                    
                    # DB 업데이트
                    if update_data:
                        update_data['updated_at'] = datetime.now().isoformat()
                        update_data['quality_enhanced'] = True
                        
                        self.supabase.table('kstartup_complete')\
                            .update(update_data)\
                            .eq('id', item['id'])\
                            .execute()
                        
                        processed += 1
                        logging.info(f"✅ ID {item['id']} 개선 완료")
                    
                except Exception as e:
                    logging.error(f"처리 오류 (ID: {item['id']}): {e}")
        
        return processed
    
    def run(self, limit=100):
        """메인 실행"""
        start_time = time.time()
        
        logging.info("="*60)
        logging.info("   K-Startup 데이터 품질 개선 시작")
        logging.info("="*60)
        
        # 1. 개선 필요 데이터 조회
        items = self.get_poor_quality_data(limit)
        
        if not items:
            logging.info("개선할 데이터가 없습니다.")
            return
        
        # 2. 배치 처리
        batch_size = 20
        total_processed = 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            processed = self.process_batch(batch)
            total_processed += processed
            
            logging.info(f"진행: {total_processed}/{len(items)}")
        
        # 3. 결과 통계
        elapsed = time.time() - start_time
        
        logging.info("\n" + "="*60)
        logging.info("   처리 완료")
        logging.info("="*60)
        logging.info(f"✅ 개선 완료: {total_processed}개")
        logging.info(f"⏱️ 소요 시간: {elapsed:.1f}초")
        logging.info(f"📊 평균 속도: {total_processed/elapsed:.1f}개/초")
        
        # 4. 개선 후 품질 확인
        self.check_quality_after()
    
    def check_quality_after(self):
        """개선 후 품질 확인"""
        stats = self.supabase.table('kstartup_complete')\
            .select('id', count='exact')\
            .eq('quality_enhanced', True)\
            .execute()
        
        if stats.count:
            logging.info(f"\n✨ 품질 개선된 데이터: {stats.count}개")

if __name__ == "__main__":
    enhancer = KStartupEnhancer()
    enhancer.run(limit=50)  # 먼저 50개만 테스트
