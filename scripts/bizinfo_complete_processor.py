#!/usr/bin/env python3
"""
기업마당 통합 처리 스크립트 (GitHub Actions용)
- 첨부파일 링크 크롤링
- 해시태그 및 요약 생성
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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class BizInfoCompleteProcessor:
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
        }
        
        logging.info("=== 기업마당 통합 처리 시작 ===")
    
    def run(self):
        """전체 프로세스 실행"""
        try:
            # Step 1: 처리 대상 조회
            unprocessed = self.get_unprocessed_announcements()
            logging.info(f"처리 대상: {len(unprocessed)}개")
            
            if not unprocessed:
                logging.info("처리할 데이터가 없습니다.")
                return
            
            # Step 2: 배치 처리
            success_count = 0
            attachment_count = 0
            error_count = 0
            
            for idx, item in enumerate(unprocessed, 1):
                try:
                    logging.info(f"\n[{idx}/{len(unprocessed)}] {item['pblanc_nm'][:50]}...")
                    
                    # 첨부파일 크롤링
                    attachments = []
                    if item.get('dtl_url'):
                        attachments = self.extract_attachments(item['pblanc_id'], item['dtl_url'])
                        if attachments:
                            attachment_count += len(attachments)
                            logging.info(f"  ├─ 첨부파일: {len(attachments)}개")
                    
                    # 해시태그 생성
                    hashtags = self.generate_hashtags(item)
                    if hashtags:
                        logging.info(f"  ├─ 해시태그: {len(hashtags.split())}개")
                    
                    # 요약 생성
                    summary = self.create_summary(item, attachments, hashtags)
                    logging.info(f"  ├─ 요약: {len(summary)}자")
                    
                    # DB 업데이트
                    if self.update_database(item['id'], attachments, hashtags, summary):
                        success_count += 1
                        logging.info(f"  └─ ✅ 처리 완료")
                    else:
                        error_count += 1
                        logging.error(f"  └─ ❌ 업데이트 실패")
                    
                    # API 부하 방지
                    if idx % 10 == 0:
                        time.sleep(2)
                    else:
                        time.sleep(0.5)
                        
                except Exception as e:
                    error_count += 1
                    logging.error(f"  └─ ❌ 처리 오류: {e}")
                    continue
            
            # 결과 요약
            logging.info("\n" + "="*50)
            logging.info("📊 처리 결과")
            logging.info(f"  전체: {len(unprocessed)}개")
            logging.info(f"  성공: {success_count}개")
            logging.info(f"  실패: {error_count}개")
            logging.info(f"  첨부파일: {attachment_count}개")
            logging.info("="*50)
            
        except Exception as e:
            logging.error(f"처리 중 오류: {e}")
            raise
    
    def get_unprocessed_announcements(self, limit=None):
        """처리 안 된 공고 조회 (수정)"""
        try:
            # attachment_urls가 비어있는 데이터 조회
            query = self.supabase.table('bizinfo_complete').select(
                'id', 'pblanc_id', 'pblanc_nm', 'dtl_url', 
                'spnsr_organ_nm', 'exctv_organ_nm', 'sprt_realm_nm',
                'reqst_begin_ymd', 'reqst_end_ymd'
            ).or_(
                'attachment_urls.is.null,attachment_urls.eq.[]'
            ).order('created_at', desc=True)
            
            if limit:
                query = query.limit(limit)
            else:
                query = query.limit(100)  # 한 번에 최대 100개
            
            result = query.execute()
            return result.data
            
        except Exception as e:
            logging.error(f"데이터 조회 오류: {e}")
            # or_ 오류 시 다른 방법 시도
            try:
                query = self.supabase.table('bizinfo_complete').select(
                    'id', 'pblanc_id', 'pblanc_nm', 'dtl_url',
                    'spnsr_organ_nm', 'exctv_organ_nm', 'sprt_realm_nm',
                    'reqst_begin_ymd', 'reqst_end_ymd', 'attachment_urls'
                ).order('created_at', desc=True).limit(500)
                
                result = query.execute()
                # attachment_urls가 없거나 빈 배열인 것만 필터
                unprocessed = []
                for item in result.data:
                    if not item.get('attachment_urls') or item.get('attachment_urls') == []:
                        # attachment_urls 필드 제거 (필요없음)
                        item.pop('attachment_urls', None)
                        unprocessed.append(item)
                        if limit and len(unprocessed) >= limit:
                            break
                
                return unprocessed[:100]  # 최대 100개
            except Exception as e2:
                logging.error(f"대체 조회도 실패: {e2}")
                return []
    
    def extract_attachments(self, pblanc_id, detail_url):
        """상세 페이지에서 첨부파일 추출"""
        if not detail_url:
            return []
        
        try:
            response = requests.get(detail_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            attachments = []
            
            # 첨부파일 패턴
            patterns = [
                r'getImageFile\.do',
                r'FileDownload\.do', 
                r'downloadFile',
                r'다운로드|download'
            ]
            
            # 첨부파일 영역 찾기
            file_areas = soup.find_all(['div', 'td', 'ul'], class_=re.compile(r'attach|file|down', re.I))
            
            # 모든 링크 검사
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # 패턴 매칭
                for pattern in patterns:
                    if re.search(pattern, href + text, re.I):
                        full_url = urljoin(detail_url, href)
                        
                        attachment = {
                            'url': full_url,
                            'name': text or '첨부파일',
                            'type': self.get_file_type(text, href)
                        }
                        
                        # 중복 제거
                        if attachment['url'] not in [a['url'] for a in attachments]:
                            attachments.append(attachment)
                        break
            
            return attachments
            
        except Exception as e:
            logging.error(f"첨부파일 크롤링 오류: {e}")
            return []
    
    def get_file_type(self, text, url):
        """파일 타입 추출"""
        text_lower = text.lower()
        url_lower = url.lower()
        
        if any(ext in text_lower + url_lower for ext in ['.hwp', 'hwp']):
            return 'HWP'
        elif any(ext in text_lower + url_lower for ext in ['.pdf', 'pdf']):
            return 'PDF'
        elif any(ext in text_lower + url_lower for ext in ['.doc', '.docx', 'word']):
            return 'DOC'
        elif any(ext in text_lower + url_lower for ext in ['.xls', '.xlsx', 'excel']):
            return 'EXCEL'
        elif any(ext in text_lower + url_lower for ext in ['.ppt', '.pptx']):
            return 'PPT'
        elif any(ext in text_lower + url_lower for ext in ['.zip', '.rar']):
            return 'ZIP'
        else:
            return 'FILE'
    
    def generate_hashtags(self, item):
        """해시태그 생성"""
        tags = []
        
        # 지원분야에서 추출
        if item.get('sprt_realm_nm'):
            field = item['sprt_realm_nm']
            field_tags = [t.strip() for t in field.split(',') if t.strip()]
            tags.extend(field_tags[:3])  # 최대 3개
        
        # 주관기관 (짧은 것만)
        if item.get('spnsr_organ_nm'):
            org = item['spnsr_organ_nm'].replace('(주)', '').strip()
            if len(org) <= 10:
                tags.append(org)
        
        # 공고명에서 주요 키워드 추출
        if item.get('pblanc_nm'):
            title = item['pblanc_nm']
            title_keywords = ['R&D', 'AI', '인공지능', '빅데이터', '바이오', '환경', '그린', 
                            '디지털', '혁신', '글로벌', '수출', '기술개발', '사업화', '투자',
                            '스타트업', '중소기업', '소상공인', '창업']
            for keyword in title_keywords:
                if keyword.lower() in title.lower():
                    tags.append(keyword)
        
        # 중복 제거 및 해시태그 형식으로 변환
        unique_tags = list(dict.fromkeys(tags))  # 순서 유지하며 중복 제거
        hashtags = ' '.join([f'#{tag.strip()}' for tag in unique_tags[:10]])  # 최대 10개
        
        return hashtags
    
    def create_summary(self, item, attachments, hashtags):
        """요약 생성"""
        summary_parts = []
        
        # 공고명
        if item.get('pblanc_nm'):
            summary_parts.append(f"📋 {item['pblanc_nm']}")
        
        # 주관/수행기관
        if item.get('spnsr_organ_nm'):
            summary_parts.append(f"🏢 주관: {item['spnsr_organ_nm']}")
        elif item.get('exctv_organ_nm'):
            summary_parts.append(f"🏢 수행: {item['exctv_organ_nm']}")
        
        # 신청기간 및 D-Day
        if item.get('reqst_begin_ymd') and item.get('reqst_end_ymd'):
            start_date = item['reqst_begin_ymd']
            end_date = item['reqst_end_ymd']
            summary_parts.append(f"📅 기간: {start_date} ~ {end_date}")
            
            # D-Day 계산
            try:
                if end_date:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d') if '-' in end_date else datetime.strptime(end_date, '%Y%m%d')
                    days_left = (end_dt - datetime.now()).days
                    
                    if 0 <= days_left <= 3:
                        summary_parts.append(f"🚨 마감임박 D-{days_left}")
                    elif 4 <= days_left <= 7:
                        summary_parts.append(f"⏰ D-{days_left}")
                    elif days_left > 0:
                        summary_parts.append(f"📆 D-{days_left}")
            except:
                pass
        
        # 첨부파일
        if attachments:
            file_types = list(set([a['type'] for a in attachments]))
            summary_parts.append(f"📎 첨부: {', '.join(file_types)} ({len(attachments)}개)")
        
        # 해시태그
        if hashtags:
            summary_parts.append(f"🏷️ {hashtags}")
        
        return '\n'.join(summary_parts)
    
    def update_database(self, record_id, attachments, hashtags, summary):
        """DB 업데이트 (컬럼명 수정: hash_tag)"""
        try:
            update_data = {
                'attachment_urls': attachments if attachments else [],
                'hash_tag': hashtags,  # hash_tags -> hash_tag
                'bsns_sumry': summary,
                'attachment_processing_status': 'completed',
                'updated_at': datetime.now().isoformat()
            }
            
            result = self.supabase.table('bizinfo_complete').update(
                update_data
            ).eq('id', record_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logging.error(f"DB 업데이트 오류: {e}")
            return False

if __name__ == "__main__":
    processor = BizInfoCompleteProcessor()
    processor.run()
