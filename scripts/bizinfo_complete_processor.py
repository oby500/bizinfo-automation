#!/usr/bin/env python3
"""
기업마당 통합 처리 스크립트 (GitHub Actions용)
- 첨부파일 링크 크롤링 (safe_filename, display_filename 포함)
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
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.bizinfo.go.kr/'
        }
        
        logging.info("=== 기업마당 통합 처리 시작 ===")
    
    def clean_filename(self, text):
        """파일명 정리 - 불필요한 텍스트 제거"""
        if not text:
            return None
        
        # 파일명 패턴: 확장자를 포함한 파일명 찾기
        patterns = [
            r'([^\/\\:*?"<>|\n\r\t]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b',
            r'([^\s]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                filename = match.group(1).strip()
                # 첨부파일, 다운로드 등의 단어 제거
                filename = re.sub(r'^(첨부파일\s*|다운로드\s*)', '', filename)
                filename = re.sub(r'\s*(다운로드|첨부파일)\s*$', '', filename)
                return filename
        
        return None
    
    def create_safe_filename(self, pblanc_id, index, original_filename):
        """안전한 파일명 생성"""
        if original_filename:
            # 확장자 추출
            ext = ''
            if '.' in original_filename:
                ext = original_filename.split('.')[-1].lower()
                # 확장자가 너무 길면 unknown
                if len(ext) > 10:
                    ext = 'unknown'
            else:
                ext = 'unknown'
            
            # 안전한 파일명: pblanc_id_순번.확장자
            safe_name = f"{pblanc_id}_{index:02d}.{ext}"
            return safe_name
        
        # 파일명을 알 수 없는 경우
        return f"{pblanc_id}_{index:02d}.unknown"
    
    def get_filename_from_head_request(self, url):
        """HEAD 요청으로 실제 파일명 추출"""
        try:
            response = requests.head(url, headers=self.headers, allow_redirects=True, timeout=5)
            content_disposition = response.headers.get('Content-Disposition', '')
            
            if content_disposition:
                # filename*=UTF-8'' 패턴
                match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
                if match:
                    filename = requests.utils.unquote(match.group(1))
                    return filename
                
                # filename= 패턴
                match = re.search(r'filename="?([^"\;]+)"?', content_disposition)
                if match:
                    filename = match.group(1)
                    try:
                        filename = filename.encode('iso-8859-1').decode('utf-8')
                    except:
                        pass
                    return filename
        except:
            pass
        
        return None
    
    def extract_hashtags_from_page(self, soup):
        """페이지에서 해시태그 추출"""
        hashtags = []
        
        try:
            # tag_ul_list 클래스 찾기
            tag_list = soup.find('ul', class_='tag_ul_list')
            if tag_list:
                tag_items = tag_list.find_all('li', class_=re.compile(r'tag_li_list\d'))
                for item in tag_items:
                    link = item.find('a')
                    if link:
                        tag_text = link.get_text(strip=True)
                        if tag_text and tag_text not in hashtags:
                            hashtags.append(tag_text)
            
            # 대체 패턴: hashtag 클래스
            if not hashtags:
                hashtag_elements = soup.find_all(class_=re.compile(r'hashtag', re.I))
                for elem in hashtag_elements:
                    tag_text = elem.get_text(strip=True)
                    if tag_text and tag_text not in hashtags:
                        hashtags.append(tag_text)
        except:
            pass
        
        return hashtags
    
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
                    page_hashtags = []
                    
                    if item.get('dtl_url'):
                        attachments, page_hashtags = self.extract_attachments(item['pblanc_id'], item['dtl_url'])
                        if attachments:
                            attachment_count += len(attachments)
                            logging.info(f"  ├─ 첨부파일: {len(attachments)}개")
                            for att_idx, att in enumerate(attachments, 1):
                                logging.info(f"    └─ {att.get('safe_filename', '')} => {att.get('display_filename', '')}")
                    
                    # 해시태그 생성 (페이지 해시태그 + 자동 생성)
                    hashtags = self.generate_hashtags(item, page_hashtags)
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
        """처리 안 된 공고 조회"""
        try:
            query = self.supabase.table('bizinfo_complete').select(
                'id', 'pblanc_id', 'pblanc_nm', 'dtl_url',
                'spnsr_organ_nm', 'exctv_organ_nm', 'sprt_realm_nm',
                'reqst_begin_ymd', 'reqst_end_ymd', 'attachment_urls'
            ).order('created_at', desc=True).limit(500)
            
            result = query.execute()
            
            # attachment_urls가 없거나 safe_filename이 없는 것만 필터
            unprocessed = []
            for item in result.data:
                if not item.get('attachment_urls'):
                    # attachment_urls가 비어있음
                    item.pop('attachment_urls', None)
                    unprocessed.append(item)
                else:
                    # attachment_urls는 있는데 safe_filename이 없는 경우
                    urls_str = json.dumps(item['attachment_urls'])
                    if 'safe_filename' not in urls_str:
                        item.pop('attachment_urls', None)
                        unprocessed.append(item)
                
                if limit and len(unprocessed) >= limit:
                    break
            
            return unprocessed[:100]  # 최대 100개
            
        except Exception as e:
            logging.error(f"데이터 조회 오류: {e}")
            return []
    
    def extract_attachments(self, pblanc_id, detail_url):
        """상세 페이지에서 첨부파일 추출 (safe_filename 포함)"""
        if not detail_url:
            return [], []
        
        try:
            response = requests.get(detail_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            attachments = []
            
            # 해시태그 추출
            page_hashtags = self.extract_hashtags_from_page(soup)
            
            # 첨부파일 패턴
            patterns = [
                {'regex': r'getImageFile\.do', 'type': 'getImageFile'},
                {'regex': r'FileDownload\.do', 'type': 'FileDownload'},
                {'regex': r'downloadFile', 'type': 'downloadFile'},
                {'regex': r'download\.do', 'type': 'download'},
                {'regex': r'/cmm/fms/', 'type': 'fms'}
            ]
            
            # 모든 링크 검사
            all_links = soup.find_all('a', href=True)
            attachment_index = 0
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                onclick = link.get('onclick', '')
                title = link.get('title', '')
                
                # 첨부파일 관련 링크 찾기
                for pattern in patterns:
                    if re.search(pattern['regex'], href) or re.search(pattern['regex'], onclick):
                        # onclick에서 URL 추출
                        if onclick and not href:
                            url_match = re.search(r"['\"]([^'\"]*" + pattern['regex'] + r"[^'\"]*)['\"]", onclick)
                            if url_match:
                                href = url_match.group(1)
                        
                        if href:
                            full_url = urljoin(detail_url, href)
                            
                            # URL 파라미터 추출
                            parsed = urlparse(full_url)
                            params = parse_qs(parsed.query)
                            
                            # 파일명 찾기
                            display_filename = None
                            original_filename = text or '첨부파일'
                            
                            # 1. 링크 텍스트에서 파일명 찾기
                            if text and text != '다운로드':
                                display_filename = self.clean_filename(text)
                                if display_filename:
                                    original_filename = display_filename
                            
                            # 2. title 속성에서 찾기
                            if not display_filename and title:
                                display_filename = self.clean_filename(title)
                                if display_filename:
                                    original_filename = display_filename
                            
                            # 3. HEAD 요청으로 실제 파일명 가져오기
                            if not display_filename or display_filename == '첨부파일':
                                real_filename = self.get_filename_from_head_request(full_url)
                                if real_filename:
                                    display_filename = real_filename
                                    original_filename = real_filename
                            
                            # display_filename이 없으면 기본값
                            if not display_filename:
                                display_filename = f"첨부파일_{attachment_index + 1}"
                            
                            # 중복 체크
                            if full_url not in [a['url'] for a in attachments]:
                                attachment_index += 1
                                
                                # safe_filename 생성
                                safe_filename = self.create_safe_filename(pblanc_id, attachment_index, display_filename)
                                
                                # 파일 타입 결정
                                file_type = self.get_file_type(display_filename, href)
                                
                                attachment = {
                                    'url': full_url,
                                    'text': '다운로드',
                                    'type': file_type,
                                    'params': {k: v[0] if len(v) == 1 else v for k, v in params.items()},
                                    'safe_filename': safe_filename,
                                    'display_filename': display_filename,
                                    'original_filename': original_filename
                                }
                                
                                attachments.append(attachment)
                        break
            
            return attachments, page_hashtags
            
        except Exception as e:
            logging.error(f"첨부파일 크롤링 오류: {e}")
            return [], []
    
    def get_file_type(self, filename, url):
        """파일 타입 추출"""
        text_lower = filename.lower() if filename else ''
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
        elif any(ext in text_lower + url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return 'IMAGE'
        else:
            return 'FILE'
    
    def generate_hashtags(self, item, page_hashtags=None):
        """해시태그 생성 (페이지 해시태그 + 자동 생성)"""
        tags = []
        
        # 페이지에서 추출한 해시태그 추가
        if page_hashtags:
            tags.extend(page_hashtags[:5])  # 최대 5개
        
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
        """DB 업데이트"""
        try:
            update_data = {
                'attachment_urls': attachments if attachments else [],
                'hash_tag': hashtags,
                'bsns_sumry': summary,
                'attachment_processing_status': 'completed',
                'updt_dt': datetime.now().isoformat()
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
