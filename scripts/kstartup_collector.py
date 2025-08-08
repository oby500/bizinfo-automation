#!/usr/bin/env python3
"""
K-Startup 데이터 수집 스크립트 (GitHub Actions용)
오전 7시 자동 실행
"""
import os
import sys
import requests
import json
from datetime import datetime, timedelta
from urllib.parse import urljoin
from supabase import create_client, Client
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class KStartupCollector:
    def __init__(self):
        """초기화"""
        # Supabase 연결
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            logging.error("환경변수가 설정되지 않았습니다.")
            sys.exit(1)
            
        self.supabase: Client = create_client(url, key)
        
        # API 설정 - HTTP 사용 (HTTPS 아님)
        self.api_base_url = "http://www.k-startup.go.kr/web/module/bizpbanc-list.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        }
        
        logging.info("=== K-Startup 데이터 수집 시작 ===")
    
    def fetch_announcements(self):
        """K-Startup 공고 목록 조회"""
        try:
            # API 파라미터 설정
            params = {
                'page': 1,
                'pageSize': 50,  # 한 번에 50개
                'searchType': 'all',
                'searchPbancSttsCd': '01',  # 모집중
                'orderBy': 'recent'  # 최신순
            }
            
            # HTTP 사용 (HTTPS 아님)
            response = requests.post(
                self.api_base_url,
                headers=self.headers,
                json=params,
                timeout=30
            )
            
            logging.info(f"API 응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    # 응답 텍스트 확인
                    response_text = response.text
                    if not response_text:
                        logging.warning("빈 응답 받음")
                        return self.scrape_announcements()
                    
                    data = response.json()
                    if 'resultList' in data:
                        logging.info(f"K-Startup API 조회 성공: {len(data['resultList'])}개")
                        return data['resultList']
                    else:
                        logging.info("조회 결과가 없습니다")
                        return self.scrape_announcements()
                except json.JSONDecodeError as e:
                    logging.error(f"JSON 파싱 오류: {e}")
                    logging.error(f"응답 내용: {response.text[:500]}")
                    return self.scrape_announcements()
            else:
                logging.error(f"API 응답 오류: {response.status_code}")
                return self.scrape_announcements()
                
        except Exception as e:
            logging.error(f"API 조회 오류: {e}")
            return self.scrape_announcements()
    
    def scrape_announcements(self):
        """웹 스크래핑 (API 실패 시 대체)"""
        try:
            from bs4 import BeautifulSoup
            
            logging.info("웹 스크래핑 시작...")
            # 웹페이지는 HTTPS 사용
            url = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                announcements = []
                
                # 공고 목록 파싱 - 더 다양한 선택자 시도
                items = (soup.find_all('div', class_='ann_list_item') or 
                        soup.find_all('li', class_='item') or
                        soup.find_all('div', class_='list_item') or
                        soup.find_all('article', class_='item'))
                
                if not items:
                    # 테이블 형식일 경우
                    table = soup.find('table', class_=['table', 'list', 'board'])
                    if table:
                        items = table.find_all('tr')[1:]  # 헤더 제외
                
                logging.info(f"발견된 항목 수: {len(items)}")
                
                for idx, item in enumerate(items[:50], 1):  # 최대 50개
                    try:
                        # 제목 찾기
                        title_elem = (item.find('a', class_=['title', 'tit', 'subject']) or
                                     item.find('h3') or item.find('h4') or 
                                     item.find('a'))
                        
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        href = title_elem.get('href', '')
                        
                        # ID 생성
                        item_id = item.get('data-id') or item.get('id') or f"{datetime.now().strftime('%Y%m%d')}_{idx}"
                        
                        announcement = {
                            'bizPbancSn': item_id,
                            'bizPbancNm': title,
                            'pbancNtrpNm': self.extract_text(item, ['org', 'agency', 'company']),
                            'pbancRcptBgngDt': self.extract_date(item, 'start'),
                            'pbancRcptEndDt': self.extract_date(item, 'end'),
                            'detlPgUrl': urljoin(url, href) if href else ''
                        }
                        
                        if announcement['bizPbancNm']:  # 제목이 있는 경우만 추가
                            announcements.append(announcement)
                            logging.info(f"  스크래핑: {announcement['bizPbancNm'][:30]}...")
                            
                    except Exception as e:
                        logging.error(f"항목 파싱 오류: {e}")
                        continue
                
                logging.info(f"웹 스크래핑 완료: {len(announcements)}개")
                return announcements
            else:
                logging.error(f"웹 페이지 접속 실패: {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"스크래핑 오류: {e}")
            return []
    
    def extract_text(self, element, class_names):
        """텍스트 추출 헬퍼"""
        for class_name in class_names:
            elem = element.find(['span', 'div', 'td'], class_=class_name)
            if elem:
                return elem.get_text(strip=True)
        return ''
    
    def extract_date(self, element, date_type):
        """날짜 추출 헬퍼"""
        try:
            date_elem = element.find(['span', 'div', 'td'], class_=['date', 'period', 'term'])
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                if '~' in date_text:
                    dates = date_text.split('~')
                    if date_type == 'start':
                        return dates[0].strip().replace('.', '-')
                    else:
                        return dates[1].strip().replace('.', '-')
            return None
        except:
            return None
    
    def save_to_database(self, announcements):
        """데이터베이스 저장 (최적화)"""
        if not announcements:
            logging.info("저장할 데이터가 없습니다.")
            return 0
        
        # 1. 기존 ID 한 번에 조회
        logging.info("기존 데이터 확인 중...")
        existing_result = self.supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = {item['announcement_id'] for item in existing_result.data} if existing_result.data else set()
        logging.info(f"기존 데이터: {len(existing_ids)}개")
        
        # 2. 신규 데이터만 필터링
        new_records = []
        duplicate_count = 0
        
        for ann in announcements:
            # announcement_id 생성
            announcement_id = f"KS_{ann.get('bizPbancSn', '')}"
            
            # 메모리에서 중복 체크
            if announcement_id in existing_ids:
                duplicate_count += 1
                if duplicate_count <= 5:  # 처음 5개만 출력
                    logging.info(f"  ⏭️ 중복: {ann.get('bizPbancNm', '')[:30]}...")
                continue
            
            # 신규 레코드 생성
            record = {
                'announcement_id': announcement_id,
                'biz_pbanc_nm': ann.get('bizPbancNm', ''),
                'pbanc_ctnt': ann.get('pbancCtnt', ''),
                'supt_biz_clsfc': ann.get('suptBizClsfc', ''),
                'aply_trgt_ctnt': ann.get('aplyTrgtCtnt', ''),
                'supt_regin': ann.get('suptRegin', ''),
                'pbanc_rcpt_bgng_dt': self.parse_date(ann.get('pbancRcptBgngDt')),
                'pbanc_rcpt_end_dt': self.parse_date(ann.get('pbancRcptEndDt')),
                'pbanc_ntrp_nm': ann.get('pbancNtrpNm', ''),
                'biz_gdnc_url': ann.get('bizGdncUrl', ''),
                'biz_aply_url': ann.get('bizAplyUrl', ''),
                'detl_pg_url': ann.get('detlPgUrl', ''),
                'attachment_urls': [],
                'attachment_count': 0,
                'created_at': datetime.now().isoformat()
            }
            
            new_records.append(record)
            logging.info(f"  ✅ 신규: {record['biz_pbanc_nm'][:30]}...")
        
        # 3. 배치 저장
        success_count = 0
        error_count = 0
        
        if new_records:
            logging.info(f"\n배치 저장 중... ({len(new_records)}개)")
            try:
                # K-Startup은 보통 50개 이하라 한 번에 저장 가능
                result = self.supabase.table('kstartup_complete').insert(new_records).execute()
                if result.data:
                    success_count = len(result.data)
                    logging.info(f"  배치 저장 완료: {success_count}개")
            except Exception as e:
                # 실패 시 개별 저장으로 fallback
                logging.error(f"배치 저장 실패, 개별 저장 시도: {e}")
                for record in new_records:
                    try:
                        result = self.supabase.table('kstartup_complete').insert(record).execute()
                        if result.data:
                            success_count += 1
                    except Exception as e2:
                        error_count += 1
                        logging.error(f"  개별 저장 오류: {e2}")
        
        # 결과 요약
        logging.info("\n=== 수집 결과 ===")
        logging.info(f"✅ 신규 저장: {success_count}개")
        logging.info(f"⏭️ 중복 제외: {duplicate_count}개")
        if error_count > 0:
            logging.info(f"❌ 오류: {error_count}개")
        logging.info(f"📊 전체 처리: {len(announcements)}개")
        
        return success_count
    
    def parse_date(self, date_str):
        """날짜 문자열 파싱"""
        if not date_str:
            return None
        
        try:
            # 다양한 형식 처리
            date_str = date_str.strip()
            
            # 2025-08-08 형식
            if '-' in date_str:
                return datetime.strptime(date_str[:10], '%Y-%m-%d').date().isoformat()
            
            # 2025.08.08 형식
            elif '.' in date_str:
                date_str = date_str.replace('.', '-')
                return datetime.strptime(date_str[:10], '%Y-%m-%d').date().isoformat()
            
            # 20250808 형식
            elif len(date_str) == 8 and date_str.isdigit():
                return datetime.strptime(date_str, '%Y%m%d').date().isoformat()
            
            return None
        except:
            return None
    
    def run(self):
        """메인 실행"""
        try:
            # 1. 공고 목록 조회
            announcements = self.fetch_announcements()
            
            if not announcements:
                logging.info("수집할 새로운 공고가 없습니다.")
                # 빈 리스트라도 정상 종료
                return True
            
            # 2. DB 저장
            saved_count = self.save_to_database(announcements)
            
            # 3. 성공 여부 반환
            return True  # 에러가 없으면 성공
            
        except Exception as e:
            logging.error(f"실행 중 오류: {e}")
            return False

if __name__ == "__main__":
    collector = KStartupCollector()
    success = collector.run()
    sys.exit(0 if success else 1)
