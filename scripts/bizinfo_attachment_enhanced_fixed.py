#!/usr/bin/env python3
"""
BizInfo 첨부파일 URL 수집 - 단순화 버전
- 첨부파일 URL만 수집
- 파일명과 타입 정보는 다운로드 시 HTTP 헤더에서 추출
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client
from dotenv import load_dotenv
from urllib.parse import urljoin, unquote, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

lock = threading.Lock()
progress = {
    'success': 0, 
    'error': 0, 
    'total': 0,
    'new_files': 0
}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.bizinfo.go.kr/'
})
# SSL 검증 비활성화 (테스트 목적)
session.verify = False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def extract_attachment_urls_simple(page_url, pblanc_id):
    """첨부파일 URL만 단순 추출"""
    attachment_urls = []
    
    try:
        response = session.get(page_url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # BizInfo 첨부파일 링크 찾기
        file_links = soup.find_all('a')
        
        for link in file_links:
            href = link.get('href', '')
            onclick = link.get('onclick', '')
            
            # 다운로드 링크 패턴 찾기
            download_url = None
            
            # 1. href에서 다운로드 링크
            if '/fileDown.do' in href or 'download' in href.lower():
                if href.startswith('http'):
                    download_url = href
                elif href.startswith('/'):
                    download_url = 'https://www.bizinfo.go.kr' + href
            
            # 2. onclick에서 다운로드 함수
            elif 'fileDown(' in onclick:
                # fileDown() 함수에서 파라미터 추출
                match = re.search(r"fileDown\(['\"]([^'\"]+)['\"](?:,['\"]([^'\"]*)['\"])*\)", onclick)
                if match:
                    file_param = match.group(1)
                    download_url = f'https://www.bizinfo.go.kr/web/file/fileDown.do?{file_param}'
            
            # 3. 기타 다운로드 관련 onclick
            elif 'javascript:' in onclick and ('down' in onclick.lower() or 'file' in onclick.lower()):
                # 더 복잡한 패턴은 필요시 추가
                pass
            
            if download_url:
                # URL만 저장 - 파일명과 타입 정보 없음
                attachment_urls.append({'url': download_url})
        
        return attachment_urls
        
    except Exception as e:
        print(f"URL 추출 실패 {page_url}: {str(e)}")
        return []

def process_record(record):
    """레코드 처리 - URL만 수집"""
    try:
        pblanc_id = record['pblanc_id']
        title = record.get('pblanc_nm', '')
        page_url = record.get('detail_url', '')
        
        if not page_url:
            # detail_url이 없으면 pblanc_id로 구성
            page_url = f'https://www.bizinfo.go.kr/web/lay1/biz/S1T122C128/AS/S1T122C128AS01/S1T122C128AS01_02_View.do?pblanc_id={pblanc_id}'
        
        print(f"처리 중: {pblanc_id} - {title[:50]}...")
        
        # 첨부파일 URL만 추출
        attachments = extract_attachment_urls_simple(page_url, pblanc_id)
        
        if attachments:
            # 데이터베이스 업데이트 - URL만 저장
            result = supabase.table('bizinfo_complete')\
                .update({
                    'attachment_urls': attachments
                })\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                    progress['new_files'] += len(attachments)
                print(f"  ✅ {len(attachments)}개 URL 수집 완료")
                return True
        else:
            # 첨부파일이 없는 경우도 업데이트
            result = supabase.table('bizinfo_complete')\
                .update({
                    'attachment_urls': []
                })\
                .eq('pblanc_id', pblanc_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['success'] += 1
                print(f"  📝 첨부파일 없음")
                return True
        
        with lock:
            progress['error'] += 1
        return False
        
    except Exception as e:
        print(f"  ❌ 오류: {str(e)}")
        with lock:
            progress['error'] += 1
        return False

def main():
    """메인 실행"""
    print("="*70)
    print("📎 BizInfo 첨부파일 URL 수집 (단순화 버전)")
    print("="*70)
    
    # 처리 제한 확인 (환경변수로 받음)
    processing_limit = int(os.environ.get('PROCESSING_LIMIT', '0'))
    
    # 처리 대상 조회 - 첨부파일이 없거나 재처리가 필요한 것들
    if processing_limit > 0:
        # Daily 모드: 최근 N개만
        all_records = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, detail_url, attachment_urls')\
            .order('created_at', desc=True)\
            .limit(processing_limit * 2)\
            .execute()
        print(f"📌 Daily 모드: 최근 {processing_limit*2}개 중에서 처리 필요한 것만 선택")
    else:
        # Full 모드: 전체
        all_records = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, detail_url, attachment_urls')\
            .execute()
        print("📌 Full 모드: 전체 데이터 처리")
    
    needs_processing = []
    
    for record in all_records.data:
        # 첨부파일 정보가 없는 경우 재처리
        if not record.get('attachment_urls'):
            needs_processing.append(record)
    
    # Daily 모드에서는 최대 N개만 처리
    if processing_limit > 0 and len(needs_processing) > processing_limit:
        needs_processing = needs_processing[:processing_limit]
        print(f"📌 Daily 모드 제한: 최대 {processing_limit}개만 처리")
    
    progress['total'] = len(needs_processing)
    
    print(f"✅ 검토 대상: {len(all_records.data)}개")
    print(f"📎 처리 필요: {progress['total']}개")
    
    if progress['total'] == 0:
        print("🎉 모든 레코드가 이미 처리되었습니다!")
        return
    
    print(f"🔥 {progress['total']}개 처리 시작 (20 workers)...\n")
    
    # 병렬 처리
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_record, record): record for record in needs_processing}
        
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                if i % 50 == 0:
                    print(f"진행: {i}/{progress['total']} | 성공: {progress['success']} | URL: {progress['new_files']}개")
            except:
                pass
    
    # 결과 출력
    print("\n" + "="*70)
    print("📊 처리 완료")
    print("="*70)
    print(f"✅ 성공: {progress['success']}/{progress['total']}")
    print(f"📎 수집된 URL: {progress['new_files']}개")
    print("\n📝 변경사항:")
    print("  - 파일명과 타입 정보 제거")
    print("  - 순수 다운로드 URL만 저장")
    print("  - 파일명은 다운로드 시 HTTP 헤더에서 추출")
    print("="*70)

if __name__ == "__main__":
    main()