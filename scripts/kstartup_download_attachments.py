#!/usr/bin/env python3
"""
K-Startup 첨부파일 다운로드
- 수집된 URL에서 실제 파일 다운로드
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from pathlib import Path
from supabase import create_client
from dotenv import load_dotenv
import time
from urllib.parse import unquote, urlparse
import re

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 다운로드 경로
DOWNLOAD_BASE = Path("E:/gov-support-automation/downloads/kstartup")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.k-startup.go.kr/'
})

def sanitize_filename(filename):
    """파일명 정리"""
    # 특수문자 제거
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 공백 정리
    filename = ' '.join(filename.split())
    # 길이 제한
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    return name + ext

def download_file(url, save_path):
    """파일 다운로드"""
    try:
        response = session.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Content-Disposition에서 파일명 추출
        filename = None
        if 'content-disposition' in response.headers:
            cd = response.headers['content-disposition']
            if 'filename=' in cd:
                filename = cd.split('filename=')[-1].strip('"\'')
                filename = unquote(filename)
        
        # URL에서 파일명 추출
        if not filename:
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename or filename == 'fileDownload':
                filename = f"attachment_{int(time.time())}.bin"
        
        # 파일명 정리
        filename = sanitize_filename(filename)
        
        # 전체 경로
        file_path = save_path / filename
        
        # 이미 존재하면 스킵
        if file_path.exists():
            print(f"    [SKIP] 이미 존재: {filename}")
            return file_path, "skipped"
        
        # 다운로드
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = file_path.stat().st_size
        print(f"    [OK] {filename} ({file_size:,} bytes)")
        return file_path, "success"
        
    except Exception as e:
        print(f"    [ERROR] {str(e)}")
        return None, str(e)

def process_announcement(record):
    """공고별 첨부파일 다운로드"""
    announcement_id = record['announcement_id']
    attachment_urls = record.get('attachment_urls', [])
    
    if not attachment_urls:
        return
    
    print(f"\n[{announcement_id}] 처리 중...")
    
    # 다운로드 폴더 생성
    save_path = DOWNLOAD_BASE / announcement_id
    save_path.mkdir(parents=True, exist_ok=True)
    
    download_results = []
    success_count = 0
    
    for i, url_info in enumerate(attachment_urls, 1):
        if isinstance(url_info, dict):
            url = url_info.get('url')
        else:
            url = url_info
        
        if not url:
            continue
        
        print(f"  [{i}/{len(attachment_urls)}] 다운로드 중...")
        file_path, status = download_file(url, save_path)
        
        if status == "success":
            success_count += 1
            download_results.append({
                'url': url,
                'filename': file_path.name if file_path else None,
                'size': file_path.stat().st_size if file_path else 0,
                'status': 'success'
            })
        elif status == "skipped":
            success_count += 1
            download_results.append({
                'url': url,
                'filename': file_path.name if file_path else None,
                'status': 'skipped'
            })
        else:
            download_results.append({
                'url': url,
                'status': 'failed',
                'error': status
            })
    
    # 결과 저장
    if download_results:
        try:
            supabase.table('kstartup_complete').update({
                'download_results': download_results,
                'download_count': success_count,
                'download_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }).eq('announcement_id', announcement_id).execute()
        except:
            pass  # 테이블 구조가 다를 수 있음
    
    print(f"  완료: {success_count}/{len(attachment_urls)} 파일")

def main():
    print("=" * 60)
    print("K-Startup 첨부파일 다운로드")
    print("=" * 60)
    
    # 다운로드할 레코드 조회
    print("\n다운로드할 공고 조회 중...")
    
    # attachment_urls가 있고 아직 다운로드하지 않은 레코드
    result = supabase.table('kstartup_complete')\
        .select('announcement_id, attachment_urls')\
        .neq('attachment_urls', [])\
        .limit(20)\
        .execute()
    
    records = result.data if result.data else []
    
    if not records:
        print("다운로드할 첨부파일이 없습니다.")
        return
    
    print(f"총 {len(records)}개 공고의 첨부파일 다운로드 시작\n")
    
    # 다운로드 실행
    total_success = 0
    total_files = 0
    
    for record in records:
        process_announcement(record)
        time.sleep(1)  # 서버 부하 방지
    
    print("\n" + "=" * 60)
    print("다운로드 완료!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n작업이 중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()