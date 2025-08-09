#!/usr/bin/env python3
"""
K-Startup 데이터 수집 스크립트 (고속 버전)
- 병렬 처리로 속도 개선
- 세션 재사용으로 연결 최적화
"""
import os
import sys
import requests
import json
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class KStartupCollectorFast:
    def __init__(self):
        """초기화"""
        # Supabase 연결
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            logging.error("환경변수가 설정되지 않았습니다.")
            sys.exit(1)
            
        self.supabase: Client = create_client(url, key)
        
        # 세션 재사용 (연결 풀링)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        })
        
        # API 설정
        self.api_base_url = "http://www.k-startup.go.kr/web/module/bizpbanc-list.do"
        
        logging.info("=== K-Startup 고속 수집 시작 ===")
    
    def fetch_page(self, page_num):
        """단일 페이지 조회 (병렬 처리용)"""
        try:
            params = {
                'page': page_num,
                'pageSize': 100,  # 한 번에 100개씩
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
    
    def fetch_all_announcements_fast(self):
        """모든 공고 병렬 조회"""
        try:
            start_time = time.time()
            
            # 먼저 첫 페이지로 전체 개수 확인
            first_page = self.fetch_page(1)
            if not first_page:
                logging.warning("API 응답 없음, 스크래핑 모드로 전환")
                return self.scrape_announcements_fast()
            
            all_announcements = first_page
            
            # 추가 페이지가 있을 경우 병렬 처리
            # K-Startup은 보통 500개 이하이므로 5페이지면 충분
            pages_to_fetch = [2, 3, 4, 5]
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(self.fetch_page, page): page 
                          for page in pages_to_fetch}
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=10)
                        if result:
                            all_announcements.extend(result)
                    except Exception as e:
                        logging.error(f"페이지 조회 오류: {e}")
            
            elapsed = time.time() - start_time
            logging.info(f"API 조회 완료: {len(all_announcements)}개 ({elapsed:.1f}초)")
            
            return all_announcements
            
        except Exception as e:
            logging.error(f"전체 조회 오류: {e}")
            return self.scrape_announcements_fast()
    
    def scrape_announcements_fast(self):
        """빠른 웹 스크래핑 (대체 방법)"""
        try:
            from bs4 import BeautifulSoup
            
            logging.info("고속 스크래핑 모드...")
            
            # 여러 페이지 병렬 스크래핑
            base_url = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
            announcements = []
            
            def scrape_page(page_num):
                try:
                    url = f"{base_url}?page={page_num}"
                    response = self.session.get(url, timeout=8)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        page_items = []
                        
                        # 공고 목록 추출 (간소화)
                        items = soup.find_all(['div', 'li', 'tr'], class_=re.compile(r'item|list|row'))[:20]
                        
                        for idx, item in enumerate(items, 1):
                            title_elem = item.find('a')
                            if title_elem:
                                page_items.append({
                                    'bizPbancSn': f"{datetime.now().strftime('%Y%m%d')}_{page_num}_{idx}",
                                    'bizPbancNm': title_elem.get_text(strip=True),
                                    'pbancNtrpNm': '',
                                    'pbancRcptBgngDt': None,
                                    'pbancRcptEndDt': None,
                                    'detlPgUrl': urljoin(base_url, title_elem.get('href', ''))
                                })
                        
                        return page_items
                    return []
                except:
                    return []
            
            # 병렬 스크래핑 (3페이지)
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(scrape_page, i) for i in range(1, 4)]
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=10)
                        announcements.extend(result)
                    except:
                        pass
            
            logging.info(f"스크래핑 완료: {len(announcements)}개")
            return announcements
            
        except Exception as e:
            logging.error(f"스크래핑 오류: {e}")
            return []
    
    def save_to_database_batch(self, announcements):
        """배치 DB 저장 (고속)"""
        if not announcements:
            logging.info("저장할 데이터가 없습니다.")
            return 0
        
        start_time = time.time()
        
        # 1. 기존 ID 조회 (한 번에)
        existing_result = self.supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = {item['announcement_id'] for item in existing_result.data} if existing_result.data else set()
        
        # 2. 신규 데이터 필터링 (메모리에서)
        new_records = []
        duplicate_count = 0
        
        for ann in announcements:
            announcement_id = f"KS_{ann.get('bizPbancSn', '')}"
            
            if announcement_id in existing_ids:
                duplicate_count += 1
                continue
            
            # 레코드 생성 (간소화)
            record = {
                'announcement_id': announcement_id,
                'biz_pbanc_nm': ann.get('bizPbancNm', ''),
                'pbanc_ctnt': ann.get('pbancCtnt', ''),
                'supt_biz_clsfc': ann.get('suptBizClsfc', ''),
                'aply_trgt_ctnt': ann.get('aplyTrgtCtnt', ''),
                'supt_regin': ann.get('suptRegin', ''),
                'pbanc_rcpt_bgng_dt': self.parse_date_fast(ann.get('pbancRcptBgngDt')),
                'pbanc_rcpt_end_dt': self.parse_date_fast(ann.get('pbancRcptEndDt')),
                'pbanc_ntrp_nm': ann.get('pbancNtrpNm', ''),
                'biz_gdnc_url': ann.get('bizGdncUrl', ''),
                'biz_aply_url': ann.get('bizAplyUrl', ''),
                'detl_pg_url': ann.get('detlPgUrl', ''),
                'attachment_urls': [],
                'attachment_count': 0,
                'attachment_processing_status': 'pending',  # 초기값
                'created_at': datetime.now().isoformat()
            }
            
            new_records.append(record)
        
        # 3. 배치 저장 (한 번에)
        success_count = 0
        
        if new_records:
            logging.info(f"배치 저장: {len(new_records)}개")
            
            # 100개씩 나눠서 저장 (Supabase 제한)
            batch_size = 100
            for i in range(0, len(new_records), batch_size):
                batch = new_records[i:i+batch_size]
                try:
                    result = self.supabase.table('kstartup_complete').insert(batch).execute()
                    if result.data:
                        success_count += len(result.data)
                        logging.info(f"  배치 {i//batch_size + 1} 저장: {len(result.data)}개")
                except Exception as e:
                    logging.error(f"배치 저장 오류: {e}")
        
        elapsed = time.time() - start_time
        
        # 결과 요약
        logging.info("\n" + "="*50)
        logging.info("📊 수집 결과")
        logging.info(f"✅ 신규 저장: {success_count}개")
        logging.info(f"⏭️ 중복 제외: {duplicate_count}개")
        logging.info(f"⏱️ 처리 시간: {elapsed:.1f}초")
        logging.info(f"⚡ 평균 속도: {len(announcements)/elapsed:.1f}개/초")
        logging.info("="*50)
        
        return success_count
    
    def parse_date_fast(self, date_str):
        """빠른 날짜 파싱"""
        if not date_str:
            return None
        
        try:
            date_str = date_str.strip()[:10]  # 날짜 부분만
            
            if '-' in date_str:
                return date_str
            elif '.' in date_str:
                return date_str.replace('.', '-')
            elif len(date_str) == 8 and date_str.isdigit():
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            return None
        except:
            return None
    
    def run(self):
        """메인 실행"""
        try:
            start_time = time.time()
            
            # 1. 병렬 조회
            announcements = self.fetch_all_announcements_fast()
            
            if not announcements:
                logging.info("수집할 새로운 공고가 없습니다.")
                return True
            
            # 2. 배치 저장
            saved_count = self.save_to_database_batch(announcements)
            
            # 3. 전체 시간
            total_elapsed = time.time() - start_time
            logging.info(f"\n🚀 전체 처리 시간: {total_elapsed:.1f}초")
            
            return True
            
        except Exception as e:
            logging.error(f"실행 중 오류: {e}")
            return False
        finally:
            # 세션 종료
            self.session.close()

if __name__ == "__main__":
    import re  # BeautifulSoup에서 사용
    
    collector = KStartupCollectorFast()
    success = collector.run()
    sys.exit(0 if success else 1)
