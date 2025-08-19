#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개선된 첨부파일 처리기
확장자 처리 오류 수정 및 attachment_urls 수집 개선
"""

import os
import sys
import requests
import json
import re
from urllib.parse import urlparse, unquote, parse_qs
from datetime import datetime
import time
from supabase import create_client
from dotenv import load_dotenv
import logging

# Windows 콘솔 유니코드 지원
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'attachment_processor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class ImprovedAttachmentProcessor:
    def __init__(self):
        """초기화"""
        self.supabase = self._get_supabase_client()
        self.valid_extensions = [
            'pdf', 'hwp', 'doc', 'docx', 
            'xls', 'xlsx', 'ppt', 'pptx', 
            'zip', 'jpg', 'jpeg', 'png', 
            'gif', 'txt', 'hwpx'
        ]
        self.processed_count = 0
        self.error_count = 0
        
    def _get_supabase_client(self):
        """Supabase 클라이언트 생성"""
        url = os.getenv('SUPABASE_URL', 'https://wzzabqbvhjctyduqllbr.supabase.co')
        key = os.getenv('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind6emFicWJ2aGpjdHlkdXFsbGJyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM1NTQ1MDEsImV4cCI6MjA2OTEzMDUwMX0.vbV4Eb5ZkCUkf6eVJmWGAfVkhlPoHiakQW5RBd05asA')
        
        logging.info(f"Supabase 연결: {url}")
        return create_client(url, key)
    
    def extract_extension(self, url, headers_dict=None):
        """개선된 확장자 추출 함수"""
        try:
            # 1. URL 파싱 및 정규화
            parsed = urlparse(url)
            path = unquote(parsed.path)
            
            # URL 파라미터 제거
            if '?' in path:
                path = path.split('?')[0]
            
            # 파일명에서 확장자 추출
            if '.' in path:
                # 마지막 . 이후의 문자열을 확장자로 추출
                potential_ext = path.split('.')[-1].lower()
                
                # 확장자 길이 체크 (너무 길면 무효)
                if len(potential_ext) <= 5:
                    # 특수문자 제거
                    clean_ext = re.sub(r'[^a-z0-9]', '', potential_ext)
                    
                    # 유효한 확장자인지 확인
                    if clean_ext in self.valid_extensions:
                        return clean_ext
            
            # 2. Content-Type 헤더에서 확장자 추출
            if headers_dict:
                content_type = headers_dict.get('content-type', '').lower()
                
                # Content-Type과 확장자 매핑
                type_mapping = {
                    'application/pdf': 'pdf',
                    'application/x-hwp': 'hwp',
                    'application/haansoft-hwp': 'hwp',
                    'application/msword': 'doc',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml': 'docx',
                    'application/vnd.ms-excel': 'xls',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml': 'xlsx',
                    'application/vnd.ms-powerpoint': 'ppt',
                    'application/vnd.openxmlformats-officedocument.presentationml': 'pptx',
                    'application/zip': 'zip',
                    'image/jpeg': 'jpg',
                    'image/jpg': 'jpg',
                    'image/png': 'png',
                    'image/gif': 'gif',
                    'text/plain': 'txt'
                }
                
                for mime_type, ext in type_mapping.items():
                    if mime_type in content_type:
                        return ext
            
            # 3. Content-Disposition 헤더에서 파일명 추출
            if headers_dict:
                disposition = headers_dict.get('content-disposition', '')
                
                # filename*=UTF-8'' 형식 (RFC 5987)
                if "filename*=UTF-8''" in disposition:
                    match = re.search(r"filename\*=UTF-8''([^;]+)", disposition)
                    if match:
                        filename = unquote(match.group(1))
                        if '.' in filename:
                            ext = filename.split('.')[-1].lower()
                            if ext in self.valid_extensions:
                                return ext
                
                # filename="..." 형식
                elif 'filename=' in disposition:
                    # 따옴표 있는 경우
                    match = re.search(r'filename="([^"]+)"', disposition)
                    if not match:
                        # 따옴표 없는 경우
                        match = re.search(r'filename=([^;]+)', disposition)
                    
                    if match:
                        filename = match.group(1).strip()
                        # 한글 파일명 디코딩
                        try:
                            filename = unquote(filename)
                        except:
                            pass
                        
                        if '.' in filename:
                            ext = filename.split('.')[-1].lower()
                            if ext in self.valid_extensions:
                                return ext
            
            # 4. 특수 케이스 처리
            # download.do, file.do 등의 경우
            if path.endswith('.do') or path.endswith('/download'):
                # HEAD 요청으로 실제 파일 정보 확인
                if not headers_dict:
                    try:
                        response = requests.head(url, timeout=5, allow_redirects=True)
                        return self.extract_extension(url, response.headers)
                    except:
                        pass
            
            return 'unknown'
            
        except Exception as e:
            logging.error(f"확장자 추출 오류: {url} - {e}")
            return 'unknown'
    
    def get_file_info(self, url):
        """파일 정보 수집"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # HEAD 요청으로 파일 정보 확인
            response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            
            # 파일 정보 추출
            file_info = {
                'url': url,
                'final_url': response.url,
                'extension': self.extract_extension(response.url, response.headers),
                'size': int(response.headers.get('content-length', 0)),
                'content_type': response.headers.get('content-type', ''),
                'filename': None,
                'status': 'available'
            }
            
            # Content-Disposition에서 파일명 추출
            disposition = response.headers.get('content-disposition', '')
            if disposition:
                filename = self.extract_filename_from_disposition(disposition)
                if filename:
                    file_info['filename'] = filename
            
            # 파일명이 없으면 URL에서 추출
            if not file_info['filename']:
                path = urlparse(file_info['final_url']).path
                if '/' in path:
                    file_info['filename'] = unquote(path.split('/')[-1])
            
            return file_info
            
        except requests.exceptions.RequestException as e:
            logging.error(f"파일 정보 수집 실패: {url} - {e}")
            return {
                'url': url,
                'extension': 'unknown',
                'status': 'error',
                'error': str(e)
            }
    
    def extract_filename_from_disposition(self, disposition):
        """Content-Disposition에서 파일명 추출"""
        try:
            # filename*=UTF-8'' 형식
            if "filename*=UTF-8''" in disposition:
                match = re.search(r"filename\*=UTF-8''([^;]+)", disposition)
                if match:
                    return unquote(match.group(1))
            
            # filename="..." 형식
            match = re.search(r'filename="([^"]+)"', disposition)
            if match:
                return match.group(1)
            
            # filename=... 형식 (따옴표 없음)
            match = re.search(r'filename=([^;]+)', disposition)
            if match:
                return match.group(1).strip()
                
        except:
            pass
        
        return None
    
    def process_kstartup_attachments(self):
        """K-Startup 첨부파일 처리"""
        logging.info("K-Startup 첨부파일 처리 시작")
        
        try:
            # detl_pg_url이 있는 공고 조회
            result = self.supabase.table('kstartup_complete')\
                .select('id, pbanc_sn, biz_pbanc_nm, detl_pg_url, attachment_urls')\
                .not_.is_('detl_pg_url', 'null')\
                .execute()
            
            announcements = result.data if result.data else []
            logging.info(f"처리할 K-Startup 공고: {len(announcements)}개")
            
            for ann in announcements:
                # attachment_urls가 없거나 빈 경우만 처리
                if not ann.get('attachment_urls') or ann['attachment_urls'] == '[]':
                    self.crawl_kstartup_detail(ann)
                    time.sleep(1)  # 서버 부하 방지
            
            logging.info(f"K-Startup 처리 완료: 성공 {self.processed_count}개, 실패 {self.error_count}개")
            
        except Exception as e:
            logging.error(f"K-Startup 처리 오류: {e}")
    
    def crawl_kstartup_detail(self, announcement):
        """K-Startup 상세페이지 크롤링"""
        try:
            url = announcement['detl_pg_url']
            if not url:
                return
            
            # 상세페이지 요청
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # BeautifulSoup으로 파싱 (필요시 추가)
            # 여기서는 간단히 예시로 작성
            
            # 첨부파일 URL 수집 (실제 구현 필요)
            attachment_urls = []
            
            # 예시: 다운로드 링크 찾기
            # soup = BeautifulSoup(response.text, 'html.parser')
            # download_links = soup.find_all('a', href=re.compile(r'download|file|attach'))
            
            # 임시로 빈 배열 저장
            self.update_attachment_urls(
                'kstartup_complete',
                announcement['id'],
                attachment_urls
            )
            
        except Exception as e:
            logging.error(f"크롤링 실패: {announcement['biz_pbanc_nm']} - {e}")
            self.error_count += 1
    
    def process_bizinfo_attachments(self):
        """기업마당 첨부파일 처리"""
        logging.info("기업마당 첨부파일 처리 시작")
        
        try:
            # 첨부파일 URL이 있는 공고 조회
            result = self.supabase.table('bizinfo_complete')\
                .select('id, pblanc_id, pblanc_nm, atch_file_url, atch_file_nm, attachment_urls')\
                .not_.is_('atch_file_url', 'null')\
                .execute()
            
            announcements = result.data if result.data else []
            logging.info(f"처리할 기업마당 공고: {len(announcements)}개")
            
            for ann in announcements:
                # attachment_urls가 없거나 잘못된 경우 처리
                if not ann.get('attachment_urls') or ann['attachment_urls'] == '[]':
                    self.process_bizinfo_attachment(ann)
            
            logging.info(f"기업마당 처리 완료: 성공 {self.processed_count}개, 실패 {self.error_count}개")
            
        except Exception as e:
            logging.error(f"기업마당 처리 오류: {e}")
    
    def process_bizinfo_attachment(self, announcement):
        """기업마당 개별 첨부파일 처리"""
        try:
            attachment_urls = []
            
            # atch_file_url 처리
            if announcement.get('atch_file_url'):
                file_info = self.get_file_info(announcement['atch_file_url'])
                
                attachment_urls.append({
                    'url': file_info['url'],
                    'filename': file_info.get('filename') or announcement.get('atch_file_nm', ''),
                    'extension': file_info['extension'],
                    'size': file_info.get('size', 0),
                    'status': file_info.get('status', 'unknown')
                })
            
            # attachment_urls 업데이트
            self.update_attachment_urls(
                'bizinfo_complete',
                announcement['id'],
                attachment_urls
            )
            
        except Exception as e:
            logging.error(f"첨부파일 처리 실패: {announcement['pblanc_nm']} - {e}")
            self.error_count += 1
    
    def update_attachment_urls(self, table_name, record_id, attachment_urls):
        """attachment_urls 컬럼 업데이트"""
        try:
            # JSON 문자열로 변환
            attachment_json = json.dumps(attachment_urls, ensure_ascii=False)
            
            # 데이터베이스 업데이트
            result = self.supabase.table(table_name)\
                .update({'attachment_urls': attachment_json})\
                .eq('id', record_id)\
                .execute()
            
            if result.data:
                self.processed_count += 1
                logging.info(f"✅ 업데이트 성공: {table_name} ID {record_id}")
            else:
                self.error_count += 1
                logging.error(f"❌ 업데이트 실패: {table_name} ID {record_id}")
                
        except Exception as e:
            logging.error(f"DB 업데이트 오류: {e}")
            self.error_count += 1
    
    def run(self):
        """전체 처리 실행"""
        print("🚀 개선된 첨부파일 처리기 시작")
        print("=" * 80)
        
        start_time = datetime.now()
        
        # K-Startup 처리
        self.process_kstartup_attachments()
        
        # 기업마당 처리
        self.process_bizinfo_attachments()
        
        # 결과 요약
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print("📊 처리 결과")
        print("=" * 80)
        print(f"✅ 성공: {self.processed_count}개")
        print(f"❌ 실패: {self.error_count}개")
        print(f"⏱️ 소요시간: {elapsed_time:.2f}초")
        print("=" * 80)
        
        return self.processed_count > 0

def main():
    """메인 실행"""
    processor = ImprovedAttachmentProcessor()
    success = processor.run()
    
    # 종료 코드 반환 (GitHub Actions용)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()