#!/usr/bin/env python3
"""
K-Startup 첨부파일 로컬 다운로드
GitHub Actions에서 사용하기 위한 로컬 저장 버전
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client
from dotenv import load_dotenv
from urllib.parse import urljoin, unquote
import time
import json

load_dotenv()

# Supabase 연결
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 다운로드 경로
DOWNLOAD_BASE = 'downloads'
KSTARTUP_DIR = os.path.join(DOWNLOAD_BASE, 'kstartup')

def ensure_download_dir():
    """다운로드 디렉토리 생성"""
    os.makedirs(KSTARTUP_DIR, exist_ok=True)
    print(f"다운로드 폴더: {KSTARTUP_DIR}")

def safe_filename(filename):
    """안전한 파일명 생성"""
    if not filename:
        return "attachment"
    
    # 특수문자 제거
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.replace('\x00', '')  # null 문자 제거
    
    # 길이 제한 (Windows 파일명 제한)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:190] + ext
    
    return filename

def download_file(url, filepath, max_retries=3):
    """파일 다운로드"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True, len(response.content) if hasattr(response, 'content') else os.path.getsize(filepath)
            else:
                print(f"    HTTP {response.status_code}: {url}")
                return False, 0
        except Exception as e:
            print(f"    시도 {attempt + 1} 실패: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    return False, 0

def parse_attachment_urls(attachment_urls_data):
    """첨부파일 URL 파싱"""
    if not attachment_urls_data:
        return []
    
    urls = []
    try:
        # 이미 리스트인 경우 (Supabase에서 JSON으로 자동 파싱됨)
        if isinstance(attachment_urls_data, list):
            for item in attachment_urls_data:
                if isinstance(item, dict) and 'url' in item:
                    original_filename = item.get('original_filename', item.get('display_filename', 'attachment'))
                    urls.append((item['url'], original_filename))
                elif isinstance(item, str):
                    urls.append((item, 'attachment'))
        # 문자열인 경우 JSON 파싱 시도
        elif isinstance(attachment_urls_data, str):
            if attachment_urls_data.startswith('['):
                parsed = json.loads(attachment_urls_data)
                for item in parsed:
                    if isinstance(item, dict) and 'url' in item:
                        original_filename = item.get('original_filename', item.get('display_filename', 'attachment'))
                        urls.append((item['url'], original_filename))
                    elif isinstance(item, str):
                        urls.append((item, 'attachment'))
            else:
                # 단순 문자열인 경우
                urls.append((attachment_urls_data, 'attachment'))
    except Exception as e:
        print(f"    URL 파싱 오류: {str(e)}")
        # 파싱 실패 시 빈 리스트 반환
        return []
    
    return urls

def process_kstartup_record(record):
    """K-Startup 레코드 처리"""
    announcement_id = record.get('announcement_id', '')
    title = record.get('biz_pbanc_nm', '')
    attachment_urls_data = record.get('attachment_urls', '')
    
    if not attachment_urls_data:
        return 0
    
    print(f"처리 중: {announcement_id} - {title[:50]}...")
    
    # 첨부파일 URL 파싱
    attachment_urls = parse_attachment_urls(attachment_urls_data)
    if not attachment_urls:
        print("    첨부파일 URL 없음")
        return 0
    
    downloaded_count = 0
    
    for i, (url, original_filename) in enumerate(attachment_urls):
        try:
            # 파일명 생성
            safe_title = safe_filename(title)[:50]  # 제목 50자로 제한
            file_ext = os.path.splitext(original_filename)[1] if '.' in original_filename else ''
            filename = f"KS_{announcement_id}_{safe_title}_{i+1}{file_ext}"
            filename = safe_filename(filename)
            
            filepath = os.path.join(KSTARTUP_DIR, filename)
            
            # 이미 다운로드된 파일 스킵
            if os.path.exists(filepath):
                print(f"    이미 존재: {filename}")
                continue
            
            # 파일 다운로드
            print(f"    다운로드: {filename}")
            success, file_size = download_file(url, filepath)
            
            if success:
                downloaded_count += 1
                print(f"    완료: {filename} ({file_size:,} bytes)")
            else:
                print(f"    실패: {filename}")
                
        except Exception as e:
            print(f"    오류: {str(e)}")
    
    return downloaded_count

def main():
    """메인 실행"""
    print("="*70)
    print("K-Startup 첨부파일 로컬 다운로드")
    print("="*70)
    
    # 다운로드 폴더 생성
    ensure_download_dir()
    
    try:
        # K-Startup 데이터 조회
        print("K-Startup 데이터 조회 중...")
        result = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm, attachment_urls, attachment_count')\
            .not_.is_('attachment_urls', 'null')\
            .not_.eq('attachment_urls', '')\
            .limit(100)\
            .execute()
        
        if not result.data:
            print("데이터가 없습니다")
            return
        
        print(f"처리 대상: {len(result.data)}개")
        
        # 각 레코드 처리
        total_downloaded = 0
        for record in result.data:
            downloaded = process_kstartup_record(record)
            total_downloaded += downloaded
            time.sleep(0.5)  # API 호출 간격
        
        print("="*70)
        print(f"K-Startup 다운로드 완료!")
        print(f"총 다운로드: {total_downloaded}개 파일")
        print(f"저장 위치: {KSTARTUP_DIR}")
        print("="*70)
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())