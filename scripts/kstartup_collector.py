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
        
        # API 설정
        self.api_base_url = "https://www.k-startup.go.kr/web/module/bizpbanc-list.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json'
        }
        
        logging.info("=== K-Startup 데이터 수집 시작 ===")
    
    def get_api_key(self):
        """API 키 조회"""
        try:
            result = self.supabase.table('api_credentials').select('api_key_encrypted').eq('service_name', 'kstartup').execute()
            if result.data:
                return result.data[0]['api_key_encrypted']
            else:
                logging.warning("K-Startup API 키가 등록되지 않았습니다")
                return None
        except Exception as e:
            logging.error(f"API 키 조회 오류: {e}")
            return None
    
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
            
            response = requests.post(
                self.api_base_url,
                headers=self.headers,
                json=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'resultList' in data:
                    logging.info(f"K-Startup API 조회 성공: {len(data['resultList'])}개")
                    return data['resultList']
                else:
                    logging.info("조회 결과가 없습니다")
                    return []
            else:
                logging.error(f"API 응답 오류: {response.status_code}")
                # 대체 방법: 웹 스크래핑
                return self.scrape_announcements()
                
        except Exception as e:
            logging.error(f"API 조회 오류: {e}")
            return self.scrape_announcements()
    
    def scrape_announcements(self):
        """웹 스크래핑 (API 실패 시 대체)"""
        try:
            from bs4 import BeautifulSoup
            
            url = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                announcements = []
                
                # 공고 목록 파싱
                items = soup.find_all('div', class_='ann_list_item') or soup.find_all('li', class_='item')
                
                for item in items[:50]:  # 최대 50개
                    try:
                        announcement = {
                            'bizPbancSn': item.get('data-id', f"KS_{datetime.now().strftime('%Y%m%d')}_{len(announcements)}"),
                            'bizPbancNm': item.find(['h3', 'h4', 'a'], class_=['title', 'tit']).get_text(strip=True),
                            'pbancNtrpNm': item.find(['span', 'div'], class_=['org', 'agency']).get_text(strip=True) if item.find(['span', 'div'], class_=['org', 'agency']) else '',
                            'pbancRcptBgngDt': self.extract_date(item, 'start'),
                            'pbancRcptEndDt': self.extract_date(item, 'end'),
                            'detlPgUrl': urljoin(url, item.find('a')['href']) if item.find('a') else ''
                        }
                        announcements.append(announcement)
                    except Exception as e:
                        logging.error(f"항목 파싱 오류: {e}")
                        continue
                
                logging.info(f"웹 스크래핑 성공: {len(announcements)}개")
                return announcements
            else:
                logging.error(f"웹 페이지 접속 실패: {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"스크래핑 오류: {e}")
            return []
    
    def extract_date(self, element, date_type):
        """날짜 추출 헬퍼"""
        try:
            date_text = element.find(['span', 'div'], class_=['date', 'period']).get_text(strip=True)
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
        """데이터베이스 저장"""
        success_count = 0
        duplicate_count = 0
        error_count = 0
        
        for ann in announcements:
            try:
                # announcement_id 생성
                announcement_id = f"KS_{ann.get('bizPbancSn', '')}"
                
                # 중복 체크
                existing = self.supabase.table('kstartup_complete').select('id').eq('announcement_id', announcement_id).execute()
                
                if existing.data:
                    duplicate_count += 1
                    logging.info(f"  ⏭️ 중복: {ann.get('bizPbancNm', '')[:50]}...")
                    continue
                
                # 레코드 생성
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
                
                # DB 저장
                result = self.supabase.table('kstartup_complete').insert(record).execute()
                if result.data:
                    success_count += 1
                    logging.info(f"  ✅ 저장: {record['biz_pbanc_nm'][:50]}...")
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                logging.error(f"  ❌ 저장 오류: {e}")
                continue
        
        # 결과 요약
        logging.info("\n=== 수집 결과 ===")
        logging.info(f"✅ 신규 저장: {success_count}개")
        logging.info(f"⏭️ 중복 제외: {duplicate_count}개")
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
                return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
            
            # 2025.08.08 형식
            elif '.' in date_str:
                date_str = date_str.replace('.', '-')
                return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
            
            # 20250808 형식
            elif len(date_str) == 8 and date_str.isdigit():
                return datetime.strptime(date_str, '%Y%m%d').date()
            
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
                return
            
            # 2. DB 저장
            saved_count = self.save_to_database(announcements)
            
            # 3. 성공 여부 반환
            return saved_count > 0
            
        except Exception as e:
            logging.error(f"실행 중 오류: {e}")
            return False

if __name__ == "__main__":
    collector = KStartupCollector()
    success = collector.run()
    sys.exit(0 if success else 1)
