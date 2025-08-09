#!/usr/bin/env python3
"""
K-Startup 데이터 수집 스크립트 (BizInfo 방식으로 개선)
- 상세 페이지에서 실제 첨부파일 정보 추출
- 정확한 파일명과 확장자 수집
- 요약 품질 개선
"""
import os
import sys
import requests
import json
from datetime import datetime, timedelta
from urllib.parse import urljoin, parse_qs, urlparse
from supabase import create_client, Client
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from bs4 import BeautifulSoup
import re

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class KStartupCollectorImproved:
    def __init__(self):
        """초기화"""
        # Supabase 연결
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            logging.error("환경변수가 설정되지 않았습니다.")
            sys.exit(1)
            
        self.supabase: Client = create_client(url, key)
        
        # 세션 재사용
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        # API 설정
        self.api_base_url = "http://www.k-startup.go.kr/web/module/bizpbanc-list.do"
        
        logging.info("=== K-Startup 개선된 수집 시작 (BizInfo 방식) ===")
    
    def fetch_list_data(self, page_num=1, page_size=100):
        """리스트 페이지 조회"""
        try:
            params = {
                'page': page_num,
                'pageSize': page_size,
                'searchType': 'all',
                'searchPbancSttsCd': '01',  # 모집중
                'orderBy': 'recent'
            }
            
            response = self.session.post(
                self.api_base_url,
                json=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'resultList' in data:
                    logging.info(f"  페이지 {page_num}: {len(data['resultList'])}개 조회")
                    return data['resultList']
            
            return []
            
        except Exception as e:
            logging.error(f"페이지 {page_num} 조회 오류: {e}")
            return []
    
    def fetch_detail_page(self, announcement):
        """상세 페이지에서 첨부파일 정보 추출 (BizInfo 방식)"""
        try:
            # 상세 페이지 URL 생성
            detail_url = announcement.get('detlPgUrl', '')
            if not detail_url:
                # URL이 없으면 ID로 생성
                pbancSn = announcement.get('bizPbancSn', '')
                detail_url = f"http://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbancSn}"
            elif not detail_url.startswith('http'):
                detail_url = f"http://www.k-startup.go.kr{detail_url}"
            
            response = self.session.get(detail_url, timeout=10)
            if response.status_code != 200:
                return announcement
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 첨부파일 추출
            attachments = []
            file_idx = 1
            
            # 방법 1: file_bg 클래스에서 title 속성 확인
            file_elements = soup.find_all('span', class_='file_bg')
            for elem in file_elements:
                title = elem.get('title', '')
                if title:
                    # 실제 파일명에서 확장자 추출
                    file_ext = self.extract_extension(title)
                    
                    # 다운로드 링크 찾기
                    parent = elem.find_parent(['li', 'div', 'td'])
                    if parent:
                        link = parent.find('a', href=True)
                        if link:
                            href = link['href']
                            # 다운로드 URL 정리
                            if 'fileDownload' in href:
                                download_url = self.build_download_url(href)
                            else:
                                download_url = urljoin(detail_url, href)
                            
                            attachments.append({
                                'url': download_url,
                                'type': file_ext.upper(),
                                'safe_filename': f"KS_{announcement.get('bizPbancSn', '')}_{file_idx:02d}.{file_ext}",
                                'display_filename': title,
                                'original_filename': title
                            })
                            file_idx += 1
            
            # 방법 2: 다운로드 링크 직접 찾기
            if not attachments:
                download_links = soup.find_all('a', href=re.compile(r'fileDownload|download|atchFile'))
                for link in download_links:
                    href = link['href']
                    link_text = link.get_text(strip=True)
                    
                    # 파일명 추출 시도
                    filename = link_text if link_text and not link_text == '다운로드' else f"attachment_{file_idx}"
                    file_ext = self.extract_extension(filename)
                    
                    # 다운로드 URL 생성
                    download_url = self.build_download_url(href)
                    
                    attachments.append({
                        'url': download_url,
                        'type': file_ext.upper() if file_ext != 'unknown' else 'FILE',
                        'safe_filename': f"KS_{announcement.get('bizPbancSn', '')}_{file_idx:02d}.{file_ext}",
                        'display_filename': filename,
                        'original_filename': filename
                    })
                    file_idx += 1
            
            # 첨부파일 정보 업데이트
            if attachments:
                announcement['attachment_urls'] = attachments
                announcement['attachment_count'] = len(attachments)
            
            # 상세 내용 추출
            content_area = soup.find(['div', 'section'], class_=['content', 'detail', 'view_cont'])
            if content_area:
                announcement['pbanc_ctnt'] = content_area.get_text(strip=True)[:3000]
            
            # 추가 정보 추출
            info_table = soup.find('table', class_=['view_tbl', 'detail_tbl'])
            if info_table:
                details = {}
                rows = info_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True)
                        value = td.get_text(strip=True)
                        details[key] = value
                
                # 주요 정보 매핑
                if '지원대상' in details:
                    announcement['aply_trgt_ctnt'] = details['지원대상']
                if '신청기간' in details:
                    dates = self.extract_dates_from_text(details['신청기간'])
                    if dates:
                        announcement['pbanc_rcpt_bgng_dt'] = dates[0]
                        if len(dates) > 1:
                            announcement['pbanc_rcpt_end_dt'] = dates[1]
            
            return announcement
            
        except Exception as e:
            logging.error(f"상세 페이지 크롤링 오류: {e}")
            return announcement
    
    def extract_extension(self, filename):
        """파일명에서 확장자 추출"""
        if not filename:
            return 'pdf'  # 기본값
        
        # 일반적인 확장자 패턴
        ext_match = re.search(r'\.([a-zA-Z0-9]+)$', filename)
        if ext_match:
            ext = ext_match.group(1).lower()
            # 유효한 확장자 목록
            valid_exts = ['pdf', 'hwp', 'hwpx', 'doc', 'docx', 'xls', 'xlsx', 
                         'ppt', 'pptx', 'zip', 'jpg', 'jpeg', 'png', 'gif']
            if ext in valid_exts:
                return ext
        
        # 텍스트에서 확장자 추측
        filename_lower = filename.lower()
        if '한글' in filename or 'hwp' in filename_lower:
            return 'hwp'
        elif 'pdf' in filename_lower:
            return 'pdf'
        elif '엑셀' in filename or 'excel' in filename_lower:
            return 'xlsx'
        elif '워드' in filename or 'word' in filename_lower:
            return 'docx'
        elif '파워포인트' in filename or 'ppt' in filename_lower:
            return 'pptx'
        
        return 'pdf'  # 기본값
    
    def build_download_url(self, href):
        """다운로드 URL 생성"""
        if href.startswith('http'):
            return href
        elif href.startswith('//'):
            return 'http:' + href
        elif 'fileDownload' in href:
            # K-Startup 특수 다운로드 URL
            return f"http://www.k-startup.go.kr{href}"
        else:
            return f"http://www.k-startup.go.kr/web/module/{href}"
    
    def extract_dates_from_text(self, text):
        """텍스트에서 날짜 추출"""
        dates = []
        
        # 날짜 패턴들
        patterns = [
            r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})',
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                year, month, day = match
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                dates.append(date_str)
        
        return dates
    
    def generate_summary(self, announcement):
        """요약 생성 (BizInfo 스타일)"""
        parts = []
        
        # 제목
        title = announcement.get('biz_pbanc_nm', '')
        if title and title not in ['모집중', 'URL복사', '홈페이지 바로가기']:
            parts.append(f"📋 {title}")
        
        # 주관기관
        org = announcement.get('pbanc_ntrp_nm', '')
        if org:
            parts.append(f"🏢 주관: {org}")
        
        # 지원대상
        target = announcement.get('aply_trgt_ctnt', '')
        if target:
            target_text = target[:80] + "..." if len(target) > 80 else target
            parts.append(f"👥 대상: {target_text}")
        
        # 신청기간
        end_date = announcement.get('pbanc_rcpt_end_dt')
        if end_date:
            parts.append(f"📅 마감: {end_date}")
            
            # D-day 계산
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                days_left = (end_datetime - today).days
                if days_left >= 0:
                    parts.append(f"⏰ D-{days_left}")
            except:
                pass
        
        # 첨부파일
        attach_count = announcement.get('attachment_count', 0)
        if attach_count > 0:
            file_types = []
            for att in announcement.get('attachment_urls', []):
                file_type = att.get('type', 'FILE')
                if file_type not in file_types:
                    file_types.append(file_type)
            parts.append(f"📎 첨부: {', '.join(file_types)} ({attach_count}개)")
        
        return '\n'.join(parts) if parts else f"📋 {title}"
    
    def generate_hashtags(self, announcement):
        """해시태그 생성"""
        tags = []
        
        title = announcement.get('biz_pbanc_nm', '')
        content = announcement.get('pbanc_ctnt', '')
        org = announcement.get('pbanc_ntrp_nm', '')
        
        text = (title + ' ' + content + ' ' + org).lower()
        
        # 키워드 매핑
        keyword_map = {
            '창업': '#창업',
            '스타트업': '#스타트업',
            'R&D': '#연구개발',
            '기술': '#기술개발',
            '투자': '#투자유치',
            '수출': '#수출지원',
            '마케팅': '#마케팅',
            '교육': '#교육',
            '멘토링': '#멘토링',
            '컨설팅': '#컨설팅',
            '사업화': '#사업화',
            'AI': '#인공지능',
            '빅데이터': '#빅데이터'
        }
        
        for keyword, tag in keyword_map.items():
            if keyword.lower() in text:
                if tag not in tags:
                    tags.append(tag)
        
        # 기본 태그
        if not tags:
            tags = ['#정부지원사업', '#K스타트업']
        
        return ' '.join(tags[:5])
    
    def process_announcements(self, announcements):
        """공고 처리 (상세 정보 포함)"""
        processed = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.fetch_detail_page, ann): ann 
                      for ann in announcements}
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=15)
                    
                    # 요약 생성
                    result['bsns_sumry'] = self.generate_summary(result)
                    
                    # 해시태그 생성
                    result['hash_tag'] = self.generate_hashtags(result)
                    
                    processed.append(result)
                    
                except Exception as e:
                    logging.error(f"처리 오류: {e}")
        
        return processed
    
    def save_to_database(self, announcements):
        """DB 저장"""
        if not announcements:
            return 0
        
        # 기존 ID 조회
        existing_result = self.supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = {item['announcement_id'] for item in existing_result.data} if existing_result.data else set()
        
        new_records = []
        for ann in announcements:
            announcement_id = f"KS_{ann.get('bizPbancSn', '')}"
            
            if announcement_id not in existing_ids:
                record = {
                    'announcement_id': announcement_id,
                    'biz_pbanc_nm': ann.get('bizPbancNm', ''),
                    'pbanc_ctnt': ann.get('pbanc_ctnt', ''),
                    'aply_trgt_ctnt': ann.get('aply_trgt_ctnt', ''),
                    'pbanc_rcpt_bgng_dt': ann.get('pbancRcptBgngDt'),
                    'pbanc_rcpt_end_dt': ann.get('pbancRcptEndDt'),
                    'pbanc_ntrp_nm': ann.get('pbancNtrpNm', ''),
                    'detl_pg_url': ann.get('detlPgUrl', ''),
                    'attachment_urls': ann.get('attachment_urls', []),
                    'attachment_count': ann.get('attachment_count', 0),
                    'bsns_sumry': ann.get('bsns_sumry', ''),
                    'hash_tag': ann.get('hash_tag', ''),
                    'created_at': datetime.now().isoformat()
                }
                new_records.append(record)
        
        # 배치 저장
        success_count = 0
        batch_size = 50
        for i in range(0, len(new_records), batch_size):
            batch = new_records[i:i+batch_size]
            try:
                result = self.supabase.table('kstartup_complete').insert(batch).execute()
                if result.data:
                    success_count += len(result.data)
                    logging.info(f"  배치 저장: {len(result.data)}개")
            except Exception as e:
                logging.error(f"저장 오류: {e}")
        
        return success_count
    
    def run(self):
        """메인 실행"""
        try:
            start_time = time.time()
            
            # 1. 리스트 조회 (5페이지, 500개)
            all_announcements = []
            for page in range(1, 6):
                page_data = self.fetch_list_data(page, 100)
                if not page_data:
                    break
                all_announcements.extend(page_data)
            
            logging.info(f"📋 전체 조회: {len(all_announcements)}개")
            
            if not all_announcements:
                logging.info("새로운 공고가 없습니다.")
                return True
            
            # 2. 상세 정보 처리 (첨부파일 포함)
            logging.info("상세 페이지 크롤링 시작...")
            processed = self.process_announcements(all_announcements)
            
            # 3. DB 저장
            saved_count = self.save_to_database(processed)
            
            # 4. 결과 출력
            elapsed = time.time() - start_time
            logging.info("\n" + "="*50)
            logging.info("📊 수집 결과")
            logging.info(f"✅ 신규 저장: {saved_count}개")
            logging.info(f"⏱️ 처리 시간: {elapsed:.1f}초")
            logging.info("="*50)
            
            return True
            
        except Exception as e:
            logging.error(f"실행 오류: {e}")
            return False
        finally:
            self.session.close()

if __name__ == "__main__":
    collector = KStartupCollectorImproved()
    success = collector.run()
    sys.exit(0 if success else 1)
