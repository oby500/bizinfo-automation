#!/usr/bin/env python3
"""
K-Startup 데이터 수집 스크립트 (URL 문제 해결)
- JavaScript URL을 실제 URL로 변환
- 상세 페이지에서 첨부파일 정보 추출
"""
import os
import sys
import requests
import json
import re
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class KStartupCollectorFixed:
    def __init__(self):
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            logging.error("환경변수가 설정되지 않았습니다.")
            sys.exit(1)
            
        self.supabase: Client = create_client(url, key)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.api_base_url = "http://www.k-startup.go.kr/web/module/bizpbanc-list.do"
        logging.info("=== K-Startup 수집 시작 (URL 문제 해결) ===")
    
    def fix_detail_url(self, url_or_js):
        """JavaScript URL을 실제 URL로 변환"""
        if not url_or_js:
            return None
            
        # javascript:go_view(174538); 형태 처리
        if 'go_view' in url_or_js:
            match = re.search(r'go_view\((\d+)\)', url_or_js)
            if match:
                pbancSn = match.group(1)
                return f"http://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbancSn}"
        
        # 이미 정상 URL인 경우
        if url_or_js.startswith('http'):
            return url_or_js
        
        # 상대 경로인 경우
        if url_or_js.startswith('/'):
            return f"http://www.k-startup.go.kr{url_or_js}"
            
        return None
    
    def fetch_list_data(self, page_num=1):
        """리스트 페이지 조회"""
        try:
            params = {
                'page': page_num,
                'pageSize': 100,
                'searchType': 'all',
                'searchPbancSttsCd': '01',  # 모집중
                'orderBy': 'recent'
            }
            
            response = self.session.post(self.api_base_url, json=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'resultList' in data:
                    logging.info(f"페이지 {page_num}: {len(data['resultList'])}개 조회")
                    return data['resultList']
            return []
        except Exception as e:
            logging.error(f"페이지 조회 오류: {e}")
            return []
    
    def fetch_detail_page(self, announcement):
        """상세 페이지에서 첨부파일 정보 추출"""
        try:
            # URL 수정
            detail_url = self.fix_detail_url(announcement.get('detlPgUrl'))
            
            if not detail_url:
                # URL이 없으면 ID로 직접 생성
                pbancSn = announcement.get('bizPbancSn', '')
                if pbancSn:
                    detail_url = f"http://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbancSn}"
                else:
                    return announcement
            
            logging.debug(f"상세 페이지 크롤링: {detail_url}")
            
            response = self.session.get(detail_url, timeout=10)
            if response.status_code != 200:
                return announcement
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 첨부파일 추출
            attachments = []
            file_idx = 1
            
            # 방법 1: 첨부파일 영역 찾기
            file_area = soup.find('div', class_=['file_area', 'attach_file', 'file_list'])
            if file_area:
                links = file_area.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    link_text = link.get_text(strip=True)
                    
                    # 파일명 추출
                    filename = link_text if link_text else f"attachment_{file_idx}"
                    
                    # 확장자 추측
                    file_ext = 'pdf'  # 기본값
                    if '.hwp' in filename.lower() or '한글' in filename:
                        file_ext = 'hwp'
                    elif '.doc' in filename.lower() or '워드' in filename:
                        file_ext = 'docx'
                    elif '.xls' in filename.lower() or '엑셀' in filename:
                        file_ext = 'xlsx'
                    elif '.pdf' in filename.lower():
                        file_ext = 'pdf'
                    elif '.zip' in filename.lower():
                        file_ext = 'zip'
                    
                    # 다운로드 URL 생성
                    if 'fileDownload' in href or 'download' in href:
                        if not href.startswith('http'):
                            download_url = f"http://www.k-startup.go.kr{href}"
                        else:
                            download_url = href
                    else:
                        download_url = urljoin(detail_url, href)
                    
                    attachments.append({
                        'url': download_url,
                        'type': file_ext.upper(),
                        'safe_filename': f"KS_{announcement.get('bizPbancSn')}_{file_idx:02d}.{file_ext}",
                        'display_filename': filename,
                        'original_filename': filename
                    })
                    file_idx += 1
            
            # 방법 2: 모든 다운로드 링크 찾기
            if not attachments:
                download_links = soup.find_all('a', href=re.compile(r'(fileDownload|download|atchFile|\.pdf|\.hwp|\.doc|\.xls|\.zip)', re.I))
                for link in download_links[:5]:  # 최대 5개
                    href = link['href']
                    link_text = link.get_text(strip=True)
                    
                    # 확장자 추출
                    ext_match = re.search(r'\.([a-zA-Z]{3,4})(?:\?|$|#)', href)
                    if ext_match:
                        file_ext = ext_match.group(1).lower()
                    else:
                        file_ext = 'pdf'
                    
                    filename = link_text if link_text and link_text != '다운로드' else f"attachment_{file_idx}.{file_ext}"
                    
                    if not href.startswith('http'):
                        download_url = f"http://www.k-startup.go.kr{href}"
                    else:
                        download_url = href
                    
                    attachments.append({
                        'url': download_url,
                        'type': file_ext.upper(),
                        'safe_filename': f"KS_{announcement.get('bizPbancSn')}_{file_idx:02d}.{file_ext}",
                        'display_filename': filename,
                        'original_filename': filename
                    })
                    file_idx += 1
            
            if attachments:
                announcement['attachment_urls'] = attachments
                announcement['attachment_count'] = len(attachments)
                logging.info(f"  - 첨부파일 {len(attachments)}개 발견")
            
            # 추가 정보 추출
            info_table = soup.find('table', class_=['view_tbl', 'detail_table', 'tbl_view'])
            if info_table:
                for row in info_table.find_all('tr'):
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True)
                        value = td.get_text(strip=True)
                        
                        if '지원대상' in key:
                            announcement['aply_trgt_ctnt'] = value
                        elif '신청기간' in key or '접수기간' in key:
                            # 날짜 추출
                            dates = re.findall(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', value)
                            if dates:
                                announcement['pbanc_rcpt_bgng_dt'] = dates[0].replace('.', '-').replace('/', '-')
                                if len(dates) > 1:
                                    announcement['pbanc_rcpt_end_dt'] = dates[1].replace('.', '-').replace('/', '-')
            
            return announcement
            
        except Exception as e:
            logging.error(f"상세 페이지 크롤링 오류: {e}")
            return announcement
    
    def generate_summary(self, announcement):
        """요약 생성"""
        parts = []
        
        title = announcement.get('bizPbancNm', '')
        # 쓰레기 제목 필터링
        if title and title not in ['모집중', 'URL복사', '홈페이지 바로가기', '모집마감', '고객센터', '법률지원']:
            parts.append(f"📋 {title}")
        
        org = announcement.get('pbancNtrpNm', '')
        if org:
            parts.append(f"🏢 주관: {org}")
        
        target = announcement.get('aply_trgt_ctnt', '')
        if target:
            parts.append(f"👥 대상: {target[:80]}")
        
        end_date = announcement.get('pbancRcptEndDt')
        if end_date:
            parts.append(f"📅 마감: {end_date}")
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                days_left = (end_dt - datetime.now()).days
                if days_left >= 0:
                    parts.append(f"⏰ D-{days_left}")
            except:
                pass
        
        attach_count = announcement.get('attachment_count', 0)
        if attach_count > 0:
            parts.append(f"📎 첨부: {attach_count}개")
        
        return '\n'.join(parts) if parts else f"📋 {title}"
    
    def generate_hashtags(self, announcement):
        """해시태그 생성"""
        title = announcement.get('bizPbancNm', '')
        content = announcement.get('pbancCtnt', '')
        
        text = (title + ' ' + content).lower()
        
        tags = []
        if '창업' in text:
            tags.append('#창업')
        if '스타트업' in text:
            tags.append('#스타트업')
        if 'r&d' in text.lower() or '연구' in text:
            tags.append('#연구개발')
        if '투자' in text:
            tags.append('#투자')
        if '교육' in text:
            tags.append('#교육')
        if '멘토' in text:
            tags.append('#멘토링')
        
        if not tags:
            tags = ['#정부지원사업']
        
        return ' '.join(tags[:5])
    
    def process_announcements(self, announcements):
        """공고 처리"""
        processed = []
        
        # 쓰레기 데이터 필터링
        valid_announcements = []
        for ann in announcements:
            title = ann.get('bizPbancNm', '')
            if title not in ['모집중', 'URL복사', '홈페이지 바로가기', '모집마감', '고객센터', '법률지원', '']:
                valid_announcements.append(ann)
        
        logging.info(f"유효한 공고: {len(valid_announcements)}개 (전체: {len(announcements)}개)")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.fetch_detail_page, ann): ann 
                      for ann in valid_announcements}
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=15)
                    result['bsns_sumry'] = self.generate_summary(result)
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
        existing = self.supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = {item['announcement_id'] for item in existing.data} if existing.data else set()
        
        new_records = []
        for ann in announcements:
            announcement_id = f"KS_{ann.get('bizPbancSn')}"
            
            if announcement_id not in existing_ids:
                # detl_pg_url 수정
                detail_url = self.fix_detail_url(ann.get('detlPgUrl'))
                
                record = {
                    'announcement_id': announcement_id,
                    'biz_pbanc_nm': ann.get('bizPbancNm', ''),
                    'pbanc_ctnt': ann.get('pbancCtnt', ''),
                    'aply_trgt_ctnt': ann.get('aply_trgt_ctnt', ''),
                    'pbanc_rcpt_bgng_dt': ann.get('pbancRcptBgngDt'),
                    'pbanc_rcpt_end_dt': ann.get('pbancRcptEndDt'),
                    'pbanc_ntrp_nm': ann.get('pbancNtrpNm', ''),
                    'detl_pg_url': detail_url or '',
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
                    logging.info(f"저장 완료: {len(result.data)}개")
            except Exception as e:
                logging.error(f"저장 오류: {e}")
        
        return success_count
    
    def run(self):
        """메인 실행"""
        try:
            start_time = time.time()
            
            # 1. 리스트 조회
            all_announcements = []
            for page in range(1, 4):  # 3페이지만
                page_data = self.fetch_list_data(page)
                if not page_data:
                    break
                all_announcements.extend(page_data)
            
            logging.info(f"전체 조회: {len(all_announcements)}개")
            
            if not all_announcements:
                logging.info("새로운 공고가 없습니다.")
                return True
            
            # 2. 상세 정보 처리
            logging.info("상세 페이지 크롤링 시작...")
            processed = self.process_announcements(all_announcements)
            
            # 3. DB 저장
            saved_count = self.save_to_database(processed)
            
            # 4. 결과
            elapsed = time.time() - start_time
            logging.info("\n" + "="*50)
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
    collector = KStartupCollectorFixed()
    success = collector.run()
    sys.exit(0 if success else 1)
