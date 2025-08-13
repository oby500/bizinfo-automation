#!/usr/bin/env python3
"""
기업마당 첨부파일 크롤러 - 정확한 파일명 추출 버전
div.file_name과 title 속성에서 파일명을 직접 추출하여 정확한 파일 타입 감지
"""
import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse
from supabase import create_client
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re

# 전역 변수
lock = threading.Lock()
success_count = 0
error_count = 0
attachment_total = 0
skip_count = 0
type_fixed = 0

def extract_file_type_from_filename(filename):
    """파일명에서 확장자 추출"""
    if not filename:
        return 'UNKNOWN'
    
    filename_lower = filename.lower()
    
    if '.hwp' in filename_lower or '.hwpx' in filename_lower:
        return 'HWP'
    elif '.pdf' in filename_lower:
        return 'PDF'
    elif '.docx' in filename_lower:
        return 'DOCX'
    elif '.doc' in filename_lower:
        return 'DOC'
    elif '.xlsx' in filename_lower:
        return 'XLSX'
    elif '.xls' in filename_lower:
        return 'XLS'
    elif '.pptx' in filename_lower:
        return 'PPTX'
    elif '.ppt' in filename_lower:
        return 'PPT'
    elif '.zip' in filename_lower or '.rar' in filename_lower:
        return 'ZIP'
    elif '.jpg' in filename_lower or '.jpeg' in filename_lower:
        return 'JPG'
    elif '.png' in filename_lower:
        return 'PNG'
    elif '.gif' in filename_lower:
        return 'GIF'
    elif '.txt' in filename_lower:
        return 'TXT'
    elif '.rtf' in filename_lower:
        return 'RTF'
    else:
        return 'UNKNOWN'

def clean_filename(text):
    """파일명 정리"""
    if not text:
        return None
    
    # 불필요한 텍스트 제거
    text = text.strip()
    text = re.sub(r'다운로드$', '', text)
    text = re.sub(r'바로보기.*$', '', text)
    text = re.sub(r'새 창 열기$', '', text)
    text = re.sub(r'^첨부파일\s*', '', text)
    
    return text.strip()

def get_file_type_by_signature(url, session=None):
    """파일의 처음 몇 바이트를 읽어 실제 타입 판단 (폴백용)"""
    if session is None:
        session = requests.Session()
    
    try:
        # 파일의 처음 부분만 다운로드 (Range 헤더 사용)
        headers = {'Range': 'bytes=0-1024'}
        response = session.get(url, headers=headers, timeout=10, stream=True)
        
        # 전체 다운로드가 필요한 경우 (Range 미지원)
        if response.status_code == 200:
            content = response.content[:1024]
        elif response.status_code == 206:  # Partial Content
            content = response.content
        else:
            return 'UNKNOWN'
        
        # 파일 시그니처로 타입 판단
        if len(content) >= 4:
            # PDF
            if content[:4] == b'%PDF':
                return 'PDF'
            # ZIP
            elif content[:2] == b'PK':
                return 'ZIP'
            # HWP 5.0
            elif content[:4] == b'\xd0\xcf\x11\xe0' or content[:8] == b'HWP Document':
                return 'HWP'
            # HWP 3.0
            elif len(content) >= 32 and b'HWP' in content[:32]:
                return 'HWP'
        
        return 'UNKNOWN'
        
    except Exception as e:
        return 'UNKNOWN'

