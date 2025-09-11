#!/usr/bin/env python3
"""
K-Startup 첨부파일 완전 수집
- 다운로드 URL
- 바로보기 URL  
- 실제 파일명 (HEAD 요청으로 확인)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import urllib.parse

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.k-startup.go.kr/'
})

def get_filename_from_headers(download_url):
    """HEAD 요청으로 실제 파일명 가져오기"""
    try:
        # HEAD 요청으로 헤더만 가져오기 (파일 다운로드하지 않음)
        response = session.head(download_url, allow_redirects=True, timeout=10)
        
        # Content-Disposition 헤더에서 파일명 추출
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if content_disposition:
            # filename*=UTF-8'' 형식 (RFC 5987)
            if "filename*=UTF-8''" in content_disposition:
                match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
                if match:
                    filename = urllib.parse.unquote(match.group(1))
                    return filename
            
            # filename="..." 형식
            if 'filename=' in content_disposition:
                match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                if match:
                    filename = match.group(1)
                    # 한글 깨짐 처리
                    try:
                        # ISO-8859-1로 인코딩된 경우
                        filename = filename.encode('iso-8859-1').decode('utf-8')
                    except:
                        try:
                            # EUC-KR로 인코딩된 경우
                            filename = filename.encode('iso-8859-1').decode('euc-kr')
                        except:
                            pass
                    return filename
        
        # Content-Disposition이 없으면 URL에서 추출
        url_path = urllib.parse.urlparse(download_url).path
        if url_path:
            filename = os.path.basename(url_path)
            if filename and not filename.isdigit():  # 숫자만 있는 파일명 제외
                return filename
        
        return None
        
    except Exception as e:
        print(f"    파일명 확인 실패: {e}")
        return None

def extract_attachments_complete(page_url):
    """K-Startup 첨부파일 완전 정보 추출"""
    all_attachments = []
    
    # pbancSn 추출 (KS_ 접두사 처리)
    if 'pbancSn=' in page_url:
        pbanc_sn_match = re.search(r'pbancSn=([^&]+)', page_url)
        if pbanc_sn_match:
            pbanc_sn = pbanc_sn_match.group(1)
            # KS_ 접두사 제거
            pbanc_sn = pbanc_sn.replace('KS_', '')
        else:
            return []
    else:
        return []
    
    try:
        # 페이지 접속
        response = session.get(page_url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 다운로드 링크 찾기
        download_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
        
        for link in download_links:
            href = link.get('href')
            if href:
                # 파일 ID 추출
                file_id = href.split('/')[-1]
                
                # 다운로드 URL
                if href.startswith('/'):
                    download_url = 'https://www.k-startup.go.kr' + href
                else:
                    download_url = href
                
                # 바로보기 URL (fileDownload → filePreview)
                preview_url = download_url.replace('fileDownload', 'filePreview')
                
                # 실제 파일명 가져오기 (HEAD 요청)
                print(f"  파일 ID {file_id} 정보 확인 중...")
                actual_filename = get_filename_from_headers(download_url)
                
                # 파일 타입 추측
                file_type = None
                if actual_filename:
                    ext = actual_filename.split('.')[-1].upper()
                    file_type = ext
                
                attachment = {
                    'file_id': file_id,
                    'download_url': download_url,
                    'preview_url': preview_url,
                    'actual_filename': actual_filename or f'파일_{file_id}',
                    'file_type': file_type,
                    'has_preview': file_type in ['PDF', 'HWP', 'DOC', 'DOCX'] if file_type else False
                }
                
                all_attachments.append(attachment)
                
                print(f"    ✓ {actual_filename or '파일명 미확인'}")
        
        # JavaScript onclick 방식도 확인
        onclick_links = soup.find_all('a', onclick=re.compile(r'fnPdfView'))
        for link in onclick_links:
            onclick = link.get('onclick', '')
            match = re.search(r"fnPdfView\('([^']+)'\)", onclick)
            if match:
                file_id = match.group(1)
                
                # 이미 추가된 파일인지 확인
                if not any(att['file_id'] == file_id for att in all_attachments):
                    download_url = f'https://www.k-startup.go.kr/afile/fileDownload/{file_id}'
                    preview_url = f'https://www.k-startup.go.kr/afile/filePreview/{file_id}'
                    
                    # 실제 파일명 가져오기
                    actual_filename = get_filename_from_headers(download_url)
                    
                    attachment = {
                        'file_id': file_id,
                        'download_url': download_url,
                        'preview_url': preview_url,
                        'actual_filename': actual_filename or f'파일_{file_id}',
                        'file_type': actual_filename.split('.')[-1].upper() if actual_filename else None,
                        'has_preview': True  # fnPdfView가 있으면 미리보기 가능
                    }
                    all_attachments.append(attachment)
        
    except Exception as e:
        print(f"  오류: {e}")
    
    return all_attachments

def process_announcement(announcement):
    """공고 하나 처리"""
    announcement_id = announcement.get('announcement_id')
    
    # KS_ 제거
    numeric_id = announcement_id.replace('KS_', '') if announcement_id else None
    if not numeric_id:
        return None
    
    # 상세 페이지 URL 생성
    detail_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={numeric_id}'
    
    print(f"\n처리 중: {announcement_id} - {announcement.get('biz_pbanc_nm', 'N/A')[:30]}...")
    
    # 첨부파일 정보 추출
    attachments = extract_attachments_complete(detail_url)
    
    if attachments:
        print(f"  → {len(attachments)}개 파일 발견")
        
        # DB 업데이트
        try:
            result = supabase.table('kstartup_complete').update({
                'attachment_urls': attachments,
                'attachment_processing_status': 'completed'
            }).eq('announcement_id', announcement_id).execute()
            
            return {
                'announcement_id': announcement_id,
                'attachments': attachments,
                'status': 'success'
            }
        except Exception as e:
            print(f"  DB 업데이트 실패: {e}")
            return None
    else:
        print(f"  → 첨부파일 없음")
        return None

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("K-Startup 첨부파일 완전 수집")
    print("=" * 60)
    
    # 처리할 공고 조회 (첨부파일 미처리 or NULL)
    try:
        result = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm')\
            .or_('attachment_processing_status.is.null,attachment_processing_status.neq.completed')\
            .limit(10)\
            .execute()
        
        if not result.data:
            print("처리할 공고가 없습니다.")
            return
        
        print(f"처리 대상: {len(result.data)}개 공고")
        
        # 병렬 처리
        success_count = 0
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(process_announcement, ann): ann 
                      for ann in result.data}
            
            for future in as_completed(futures):
                result = future.result()
                if result and result['status'] == 'success':
                    success_count += 1
        
        print("\n" + "=" * 60)
        print(f"완료: {success_count}개 공고 처리")
        print("=" * 60)
        
    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    main()