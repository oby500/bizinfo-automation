#!/usr/bin/env python3
"""
K-Startup + BizInfo 전체 첨부파일 재수집 - 파일 타입 정확히 감지
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json
import time

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

lock = threading.Lock()
progress = {
    'ks_total': 0,
    'ks_processed': 0,
    'ks_success': 0,
    'ks_error': 0,
    'ks_skipped': 0,
    'bi_total': 0,
    'bi_processed': 0,
    'bi_success': 0,
    'bi_error': 0,
    'bi_skipped': 0,
    'hwp_found': 0,
    'pdf_found': 0,
    'image_found': 0,
    'file_type_fixed': 0
}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
})

def detect_file_type_by_signature(url, filename=''):
    """파일 시그니처로 실제 파일 타입 감지"""
    try:
        # Referer 설정
        if 'k-startup.go.kr' in url:
            session.headers['Referer'] = 'https://www.k-startup.go.kr/'
        elif 'bizinfo.go.kr' in url:
            session.headers['Referer'] = 'https://www.bizinfo.go.kr/'
        
        # 파일의 처음 부분만 다운로드
        response = session.get(url, stream=True, timeout=10)
        
        # 처음 1KB 읽기
        chunk = response.raw.read(1024)
        
        # 파일 시그니처 확인
        if chunk[:4] == b'%PDF':
            file_type, file_ext = 'PDF', 'pdf'
        elif chunk[:8] == b'\x89PNG\r\n\x1a\n':
            file_type, file_ext = 'IMAGE', 'png'
        elif chunk[:2] == b'\xff\xd8':
            file_type, file_ext = 'IMAGE', 'jpg'
        elif chunk[:6] == b'GIF87a' or chunk[:6] == b'GIF89a':
            file_type, file_ext = 'IMAGE', 'gif'
        elif b'HWP Document File' in chunk[:100]:
            file_type, file_ext = 'HWP', 'hwp'
        elif chunk[:2] == b'PK':
            # ZIP 또는 Office 문서
            if b'word/' in chunk:
                file_type, file_ext = 'WORD', 'docx'
            elif b'xl/' in chunk:
                file_type, file_ext = 'EXCEL', 'xlsx'
            elif b'ppt/' in chunk:
                file_type, file_ext = 'PPT', 'pptx'
            elif filename and filename.lower().endswith('.hwpx'):
                file_type, file_ext = 'HWPX', 'hwpx'
            else:
                file_type, file_ext = 'ZIP', 'zip'
        else:
            # Content-Disposition에서 파일명 추출
            content_disp = response.headers.get('Content-Disposition', '')
            if 'filename=' in content_disp:
                filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disp)
                if filename_match:
                    extracted_name = filename_match.group(1).strip('"\'')
                    if not filename:
                        filename = extracted_name
            
            # 파일명으로 추측
            if filename:
                ext = filename.lower().split('.')[-1] if '.' in filename else ''
                if ext == 'hwp':
                    file_type, file_ext = 'HWP', 'hwp'
                elif ext == 'hwpx':
                    file_type, file_ext = 'HWPX', 'hwpx'
                elif ext == 'pdf':
                    file_type, file_ext = 'PDF', 'pdf'
                elif ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
                    file_type, file_ext = 'IMAGE', ext
                elif ext in ['zip', 'rar', '7z']:
                    file_type, file_ext = 'ZIP', ext
                elif ext in ['xls', 'xlsx']:
                    file_type, file_ext = 'EXCEL', ext
                elif ext in ['doc', 'docx']:
                    file_type, file_ext = 'WORD', ext
                elif ext in ['ppt', 'pptx']:
                    file_type, file_ext = 'PPT', ext
                else:
                    file_type, file_ext = 'FILE', ext
            else:
                file_type, file_ext = 'FILE', ''
        
        response.close()
        return file_type, file_ext
        
    except Exception as e:
        # 폴백: 파일명으로 추측
        if filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            file_type = 'HWP' if ext == 'hwp' else \
                       'HWPX' if ext == 'hwpx' else \
                       'PDF' if ext == 'pdf' else \
                       'IMAGE' if ext in ['png', 'jpg', 'jpeg', 'gif'] else \
                       'ZIP' if ext in ['zip', 'rar', '7z'] else \
                       'EXCEL' if ext in ['xls', 'xlsx'] else \
                       'WORD' if ext in ['doc', 'docx'] else \
                       'PPT' if ext in ['ppt', 'pptx'] else \
                       'FILE'
            return file_type, ext
        
        return 'FILE', ''

def extract_kstartup_attachments(page_url, announcement_id):
    """K-Startup 첨부파일 추출"""
    all_attachments = []
    
    # pbanc_sn 추출
    if 'pbancSn=' in page_url:
        pbanc_sn = re.search(r'pbancSn=(\d+)', page_url).group(1)
    else:
        pbanc_sn = announcement_id.replace('KS_', '') if announcement_id.startswith('KS_') else announcement_id
    
    # ongoing과 deadline 모두 시도
    urls_to_try = [
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}',
        f'https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?schM=view&pbancSn={pbanc_sn}',
    ]
    
    for try_url in urls_to_try:
        try:
            session.headers['Referer'] = 'https://www.k-startup.go.kr/'
            response = session.get(try_url, timeout=15)
            if response.status_code != 200:
                continue
                
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            attachments = []
            
            # /afile/fileDownload/ 패턴 찾기
            download_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/'))
            
            for link in download_links:
                href = link.get('href', '')
                text = link.get_text(strip=True) or ''
                
                # 전체 URL 생성
                full_url = urljoin(try_url, href)
                
                # 파일명 추출
                filename = text
                if not filename or filename == '다운로드':
                    file_id_match = re.search(r'/afile/fileDownload/([^/\?]+)', href)
                    if file_id_match:
                        file_id = file_id_match.group(1)
                        filename = f"첨부파일_{file_id}"
                    else:
                        filename = f"첨부파일_{len(attachments)+1}"
                
                # 파일 시그니처로 타입 감지
                file_type, file_ext = detect_file_type_by_signature(full_url, filename)
                
                attachment = {
                    'url': full_url,
                    'text': filename,
                    'type': file_type,
                    'params': {},
                    'safe_filename': f"KS_{announcement_id}_{len(attachments)+1:02d}",
                    'display_filename': filename,
                    'original_filename': filename,
                    'file_extension': file_ext
                }
                
                attachments.append(attachment)
            
            if attachments:
                all_attachments.extend(attachments)
                
        except Exception as e:
            continue
    
    # 중복 제거
    unique_attachments = []
    seen_urls = set()
    for att in all_attachments:
        if att['url'] not in seen_urls:
            seen_urls.add(att['url'])
            unique_attachments.append(att)
    
    return unique_attachments

def extract_bizinfo_attachments(page_url, announcement_id):
    """BizInfo 첨부파일 추출"""
    all_attachments = []
    
    try:
        session.headers['Referer'] = 'https://www.bizinfo.go.kr/'
        response = session.get(page_url, timeout=15)
        if response.status_code != 200:
            return []
            
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        attachments = []
        
        # 다양한 패턴의 첨부파일 링크 찾기
        # 1. onclick에 javascript:fn_egov_downFile 패턴
        download_elements = soup.find_all(attrs={'onclick': re.compile(r'fn_egov_downFile')})
        for elem in download_elements:
            onclick = elem.get('onclick', '')
            # fn_egov_downFile('param1', 'param2') 패턴에서 파라미터 추출
            match = re.search(r"fn_egov_downFile\('([^']+)',\s*'([^']+)'\)", onclick)
            if match:
                param1, param2 = match.groups()
                # BizInfo 다운로드 URL 생성
                full_url = f'https://www.bizinfo.go.kr/cmm/fms/FileDown.do?atchFileId={param1}&fileSn={param2}'
                filename = elem.get_text(strip=True) or f'첨부파일_{len(attachments)+1}'
                
                # 파일 시그니처로 타입 감지
                file_type, file_ext = detect_file_type_by_signature(full_url, filename)
                
                attachment = {
                    'url': full_url,
                    'text': filename,
                    'type': file_type,
                    'params': {'atchFileId': param1, 'fileSn': param2},
                    'safe_filename': f"{announcement_id}_{len(attachments)+1:02d}",
                    'display_filename': filename,
                    'original_filename': filename,
                    'file_extension': file_ext
                }
                
                attachments.append(attachment)
        
        # 2. href에 FileDown.do 패턴
        download_links = soup.find_all('a', href=re.compile(r'FileDown\.do'))
        for link in download_links:
            href = link.get('href', '')
            full_url = urljoin(page_url, href)
            filename = link.get_text(strip=True) or f'첨부파일_{len(attachments)+1}'
            
            # 파일 시그니처로 타입 감지
            file_type, file_ext = detect_file_type_by_signature(full_url, filename)
            
            attachment = {
                'url': full_url,
                'text': filename,
                'type': file_type,
                'params': {},
                'safe_filename': f"{announcement_id}_{len(attachments)+1:02d}",
                'display_filename': filename,
                'original_filename': filename,
                'file_extension': file_ext
            }
            
            # 중복 체크
            if not any(att['url'] == attachment['url'] for att in attachments):
                attachments.append(attachment)
        
        all_attachments.extend(attachments)
        
    except Exception as e:
        pass
    
    # 중복 제거
    unique_attachments = []
    seen_urls = set()
    for att in all_attachments:
        if att['url'] not in seen_urls:
            seen_urls.add(att['url'])
            unique_attachments.append(att)
    
    return unique_attachments

def process_kstartup_record(record):
    """K-Startup 레코드 처리"""
    announcement_id = record['announcement_id']
    detl_pg_url = record.get('detl_pg_url')
    current_attachments = record.get('attachment_urls')
    
    # 이미 정확한 타입이 있는지 확인 (FILE 타입이 없으면 스킵)
    needs_update = False
    if current_attachments:
        try:
            if isinstance(current_attachments, str):
                attachments_list = json.loads(current_attachments)
            else:
                attachments_list = current_attachments
            
            # FILE 타입이 있으면 재수집 필요
            for att in attachments_list:
                if att.get('type') == 'FILE':
                    needs_update = True
                    break
        except:
            needs_update = True
    else:
        needs_update = True
    
    if not needs_update:
        with lock:
            progress['ks_skipped'] += 1
        return 'skipped'
    
    if not detl_pg_url:
        pbanc_sn = announcement_id.replace('KS_', '') if announcement_id.startswith('KS_') else announcement_id
        detl_pg_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}'
    
    try:
        attachments = extract_kstartup_attachments(detl_pg_url, announcement_id)
        
        if attachments:
            # 타입별 카운트
            for att in attachments:
                file_type = att.get('type', 'FILE')
                with lock:
                    if file_type in ['HWP', 'HWPX']:
                        progress['hwp_found'] += 1
                    elif file_type == 'PDF':
                        progress['pdf_found'] += 1
                    elif file_type == 'IMAGE':
                        progress['image_found'] += 1
            
            update_data = {
                'attachment_urls': attachments,
                'attachment_count': len(attachments)
            }
            
            result = supabase.table('kstartup_complete')\
                .update(update_data)\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['ks_success'] += 1
                    progress['file_type_fixed'] += 1
                return 'success'
        else:
            # 첨부파일 없음으로 업데이트
            update_data = {
                'attachment_urls': [],
                'attachment_count': 0
            }
            
            result = supabase.table('kstartup_complete')\
                .update(update_data)\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            with lock:
                progress['ks_success'] += 1
            return 'no_attachments'
        
    except Exception as e:
        with lock:
            progress['ks_error'] += 1
        return 'error'

def process_bizinfo_record(record):
    """BizInfo 레코드 처리"""
    announcement_id = record.get('announcement_id') or record.get('pblanc_id')
    detail_url = record.get('detail_url') or record.get('dtl_url')
    current_attachments = record.get('attachment_urls')
    
    # 이미 정확한 타입이 있는지 확인
    needs_update = False
    if current_attachments:
        try:
            if isinstance(current_attachments, str):
                attachments_list = json.loads(current_attachments)
            else:
                attachments_list = current_attachments
            
            # FILE 타입이 있으면 재수집 필요
            for att in attachments_list:
                if att.get('type') == 'FILE':
                    needs_update = True
                    break
        except:
            needs_update = True
    else:
        # 첨부파일 정보가 없으면 재수집
        needs_update = True
    
    if not needs_update:
        with lock:
            progress['bi_skipped'] += 1
        return 'skipped'
    
    if not detail_url:
        with lock:
            progress['bi_error'] += 1
        return 'no_url'
    
    try:
        attachments = extract_bizinfo_attachments(detail_url, announcement_id)
        
        if attachments:
            # 타입별 카운트
            for att in attachments:
                file_type = att.get('type', 'FILE')
                with lock:
                    if file_type in ['HWP', 'HWPX']:
                        progress['hwp_found'] += 1
                    elif file_type == 'PDF':
                        progress['pdf_found'] += 1
                    elif file_type == 'IMAGE':
                        progress['image_found'] += 1
            
            update_data = {
                'attachment_urls': attachments
            }
            
            result = supabase.table('bizinfo_complete')\
                .update(update_data)\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            if result.data:
                with lock:
                    progress['bi_success'] += 1
                    progress['file_type_fixed'] += 1
                return 'success'
        
        with lock:
            progress['bi_success'] += 1
        return 'no_attachments'
        
    except Exception as e:
        with lock:
            progress['bi_error'] += 1
        return 'error'

def show_progress():
    """진행상황 표시"""
    while (progress['ks_processed'] < progress['ks_total']) or (progress['bi_processed'] < progress['bi_total']):
        with lock:
            ks_processed = progress['ks_processed']
            ks_total = progress['ks_total']
            bi_processed = progress['bi_processed']
            bi_total = progress['bi_total']
            total_processed = ks_processed + bi_processed
            total = ks_total + bi_total
        
        if total > 0:
            percentage = (total_processed / total) * 100
            print(f"\r⏳ 진행: {total_processed}/{total} ({percentage:.1f}%) | "
                  f"KS: {ks_processed}/{ks_total} | BI: {bi_processed}/{bi_total} | "
                  f"📝 HWP: {progress['hwp_found']} | 📄 PDF: {progress['pdf_found']} | "
                  f"🖼️ IMG: {progress['image_found']}", end='')
        
        time.sleep(1)

def main():
    """메인 실행"""
    print("="*70)
    print("🔄 K-Startup + BizInfo 전체 첨부파일 재수집")
    print("="*70)
    
    # K-Startup 데이터 조회 (전체)
    print("\n📊 K-Startup 데이터 조회 중...")
    ks_records = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, detl_pg_url, attachment_urls, attachment_count')\
        .limit(10000)\
        .execute()
    
    progress['ks_total'] = len(ks_records.data)
    print(f"✅ K-Startup: {progress['ks_total']}개 공고")
    
    # BizInfo 데이터 조회 (전체)
    print("\n📊 BizInfo 데이터 조회 중...")
    bi_records = supabase.table('bizinfo_complete')\
        .select('announcement_id, pblanc_id, pblanc_nm, detail_url, dtl_url, attachment_urls')\
        .limit(10000)\
        .execute()
    
    progress['bi_total'] = len(bi_records.data)
    print(f"✅ BizInfo: {progress['bi_total']}개 공고")
    
    total_records = progress['ks_total'] + progress['bi_total']
    print(f"\n📊 전체: {total_records}개 공고")
    print(f"🚀 병렬 처리 시작 (30개 동시 실행)")
    print("-" * 70)
    
    # 진행상황 표시 스레드
    progress_thread = threading.Thread(target=show_progress)
    progress_thread.daemon = True
    progress_thread.start()
    
    # ThreadPoolExecutor로 병렬 처리
    with ThreadPoolExecutor(max_workers=30) as executor:
        # K-Startup 처리
        ks_futures = {executor.submit(process_kstartup_record, record): ('ks', record) 
                      for record in ks_records.data}
        
        # BizInfo 처리
        bi_futures = {executor.submit(process_bizinfo_record, record): ('bi', record) 
                      for record in bi_records.data}
        
        # 모든 futures 합치기
        all_futures = {**ks_futures, **bi_futures}
        
        for future in as_completed(all_futures):
            source, _ = all_futures[future]
            with lock:
                if source == 'ks':
                    progress['ks_processed'] += 1
                else:
                    progress['bi_processed'] += 1
            try:
                future.result()
            except Exception as e:
                pass
    
    # 최종 결과
    print("\n\n" + "="*70)
    print("📊 처리 결과")
    print("="*70)
    
    print("\n🎯 K-Startup:")
    print(f"   처리: {progress['ks_processed']}/{progress['ks_total']}")
    print(f"   성공: {progress['ks_success']}")
    print(f"   스킵: {progress['ks_skipped']}")
    print(f"   오류: {progress['ks_error']}")
    
    print("\n🏢 BizInfo:")
    print(f"   처리: {progress['bi_processed']}/{progress['bi_total']}")
    print(f"   성공: {progress['bi_success']}")
    print(f"   스킵: {progress['bi_skipped']}")
    print(f"   오류: {progress['bi_error']}")
    
    print(f"\n📁 파일 타입 통계:")
    print(f"   📝 HWP/HWPX: {progress['hwp_found']}개")
    print(f"   📄 PDF: {progress['pdf_found']}개")
    print(f"   🖼️  IMAGE: {progress['image_found']}개")
    print(f"\n🔧 FILE → 정확한 타입으로 수정됨: {progress['file_type_fixed']}개")
    
    if progress['hwp_found'] > 0:
        print(f"\n🎯 {progress['hwp_found']}개의 HWP 파일이 PDF 변환 대상입니다.")

if __name__ == "__main__":
    main()