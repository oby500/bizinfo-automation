#!/usr/bin/env python3
"""
기업마당 첨부파일 크롤러 - 파일 시그니처로 실제 타입 감지
파일의 처음 몇 바이트를 읽어 실제 파일 타입 판단
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

def get_file_type_by_signature(url, session=None):
    """파일의 처음 몇 바이트를 읽어 실제 타입 판단"""
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
            # MS Office 2007+ (DOCX, XLSX, PPTX) - ZIP 기반
            elif content[:4] == b'PK\x03\x04':
                # 더 자세한 판단을 위해 더 많이 읽기
                full_response = session.get(url, timeout=15)
                full_content = full_response.content
                
                # Content-Type 힌트 확인
                content_type = full_response.headers.get('Content-Type', '').lower()
                
                # 파일 내용으로 판단
                if b'word/' in full_content[:2000]:
                    return 'DOCX'
                elif b'xl/' in full_content[:2000]:
                    return 'XLSX'
                elif b'ppt/' in full_content[:2000]:
                    return 'PPTX'
                else:
                    return 'ZIP'
            # MS Office 97-2003
            elif content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                return 'DOC'  # 또는 XLS, PPT - 구분 어려움
            # HWP 5.0
            elif content[:4] == b'\xd0\xcf\x11\xe0' or content[:8] == b'HWP Document':
                return 'HWP'
            # HWP 3.0
            elif len(content) >= 32 and b'HWP' in content[:32]:
                return 'HWP'
            # JPEG
            elif content[:3] == b'\xff\xd8\xff':
                return 'JPG'
            # PNG
            elif content[:8] == b'\x89PNG\r\n\x1a\n':
                return 'PNG'
            # GIF
            elif content[:6] in [b'GIF87a', b'GIF89a']:
                return 'GIF'
            # BMP
            elif content[:2] == b'BM':
                return 'BMP'
            # RTF
            elif content[:5] == b'{\\rtf':
                return 'RTF'
            # Plain Text (UTF-8 BOM)
            elif content[:3] == b'\xef\xbb\xbf':
                return 'TXT'
            # HTML
            elif b'<html' in content[:100].lower() or b'<!doctype html' in content[:100].lower():
                return 'HTML'
        
        # 파일명에서 확장자 확인 (폴백)
        if 'Content-Disposition' in response.headers:
            disposition = response.headers['Content-Disposition']
            if 'filename=' in disposition:
                filename = disposition.split('filename=')[-1].strip('"').strip("'")
                return guess_type_from_filename(filename)
        
        return 'UNKNOWN'
        
    except Exception as e:
        print(f"    파일 시그니처 확인 실패: {str(e)[:30]}")
        return 'UNKNOWN'

def guess_type_from_filename(filename):
    """파일명에서 확장자 추출"""
    if not filename:
        return 'UNKNOWN'
    
    filename_lower = filename.lower()
    
    if filename_lower.endswith('.hwp') or filename_lower.endswith('.hwpx'):
        return 'HWP'
    elif filename_lower.endswith('.pdf'):
        return 'PDF'
    elif filename_lower.endswith('.docx'):
        return 'DOCX'
    elif filename_lower.endswith('.doc'):
        return 'DOC'
    elif filename_lower.endswith('.xlsx'):
        return 'XLSX'
    elif filename_lower.endswith('.xls'):
        return 'XLS'
    elif filename_lower.endswith('.pptx'):
        return 'PPTX'
    elif filename_lower.endswith('.ppt'):
        return 'PPT'
    elif filename_lower.endswith('.zip'):
        return 'ZIP'
    elif filename_lower.endswith('.jpg') or filename_lower.endswith('.jpeg'):
        return 'JPG'
    elif filename_lower.endswith('.png'):
        return 'PNG'
    elif filename_lower.endswith('.gif'):
        return 'GIF'
    elif filename_lower.endswith('.txt'):
        return 'TXT'
    elif filename_lower.endswith('.rtf'):
        return 'RTF'
    else:
        return 'UNKNOWN'

def extract_filename_from_text(text):
    """링크 텍스트에서 실제 파일명 추출"""
    if not text:
        return None
    
    # 파일명 패턴 찾기
    patterns = [
        r'([가-힣a-zA-Z0-9\s\-\_\.]+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))',
        r'(\S+\.(?:hwp|hwpx|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|jpeg|png|gif|txt|rtf))'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def extract_file_type_from_text(text):
    """링크 텍스트에서 파일 타입 힌트 추출"""
    text_lower = text.lower()
    
    # 명확한 확장자가 텍스트에 있는 경우
    filename = extract_filename_from_text(text)
    if filename:
        return guess_type_from_filename(filename)
    
    # 텍스트 힌트로 추측
    if '한글' in text_lower or 'hwp' in text_lower:
        return 'HWP'
    elif 'pdf' in text_lower:
        return 'PDF'
    elif 'word' in text_lower or 'doc' in text_lower or '워드' in text_lower:
        return 'DOCX'
    elif 'excel' in text_lower or 'xls' in text_lower or '엑셀' in text_lower:
        return 'XLSX'
    elif 'ppt' in text_lower or 'powerpoint' in text_lower or '파워포인트' in text_lower:
        return 'PPT'
    elif 'zip' in text_lower or '압축' in text_lower:
        return 'ZIP'
    elif '이미지' in text_lower or 'image' in text_lower or '사진' in text_lower:
        return 'IMAGE'
    elif '양식' in text_lower or '서식' in text_lower or '신청서' in text_lower:
        return 'HWP'  # 한국 공공기관 양식은 대부분 HWP
    
    return None

def process_item(data, idx, total, supabase):
    """개별 항목 처리"""
    global success_count, error_count, attachment_total, skip_count, type_fixed
    
    # 이미 처리된 데이터 체크
    current_summary = data.get('bsns_sumry', '')
    current_attachments = data.get('attachment_urls')
    
    # 첨부파일이 있고 UNKNOWN이 있는지 체크
    has_unknown = False
    if current_attachments:
        for att in current_attachments:
            if isinstance(att, dict) and (att.get('type') == 'UNKNOWN' or att.get('type') == 'HTML'):
                has_unknown = True
                break
    
    # UNKNOWN이나 HTML이 없고 요약도 충분한 경우 스킵
    if current_summary and len(current_summary) >= 150 and current_attachments and not has_unknown:
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
        if current_attachments and has_unknown:
            print(f"  [{idx}] 기존 첨부파일 타입 수정 중...")
            
            updated_attachments = []
            fixed_count = 0
            
            for att in current_attachments:
                if isinstance(att, dict):
                    new_att = att.copy()
                    
                    # UNKNOWN이나 HTML인 경우만 재확인
                    if att.get('type') in ['UNKNOWN', 'HTML']:
                        url = att.get('url')
                        text = att.get('text', '') or att.get('display_filename', '')
                        
                        # 1. 텍스트에서 파일명/타입 추출 시도
                        text_type = extract_file_type_from_text(text)
                        
                        # 2. 파일 시그니처로 확인 (텍스트에서 못 찾은 경우)
                        if not text_type or text_type == 'UNKNOWN':
                            actual_type = get_file_type_by_signature(url, session)
                        else:
                            actual_type = text_type
                        
                        # 3. 여전히 UNKNOWN이면 텍스트 기반으로 한 번 더
                        if actual_type in ['UNKNOWN', 'HTML'] and text:
                            # 일반적인 패턴으로 추측
                            if any(keyword in text for keyword in ['양식', '서식', '신청서', '계획서']):
                                actual_type = 'HWP'
                            elif '붙임' in text or '첨부' in text:
                                actual_type = 'HWP'  # 한국 공공기관 기본
                        
                        if actual_type not in ['UNKNOWN', 'HTML']:
                            new_att['type'] = actual_type
                            new_att['safe_filename'] = f"{pblanc_id}_{len(updated_attachments)+1:02d}.{actual_type.lower()}"
                            fixed_count += 1
                            print(f"    - {att.get('type')} → {actual_type}")
                    
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
            else:
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
        processed_urls = set()
        
        # 모든 첨부파일 링크 찾기
        file_links = soup.find_all('a', href=lambda x: x and 'atchFileId=' in x)
        
        for link in file_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if 'atchFileId=' in href:
                atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                file_sn = '0'
                if 'fileSn=' in href:
                    file_sn = href.split('fileSn=')[1].split('&')[0]
                
                direct_url = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                
                if direct_url in processed_urls:
                    continue
                processed_urls.add(direct_url)
                
                # 파일 타입 감지
                # 1. 텍스트에서 힌트 찾기
                file_type = extract_file_type_from_text(text)
                
                # 2. 파일 시그니처로 확인
                if not file_type or file_type == 'UNKNOWN':
                    file_type = get_file_type_by_signature(direct_url, session)
                
                # 3. 기본값 설정
                if file_type in ['UNKNOWN', 'HTML']:
                    # 한국 공공기관 기본 양식은 HWP
                    if any(keyword in text for keyword in ['양식', '서식', '신청', '계획']):
                        file_type = 'HWP'
                
                display_filename = text or f"첨부파일_{len(attachments)+1}"
                safe_filename = f"{pblanc_id}_{len(attachments)+1:02d}.{file_type.lower()}"
                
                attachment = {
                    'url': direct_url,
                    'type': file_type,
                    'safe_filename': safe_filename,
                    'display_filename': display_filename,
                    'original_filename': text,
                    'text': text,
                    'params': {
                        'atchFileId': atch_file_id,
                        'fileSn': file_sn
                    }
                }
                
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
    print(" 기업마당 첨부파일 타입 복구 크롤링 v2")
    print(" - 파일 시그니처로 실제 타입 감지")
    print(" - UNKNOWN/HTML 타입 수정")
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
            
            # 수정이 필요하거나 요약이 부족한 경우
            if needs_fix or (not bsns_sumry or len(bsns_sumry) < 150) or (not attachment_urls):
                targets.append(item)
            else:
                already_done += 1
        
        print(f"✅ 전체: {len(all_targets)}개")
        print(f"⚠️ UNKNOWN 타입: {unknown_count}개")
        print(f"⚠️ HTML 타입: {html_count}개")
        print(f"✅ 정상 처리: {already_done}개")
        print(f"🔧 처리 필요: {len(targets)}개")
        
    except Exception as e:
        print(f"❌ 데이터 조회 오류: {e}")
        sys.exit(1)
    
    if not targets:
        print("처리할 데이터가 없습니다.")
        return
    
    print("\n2. 파일 타입 복구 시작...")
    print(f"   - 파일 시그니처 확인")
    print(f"   - 텍스트 힌트 활용")
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
    print(" 파일 타입 복구 완료")
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
