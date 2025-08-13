#!/usr/bin/env python3
"""
기업마당 첨부파일 크롤러 - 실제 파일 타입 감지 버전
HEAD 요청으로 Content-Type을 확인하여 정확한 파일 타입 저장
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
import mimetypes

# 전역 변수
lock = threading.Lock()
success_count = 0
error_count = 0
attachment_total = 0
skip_count = 0

def get_file_type_from_url(url, session=None):
    """HEAD 요청으로 실제 파일 타입 감지"""
    if session is None:
        session = requests.Session()
    
    try:
        # HEAD 요청으로 Content-Type 확인
        response = session.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Content-Type으로 확장자 결정
        if 'pdf' in content_type:
            return 'PDF'
        elif 'hwp' in content_type or 'haansoft' in content_type or 'x-hwp' in content_type:
            return 'HWP'
        elif 'word' in content_type or 'msword' in content_type or 'document' in content_type:
            return 'DOCX'
        elif 'excel' in content_type or 'spreadsheet' in content_type or 'ms-excel' in content_type:
            return 'XLSX'
        elif 'powerpoint' in content_type or 'presentation' in content_type:
            return 'PPT'
        elif 'zip' in content_type or 'x-zip' in content_type or 'compressed' in content_type:
            return 'ZIP'
        elif 'image' in content_type:
            if 'jpeg' in content_type or 'jpg' in content_type:
                return 'JPG'
            elif 'png' in content_type:
                return 'PNG'
            elif 'gif' in content_type:
                return 'GIF'
            else:
                return 'IMAGE'
        elif 'text' in content_type:
            if 'plain' in content_type:
                return 'TXT'
            elif 'html' in content_type:
                return 'HTML'
            else:
                return 'TEXT'
        elif 'octet-stream' in content_type:
            # octet-stream인 경우 URL의 확장자로 추측
            return guess_type_from_url(url)
        else:
            return 'UNKNOWN'
            
    except Exception as e:
        # HEAD 요청 실패 시 URL에서 추측
        return guess_type_from_url(url)

def guess_type_from_url(url):
    """URL 또는 파일명에서 확장자 추측 (폴백용)"""
    url_lower = url.lower()
    
    # URL에서 확장자 추출 시도
    if '.hwp' in url_lower or '.hwpx' in url_lower:
        return 'HWP'
    elif '.pdf' in url_lower:
        return 'PDF'
    elif '.doc' in url_lower or '.docx' in url_lower:
        return 'DOCX'
    elif '.xls' in url_lower or '.xlsx' in url_lower:
        return 'XLSX'
    elif '.ppt' in url_lower or '.pptx' in url_lower:
        return 'PPT'
    elif '.zip' in url_lower or '.rar' in url_lower or '.7z' in url_lower:
        return 'ZIP'
    elif '.jpg' in url_lower or '.jpeg' in url_lower:
        return 'JPG'
    elif '.png' in url_lower:
        return 'PNG'
    elif '.gif' in url_lower:
        return 'GIF'
    elif '.txt' in url_lower:
        return 'TXT'
    elif '.rtf' in url_lower:
        return 'RTF'
    else:
        return 'UNKNOWN'

def extract_file_type_from_text(text):
    """링크 텍스트에서 파일 타입 힌트 추출"""
    text_lower = text.lower()
    if '한글' in text_lower or 'hwp' in text_lower:
        return 'HWP'
    elif 'pdf' in text_lower:
        return 'PDF'
    elif 'word' in text_lower or 'doc' in text_lower:
        return 'DOCX'
    elif 'excel' in text_lower or 'xls' in text_lower or '엑셀' in text_lower:
        return 'XLSX'
    elif 'ppt' in text_lower or 'powerpoint' in text_lower or '파워포인트' in text_lower:
        return 'PPT'
    elif 'zip' in text_lower or '압축' in text_lower:
        return 'ZIP'
    elif '이미지' in text_lower or 'image' in text_lower or '사진' in text_lower:
        return 'IMAGE'
    return None

def process_item(data, idx, total, supabase):
    """개별 항목 처리"""
    global success_count, error_count, attachment_total, skip_count
    
    # 이미 처리된 데이터 체크
    current_summary = data.get('bsns_sumry', '')
    current_attachments = data.get('attachment_urls')
    
    # 첨부파일이 있고 모든 파일이 UNKNOWN이 아닌 경우만 스킵
    has_valid_types = False
    if current_attachments:
        for att in current_attachments:
            if isinstance(att, dict) and att.get('type') != 'UNKNOWN':
                has_valid_types = True
                break
    
    # 이미 충분히 처리된 경우 스킵 (요약도 충분하고 파일 타입도 정상)
    if current_summary and len(current_summary) >= 150 and has_valid_types:
        with lock:
            skip_count += 1
        print(f"[{idx}/{total}] ⏭️ 이미 처리 완료")
        return False
    
    # 세션 생성 (스레드별로 독립적인 세션)
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    try:
        pblanc_id = data['pblanc_id']
        pblanc_nm = data['pblanc_nm'][:50] + "..." if len(data['pblanc_nm']) > 50 else data['pblanc_nm']
        dtl_url = data.get('dtl_url')
        
        print(f"[{idx}/{total}] {pblanc_nm}")
        
        if not dtl_url:
            print(f"  [{idx}] ⚠️ 상세 URL 없음")
            return False
        
        # 재시도 로직 추가
        max_retries = 3
        for retry in range(max_retries):
            try:
                # 상세페이지 접속
                response = session.get(dtl_url, timeout=15)
                response.encoding = 'utf-8'
                
                if response.status_code != 200:
                    print(f"  [{idx}] ⚠️ HTTP {response.status_code}")
                    if retry < max_retries - 1:
                        time.sleep(2)
                        continue
                    with lock:
                        error_count += 1
                    return False
                
                break  # 성공하면 재시도 루프 종료
            except requests.exceptions.RequestException as e:
                if retry < max_retries - 1:
                    print(f"  [{idx}] 재시도 {retry+1}/{max_retries-1}")
                    time.sleep(3)
                    continue
                print(f"  [{idx}] ❌ 연결 실패: {str(e)[:30]}")
                with lock:
                    error_count += 1
                return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 첨부파일 정보 추출
        attachments = []
        processed_urls = set()  # 중복 체크용
        
        # 방법 1: atchFileId가 있는 모든 링크 찾기
        file_links = soup.find_all('a', href=lambda x: x and 'atchFileId=' in x)
        
        for link in file_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # URL에서 파라미터 추출
            if 'atchFileId=' in href:
                # atchFileId 추출
                atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                
                # fileSn 추출 (없으면 0)
                file_sn = '0'
                if 'fileSn=' in href:
                    file_sn = href.split('fileSn=')[1].split('&')[0]
                
                # 직접 다운로드 URL 구성
                direct_url = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                
                # 중복 체크
                if direct_url in processed_urls:
                    continue
                processed_urls.add(direct_url)
                
                # 실제 파일 타입 감지 (HEAD 요청)
                file_type = get_file_type_from_url(direct_url, session)
                
                # 여전히 UNKNOWN이면 텍스트에서 힌트 찾기
                if file_type == 'UNKNOWN':
                    text_hint = extract_file_type_from_text(text)
                    if text_hint:
                        file_type = text_hint
                
                # 파일명 정리
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
        
        # 방법 2: 첨부파일 영역에서 추가 찾기
        if not attachments:
            file_areas = soup.find_all(['div', 'ul', 'dl'], class_=['file', 'attach', 'download'])
            for area in file_areas:
                links = area.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    if 'atchFileId=' in href:
                        atch_file_id = href.split('atchFileId=')[1].split('&')[0]
                        file_sn = href.split('fileSn=')[1].split('&')[0] if 'fileSn=' in href else '0'
                        
                        direct_url = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                        
                        if direct_url not in processed_urls:
                            processed_urls.add(direct_url)
                            file_type = get_file_type_from_url(direct_url, session)
                            
                            attachments.append({
                                'url': direct_url,
                                'type': file_type,
                                'safe_filename': f"{pblanc_id}_{len(attachments)+1:02d}.{file_type.lower()}",
                                'display_filename': link.get_text(strip=True) or f"첨부파일_{len(attachments)+1}",
                                'params': {'atchFileId': atch_file_id, 'fileSn': file_sn}
                            })
        
        # 상세 내용 추출 (요약 개선용)
        content_parts = []
        
        # 본문 내용 찾기 - 더 많은 선택자 추가
        content_selectors = [
            'div.view_cont', 'div.content', 'div.board_view',
            'td.content', 'td.view_cont',
            'div.bbs_cont', 'div.board_content',
            'div#content', 'div.con_view'
        ]
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                text = content_area.get_text(separator=' ', strip=True)
                if text and len(text) > 50:
                    content_parts.append(text[:1000])  # 더 긴 텍스트 추출
                    break
        
        # 요약 생성/개선 - 현재 요약이 부족한 경우만
        if not current_summary or len(current_summary) < 150:
            summary_parts = []
            summary_parts.append(f"📋 {data['pblanc_nm']}")
            
            # 본문 내용 더 자세히 포함
            if content_parts:
                # 공백 정리 및 주요 내용 추출
                content_text = ' '.join(content_parts[0].split())[:400]
                summary_parts.append(f"📝 {content_text}...")
            
            # 기간 정보 추출 시도
            date_info = soup.find(text=lambda t: t and ('접수기간' in t or '신청기간' in t))
            if date_info:
                summary_parts.append(f"📅 {date_info.strip()}")
            
            if attachments:
                file_types = list(set([a['type'] for a in attachments]))
                summary_parts.append(f"📎 첨부: {', '.join(file_types)} ({len(attachments)}개)")
            
            new_summary = "\n".join(summary_parts)
        else:
            new_summary = current_summary
            # 첨부파일 정보만 추가
            if attachments and '📎' not in current_summary:
                file_types = list(set([a['type'] for a in attachments]))
                new_summary += f"\n📎 첨부: {', '.join(file_types)} ({len(attachments)}개)"
        
        # DB 업데이트 - 실제 변경사항이 있을 때만
        update_data = {}
        
        # 첨부파일이 없거나 UNKNOWN만 있는 경우 업데이트
        if attachments and (not current_attachments or not has_valid_types):
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
            
            # 파일 타입 통계 출력
            if attachments:
                type_counts = {}
                for att in attachments:
                    file_type = att.get('type', 'UNKNOWN')
                    type_counts[file_type] = type_counts.get(file_type, 0) + 1
                type_info = ', '.join([f"{t}:{c}" for t, c in type_counts.items()])
                print(f"  [{idx}] ✅ 성공 (첨부: {len(attachments)}개 [{type_info}], 요약: {len(new_summary)}자)")
            else:
                print(f"  [{idx}] ✅ 성공 (요약: {len(new_summary)}자)")
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

def main():
    global success_count, error_count, attachment_total, skip_count
    
    print("=" * 60)
    print(" 기업마당 첨부파일 타입 복구 크롤링")
    print(" - HEAD 요청으로 실제 파일 타입 감지")
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
        # 전체 데이터 조회 (최대 5000개)
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
            
            if len(all_targets) >= 5000:  # 최대 5000개
                break
        
        # 처리 대상 분류
        targets = []
        unknown_count = 0
        already_done = 0
        
        for item in all_targets:
            bsns_sumry = item.get('bsns_sumry', '')
            attachment_urls = item.get('attachment_urls')
            
            # 첨부파일이 있는 경우 UNKNOWN 체크
            has_unknown = False
            if attachment_urls:
                for att in attachment_urls:
                    if isinstance(att, dict) and att.get('type') == 'UNKNOWN':
                        has_unknown = True
                        unknown_count += 1
                        break
            
            # UNKNOWN이 있거나, 요약이 부족하거나, 첨부파일이 없는 경우
            if has_unknown or (not bsns_sumry or len(bsns_sumry) < 150) or (not attachment_urls):
                targets.append(item)
            else:
                already_done += 1
        
        print(f"✅ 전체: {len(all_targets)}개")
        print(f"✅ UNKNOWN 파일 타입: {unknown_count}개")
        print(f"✅ 이미 처리 완료: {already_done}개")
        print(f"✅ 처리 필요: {len(targets)}개")
        
    except Exception as e:
        print(f"❌ 데이터 조회 오류: {e}")
        sys.exit(1)
    
    if not targets:
        print("처리할 데이터가 없습니다.")
        return
    
    print("\n2. 파일 타입 복구 크롤링 시작...")
    print(f"   - 스레드 수: 5개 (안정성 우선)")
    print(f"   - HEAD 요청으로 실제 파일 타입 확인")
    print(f"   - 예상 시간: {len(targets) // 5 // 2}분")
    print("-" * 60)
    
    start_time = time.time()
    
    # 배치 처리 (50개씩, 더 작은 배치)
    batch_size = 50
    for batch_start in range(0, len(targets), batch_size):
        batch_end = min(batch_start + batch_size, len(targets))
        batch = targets[batch_start:batch_end]
        
        print(f"\n배치 처리: {batch_start+1}-{batch_end}/{len(targets)}")
        
        # 멀티스레딩으로 처리 (스레드 수 줄임)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i, data in enumerate(batch, batch_start + 1):
                future = executor.submit(process_item, data, i, len(targets), supabase)
                futures.append(future)
                time.sleep(0.2)  # 요청 간격
            
            # 결과 대기
            for future in as_completed(futures):
                future.result()
        
        # 배치 간 휴식
        if batch_end < len(targets):
            print(f"배치 완료. 3초 대기...")
            time.sleep(3)
    
    elapsed_time = time.time() - start_time
    
    # 결과 출력
    print("\n" + "=" * 60)
    print(" 파일 타입 복구 완료")
    print("=" * 60)
    print(f"✅ 성공: {success_count}개")
    print(f"⏭️ 스킵: {skip_count}개 (이미 처리됨)")
    print(f"❌ 실패: {error_count}개")
    print(f"📎 첨부파일: {attachment_total}개")
    print(f"⏱️ 소요 시간: {elapsed_time:.1f}초 ({elapsed_time/60:.1f}분)")
    if success_count > 0:
        print(f"📊 처리 속도: {success_count/elapsed_time:.1f}개/초")
    print("=" * 60)

if __name__ == "__main__":
    main()
