#!/usr/bin/env python3
"""
K-Startup 데이터 수집 스크립트 (개선된 고속 버전)
- 병렬 처리로 속도 개선
- 세션 재사용으로 연결 최적화
- 새로운 공고 감지 로직 추가
- 더 많은 페이지 수집
"""
import os
import sys
import requests
import json
from datetime import datetime, timedelta
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
        
        # 최근 체크 기준 (7일)
        self.recent_days = 7
        
        logging.info("=== K-Startup 고속 수집 시작 (개선 버전) ===")
    
    def get_last_collected_info(self):
        """마지막 수집 정보 조회"""
        try:
            # 가장 최근 데이터 조회
            result = self.supabase.table('kstartup_complete')\
                .select('announcement_id,created_at')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                last_record = result.data[0]
                last_time = datetime.fromisoformat(last_record['created_at'].replace('Z', '+00:00'))
                logging.info(f"마지막 수집: {last_time.strftime('%Y-%m-%d %H:%M')} - {last_record['announcement_id']}")
                return last_time
            else:
                logging.info("첫 수집입니다.")
                return None
                
        except Exception as e:
            logging.error(f"마지막 수집 정보 조회 오류: {e}")
            return None
    
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
        """모든 공고 병렬 조회 (개선)"""
        try:
            start_time = time.time()
            
            # 먼저 첫 페이지로 전체 개수 확인
            first_page = self.fetch_page(1)
            if not first_page:
                logging.warning("API 응답 없음, 스크래핑 모드로 전환")
                return self.scrape_announcements_fast()
            
            all_announcements = first_page
            
            # 추가 페이지가 있을 경우 병렬 처리
            # 10페이지까지 확장 (1000개)
            pages_to_fetch = list(range(2, 11))  # 2~10 페이지
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self.fetch_page, page): page 
                          for page in pages_to_fetch}
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=10)
                        if result:
                            all_announcements.extend(result)
                        else:
                            # 빈 페이지면 더 이상 진행 안함
                            break
                    except Exception as e:
                        logging.error(f"페이지 조회 오류: {e}")
            
            elapsed = time.time() - start_time
            logging.info(f"API 조회 완료: {len(all_announcements)}개 ({elapsed:.1f}초)")
            
            return all_announcements
            
        except Exception as e:
            logging.error(f"전체 조회 오류: {e}")
            return self.scrape_announcements_fast()
    
    def scrape_announcements_fast(self):
        """빠른 웹 스크래핑 (개선된 버전)"""
        try:
            from bs4 import BeautifulSoup
            import re
            
            logging.info("고속 스크래핑 모드 (확장)...")
            
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
                        
                        # 공고 목록 추출 (더 많이)
                        items = soup.find_all(['div', 'li', 'tr'], class_=re.compile(r'item|list|row'))[:50]
                        
                        for idx, item in enumerate(items, 1):
                            title_elem = item.find('a')
                            if title_elem:
                                # 날짜 추출 시도
                                date_elem = item.find(['span', 'td'], class_=re.compile(r'date|time'))
                                date_str = date_elem.get_text(strip=True) if date_elem else None
                                
                                page_items.append({
                                    'bizPbancSn': f"{datetime.now().strftime('%Y%m%d')}_{page_num}_{idx}",
                                    'bizPbancNm': title_elem.get_text(strip=True),
                                    'pbancNtrpNm': '',
                                    'pbancRcptBgngDt': self.parse_date_from_text(date_str),
                                    'pbancRcptEndDt': None,
                                    'detlPgUrl': urljoin(base_url, title_elem.get('href', ''))
                                })
                        
                        return page_items
                    return []
                except Exception as e:
                    logging.error(f"스크래핑 페이지 {page_num} 오류: {e}")
                    return []
            
            # 병렬 스크래핑 (10페이지로 확장)
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(scrape_page, i) for i in range(1, 11)]
                
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
    
    def check_new_announcements(self, announcements):
        """새로운 공고 감지"""
        if not announcements:
            return [], []
        
        # 1. 기존 ID 조회 (한 번에)
        existing_result = self.supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = {item['announcement_id'] for item in existing_result.data} if existing_result.data else set()
        
        new_announcements = []
        updated_announcements = []
        
        # 2. 새로운 공고와 업데이트된 공고 분류
        for ann in announcements:
            announcement_id = f"KS_{ann.get('bizPbancSn', '')}"
            
            if announcement_id not in existing_ids:
                new_announcements.append(ann)
            else:
                # 마감일 변경 등 체크 필요시
                updated_announcements.append(ann)
        
        logging.info(f"📊 감지 결과: 신규 {len(new_announcements)}개, 업데이트 {len(updated_announcements)}개")
        
        return new_announcements, updated_announcements
    
    def save_to_database_batch(self, announcements):
        """배치 DB 저장 (개선)"""
        if not announcements:
            logging.info("저장할 데이터가 없습니다.")
            return 0
        
        start_time = time.time()
        
        # 새로운 공고 감지
        new_announcements, updated_announcements = self.check_new_announcements(announcements)
        
        if not new_announcements and not updated_announcements:
            logging.info("✅ 모든 공고가 최신 상태입니다.")
            return 0
        
        # 신규 공고 저장
        success_count = 0
        
        if new_announcements:
            logging.info(f"🆕 신규 공고 저장: {len(new_announcements)}개")
            
            new_records = []
            for ann in new_announcements:
                announcement_id = f"KS_{ann.get('bizPbancSn', '')}"
                
                # 레코드 생성
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
                    'attachment_processing_status': 'pending',
                    'created_at': datetime.now().isoformat()
                }
                
                new_records.append(record)
            
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
        
        # 업데이트된 공고 처리 (필요시)
        if updated_announcements:
            logging.info(f"🔄 업데이트 필요 공고: {len(updated_announcements)}개 (현재 스킵)")
        
        elapsed = time.time() - start_time
        
        # 결과 요약
        logging.info("\n" + "="*50)
        logging.info("📊 수집 결과")
        logging.info(f"✅ 신규 저장: {success_count}개")
        logging.info(f"⏭️ 중복 제외: {len(announcements) - len(new_announcements)}개")
        logging.info(f"⏱️ 처리 시간: {elapsed:.1f}초")
        if len(announcements) > 0:
            logging.info(f"⚡ 평균 속도: {len(announcements)/elapsed:.1f}개/초")
        
        # 알림용 메시지 (신규 공고가 많으면)
        if success_count > 10:
            logging.info(f"\n🎉 오늘 신규 공고가 {success_count}개나 있습니다!")
        
        logging.info("="*50)
        
        return success_count
    
    def parse_date_fast(self, date_str):
        """빠른 날짜 파싱"""
        if not date_str:
            return None
        
        try:
            date_str = str(date_str).strip()[:10]  # 날짜 부분만
            
            if '-' in date_str:
                return date_str
            elif '.' in date_str:
                return date_str.replace('.', '-')
            elif len(date_str) == 8 and date_str.isdigit():
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            return None
        except:
            return None
    
    def parse_date_from_text(self, text):
        """텍스트에서 날짜 추출"""
        if not text:
            return None
        
        import re
        
        # 2025-01-01, 2025.01.01, 2025/01/01 형식
        patterns = [
            r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})',
            r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)',
            r'(\d{2}[-./]\d{1,2}[-./]\d{1,2})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return self.parse_date_fast(match.group(1))
        
        return None
    
    def run(self):
        """메인 실행"""
        try:
            start_time = time.time()
            
            # 0. 마지막 수집 정보 확인
            last_collected = self.get_last_collected_info()
            
            # 1. 병렬 조회 (최대 1000개)
            announcements = self.fetch_all_announcements_fast()
            
            if not announcements:
                logging.info("수집할 새로운 공고가 없습니다.")
                return True
            
            logging.info(f"📋 전체 조회: {len(announcements)}개")
            
            # 2. 배치 저장 (중복 체크 포함)
            saved_count = self.save_to_database_batch(announcements)
            
            # 3. 전체 시간
            total_elapsed = time.time() - start_time
            logging.info(f"\n🚀 전체 처리 시간: {total_elapsed:.1f}초")
            
            # 4. 처리 통계
            if saved_count > 0:
                logging.info(f"✨ 새로운 공고 {saved_count}개 추가 완료!")
            
            return True
            
        except Exception as e:
            logging.error(f"실행 중 오류: {e}")
            return False
        finally:
            # 세션 종료
            self.session.close()

if __name__ == "__main__":
    collector = KStartupCollectorFast()
    success = collector.run()
    sys.exit(0 if success else 1)