def process_item(data, idx, total, supabase):
    """개별 항목 처리"""
    global success_count, error_count, attachment_total, skip_count, type_fixed
    
    # 이미 처리된 데이터 체크
    current_summary = data.get('bsns_sumry', '')
    current_attachments = data.get('attachment_urls')
    
    # 첨부파일이 있고 UNKNOWN/HTML/DOC이 있는지 체크
    has_problem = False
    if current_attachments:
        for att in current_attachments:
            if isinstance(att, dict):
                file_type = att.get('type')
                # DOC도 문제로 간주 (대부분 HWP여야 함)
                if file_type in ['UNKNOWN', 'HTML', 'DOC']:
                    has_problem = True
                    break
    
    # 문제가 없고 요약도 충분한 경우 스킵
    if current_summary and len(current_summary) >= 150 and current_attachments and not has_problem:
        with lock:
            skip_count += 1
        print(f"[{idx}/{total}] ⏭️ 이미 처리 완료")
        return False
    
    # 세션 생성
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive'
    })
    
    try:
        pblanc_id = data['pblanc_id']
        pblanc_nm = data['pblanc_nm'][:50] + "..." if len(data['pblanc_nm']) > 50 else data['pblanc_nm']
        dtl_url = data.get('dtl_url')
        
        print(f"[{idx}/{total}] {pblanc_nm}")
        
        # 이미 첨부파일이 있는 경우 타입만 수정
        if current_attachments and has_problem:
            print(f"  [{idx}] 기존 첨부파일 타입 수정 중...")
            
            # 상세 페이지에서 실제 파일명 가져오기
            if dtl_url:
                try:
                    response = session.get(dtl_url, timeout=15)
                    response.encoding = 'utf-8'
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # div.file_name에서 파일명 추출
                    file_names_map = {}
                    file_names = soup.find_all('div', class_='file_name')
                    
                    for i, file_div in enumerate(file_names):
                        filename = file_div.get_text(strip=True)
                        filename = clean_filename(filename)
                        if filename:
                            file_names_map[i] = filename
                    
                    # title 속성에서도 파일명 추출
                    download_links = soup.find_all('a', href=lambda x: x and 'atchFileId' in x)
                    for link in download_links:
                        title = link.get('title', '')
                        if title and '첨부파일' in title:
                            filename = re.sub(r'^첨부파일\s*', '', title)
                            filename = re.sub(r'\s*다운로드$', '', filename)
                            if filename:
                                # atchFileId로 매핑
                                href = link.get('href', '')
                                if 'atchFileId=' in href:
                                    atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                                    file_sn = '0'
                                    if 'fileSn=' in href:
                                        file_sn = href.split('fileSn=')[1].split('&')[0]
                                    key = f"{atch_file_id}_{file_sn}"
                                    file_names_map[key] = filename
                    
                    # 기존 첨부파일 타입 수정
                    updated_attachments = []
                    fixed_count = 0
                    
                    for i, att in enumerate(current_attachments):
                        if isinstance(att, dict):
                            new_att = att.copy()
                            
                            # 문제가 있는 타입인 경우
                            if att.get('type') in ['UNKNOWN', 'HTML', 'DOC']:
                                # 파일명 찾기
                                actual_filename = None
                                
                                # 1. file_names_map에서 찾기
                                if i in file_names_map:
                                    actual_filename = file_names_map[i]
                                elif att.get('params'):
                                    key = f"{att['params'].get('atchFileId', '')}_{att['params'].get('fileSn', '0')}"
                                    if key in file_names_map:
                                        actual_filename = file_names_map[key]
                                
                                # 2. 파일명에서 타입 추출
                                if actual_filename:
                                    actual_type = extract_file_type_from_filename(actual_filename)
                                    new_att['display_filename'] = actual_filename
                                    new_att['original_filename'] = actual_filename
                                else:
                                    # 파일 시그니처로 확인 (폴백)
                                    actual_type = get_file_type_by_signature(att.get('url'), session)
                                
                                # 3. 여전히 UNKNOWN이면 HWP로 가정 (한국 공공기관)
                                if actual_type in ['UNKNOWN', 'HTML']:
                                    actual_type = 'HWP'
                                
                                if att.get('type') != actual_type:
                                    new_att['type'] = actual_type
                                    new_att['safe_filename'] = f"{pblanc_id}_{i+1:02d}.{actual_type.lower()}"
                                    fixed_count += 1
                                    print(f"    - {att.get('type')} → {actual_type} ({actual_filename if actual_filename else 'signature'})")
                            
                            updated_attachments.append(new_att)
                        else:
                            updated_attachments.append(att)
                    
                    if fixed_count > 0:
                        # DB 업데이트
                        result = supabase.table('bizinfo_complete').update({
                            'attachment_urls': updated_attachments
                        }).eq('id', data['id']).execute()
                        
                        with lock:
                            success_count += 1
                            type_fixed += fixed_count
                        
                        print(f"  [{idx}] ✅ 타입 수정: {fixed_count}개")
                        return True
                        
                except Exception as e:
                    print(f"  [{idx}] ⚠️ 페이지 파싱 실패: {str(e)[:30]}")
            
            print(f"  [{idx}] ⏭️ 수정할 타입 없음")
            return False
        
        # 새로 크롤링이 필요한 경우
        if not dtl_url:
            print(f"  [{idx}] ⚠️ 상세 URL 없음")
            return False
        
        # 재시도 로직
        max_retries = 3
        for retry in range(max_retries):
            try:
                response = session.get(dtl_url, timeout=15)
                response.encoding = 'utf-8'
                
                if response.status_code != 200:
                    if retry < max_retries - 1:
                        time.sleep(2)
                        continue
                    with lock:
                        error_count += 1
                    return False
                
                break
            except requests.exceptions.RequestException as e:
                if retry < max_retries - 1:
                    time.sleep(3)
                    continue
                print(f"  [{idx}] ❌ 연결 실패")
                with lock:
                    error_count += 1
                return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 첨부파일 정보 추출
        attachments = []
        unique_files = {}
        
        # 방법 1: file_name 클래스를 가진 div 찾기 (가장 정확)
        file_names = soup.find_all('div', class_='file_name')
        
        for file_div in file_names:
            filename = file_div.get_text(strip=True)
            filename = clean_filename(filename)
            
            if filename:
                # 같은 부모나 형제에서 다운로드 링크 찾기
                parent = file_div.parent
                if parent:
                    download_link = parent.find('a', href=lambda x: x and 'atchFileId' in x)
                    
                    if download_link:
                        href = download_link.get('href', '')
                        
                        # atchFileId 추출
                        atch_file_id = ''
                        file_sn = '0'
                        if 'atchFileId=' in href:
                            atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                        if 'fileSn=' in href:
                            file_sn = href.split('fileSn=')[1].split('&')[0]
                        
                        if atch_file_id:
                            direct_url = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                            
                            unique_key = f"{atch_file_id}_{file_sn}"
                            if unique_key not in unique_files:
                                file_type = extract_file_type_from_filename(filename)
                                
                                attachment = {
                                    'url': direct_url,
                                    'type': file_type,
                                    'safe_filename': f"{pblanc_id}_{len(attachments)+1:02d}.{file_type.lower()}",
                                    'display_filename': filename,
                                    'original_filename': filename,
                                    'text': filename,
                                    'params': {
                                        'atchFileId': atch_file_id,
                                        'fileSn': file_sn
                                    }
                                }
                                
                                unique_files[unique_key] = attachment
                                attachments.append(attachment)
        
        # 방법 2: title 속성이 있는 다운로드 링크 찾기 (백업)
        if not attachments:
            download_links = soup.find_all('a', href=lambda x: x and 'atchFileId' in x)
            
            for link in download_links:
                href = link.get('href', '')
                title = link.get('title', '')  # title 속성에 파일명이 있음
                text = link.get_text(strip=True)
                
                # 파일명 결정 (우선순위: title > text)
                filename = None
                if title and '첨부파일' in title:
                    # "첨부파일 파일명.hwp 다운로드" 형태
                    filename = re.sub(r'^첨부파일\s*', '', title)
                    filename = re.sub(r'\s*다운로드$', '', filename)
                elif title:
                    filename = title
                elif text and text != '다운로드':
                    filename = text
                
                if filename:
                    filename = clean_filename(filename)
                
                # atchFileId 추출
                atch_file_id = ''
                file_sn = '0'
                if 'atchFileId=' in href:
                    atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                if 'fileSn=' in href:
                    file_sn = href.split('fileSn=')[1].split('&')[0]
                
                if atch_file_id:
                    unique_key = f"{atch_file_id}_{file_sn}"
                    
                    if unique_key not in unique_files:
                        direct_url = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                        
                        file_type = extract_file_type_from_filename(filename) if filename else 'UNKNOWN'
                        
                        # UNKNOWN이면 HWP로 가정 (한국 공공기관)
                        if file_type == 'UNKNOWN':
                            file_type = 'HWP'
                        
                        attachment = {
                            'url': direct_url,
                            'type': file_type,
                            'safe_filename': f"{pblanc_id}_{len(attachments)+1:02d}.{file_type.lower()}",
                            'display_filename': filename or f"첨부파일_{len(attachments)+1}",
                            'original_filename': filename or text,
                            'text': text,
                            'params': {
                                'atchFileId': atch_file_id,
                                'fileSn': file_sn
                            }
                        }
                        
                        unique_files[unique_key] = attachment
                        attachments.append(attachment)
        
        # 요약 생성/개선
        if not current_summary or len(current_summary) < 150:
            summary_parts = []
            summary_parts.append(f"📋 {data['pblanc_nm']}")
            
            # 본문 내용 추출
            content_selectors = [
                'div.view_cont', 'div.content', 'div.board_view',
                'td.content', 'td.view_cont'
            ]
            
            for selector in content_selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    text = content_area.get_text(separator=' ', strip=True)
                    if text and len(text) > 50:
                        content_text = ' '.join(text.split())[:400]
                        summary_parts.append(f"📝 {content_text}...")
                        break
            
            if attachments:
                file_types = list(set([a['type'] for a in attachments]))
                summary_parts.append(f"📎 첨부: {', '.join(file_types)} ({len(attachments)}개)")
            
            new_summary = "\n".join(summary_parts)
        else:
            new_summary = current_summary
        
        # DB 업데이트
        update_data = {}
        
        if attachments and not current_attachments:
            update_data['attachment_urls'] = attachments
            with lock:
                attachment_total += len(attachments)
        
        if len(new_summary) > len(current_summary):
            update_data['bsns_sumry'] = new_summary
        
        if update_data:
            result = supabase.table('bizinfo_complete').update(
                update_data
            ).eq('id', data['id']).execute()
            
            with lock:
                success_count += 1
            
            if attachments:
                type_counts = {}
                for att in attachments:
                    file_type = att.get('type', 'UNKNOWN')
                    type_counts[file_type] = type_counts.get(file_type, 0) + 1
                type_info = ', '.join([f"{t}:{c}" for t, c in type_counts.items()])
                print(f"  [{idx}] ✅ 성공 (첨부: {len(attachments)}개 [{type_info}])")
            else:
                print(f"  [{idx}] ✅ 성공")
            return True
        else:
            with lock:
                skip_count += 1
            print(f"  [{idx}] ⏭️ 변경사항 없음")
            return False
        
    except Exception as e:
        with lock:
            error_count += 1
        print(f"  [{idx}] ❌ 오류: {str(e)[:50]}")
        return False
    finally:
        session.close()

def main():
    global success_count, error_count, attachment_total, skip_count, type_fixed
    
    print("=" * 60)
    print(" 기업마당 첨부파일 정확한 파일명 추출 v3")
    print(" - div.file_name에서 실제 파일명 추출")
    print(" - title 속성에서 파일명 확인")
    print(" - DOC/HTML → 정확한 타입으로 수정")
    print("=" * 60)
    
    # Supabase 연결
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ 환경변수가 설정되지 않았습니다.")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    # 처리 대상 조회
    print("1. 처리 대상 조회 중...")
    try:
        all_targets = []
        offset = 0
        limit = 1000
        
        while True:
            response = supabase.table('bizinfo_complete').select(
                'id', 'pblanc_id', 'pblanc_nm', 'dtl_url', 'bsns_sumry', 'attachment_urls'
            ).range(offset, offset + limit - 1).execute()
            
            if not response.data:
                break
                
            all_targets.extend(response.data)
            offset += limit
            
            if len(all_targets) >= 5000:
                break
        
        # 처리 대상 분류
        targets = []
        unknown_count = 0
        html_count = 0
        doc_count = 0
        already_done = 0
        
        for item in all_targets:
            bsns_sumry = item.get('bsns_sumry', '')
            attachment_urls = item.get('attachment_urls')
            
            # 첨부파일의 타입 체크
            needs_fix = False
            if attachment_urls:
                for att in attachment_urls:
                    if isinstance(att, dict):
                        file_type = att.get('type')
                        if file_type == 'UNKNOWN':
                            unknown_count += 1
                            needs_fix = True
                        elif file_type == 'HTML':
                            html_count += 1
                            needs_fix = True
                        elif file_type == 'DOC':
                            doc_count += 1
                            needs_fix = True
            
            # 수정이 필요하거나 요약이 부족한 경우
            if needs_fix or (not bsns_sumry or len(bsns_sumry) < 150) or (not attachment_urls):
                targets.append(item)
            else:
                already_done += 1
        
        print(f"✅ 전체: {len(all_targets)}개")
        print(f"⚠️ UNKNOWN 타입: {unknown_count}개")
        print(f"⚠️ HTML 타입: {html_count}개")
        print(f"⚠️ DOC 타입: {doc_count}개 (대부분 HWP일 가능성)")
        print(f"✅ 정상 처리: {already_done}개")
        print(f"🔧 처리 필요: {len(targets)}개")
        
    except Exception as e:
        print(f"❌ 데이터 조회 오류: {e}")
        sys.exit(1)
    
    if not targets:
        print("처리할 데이터가 없습니다.")
        return
    
    print("\n2. 파일명 추출 및 타입 수정 시작...")
    print(f"   - div.file_name에서 파일명 추출")
    print(f"   - title 속성에서 파일명 확인")
    print(f"   - 예상 시간: {len(targets) // 3}분")
    print("-" * 60)
    
    start_time = time.time()
    
    # 배치 처리
    batch_size = 50
    for batch_start in range(0, len(targets), batch_size):
        batch_end = min(batch_start + batch_size, len(targets))
        batch = targets[batch_start:batch_end]
        
        print(f"\n배치 처리: {batch_start+1}-{batch_end}/{len(targets)}")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i, data in enumerate(batch, batch_start + 1):
                future = executor.submit(process_item, data, i, len(targets), supabase)
                futures.append(future)
                time.sleep(0.3)  # 서버 부하 방지
            
            for future in as_completed(futures):
                future.result()
        
        if batch_end < len(targets):
            print(f"배치 완료. 3초 대기...")
            time.sleep(3)
    
    elapsed_time = time.time() - start_time
    
    # 결과 출력
    print("\n" + "=" * 60)
    print(" 파일명 추출 및 타입 수정 완료")
    print("=" * 60)
    print(f"✅ 성공: {success_count}개")
    print(f"🔧 타입 수정: {type_fixed}개 파일")
    print(f"⏭️ 스킵: {skip_count}개")
    print(f"❌ 실패: {error_count}개")
    print(f"📎 새 첨부파일: {attachment_total}개")
    print(f"⏱️ 소요 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
    if success_count > 0:
        print(f"📊 처리 속도: {success_count/elapsed_time:.1f}개/초")
    print("=" * 60)

if __name__ == "__main__":
    main()
