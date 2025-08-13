#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BizInfo 파일 타입 완전 수정 스크립트
- getImageFile 타입 1,264개 수정
- DOC 타입 182개 수정 
- UNKNOWN 타입 99개 수정
- HTML 타입 63개 수정
- 깨진 파일명 복구
"""

import os
import json
import time
import requests
from datetime import datetime
from supabase import create_client, Client
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
import urllib.parse
import re

# Supabase 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_file_extension_from_filename(filename: str) -> str:
    """파일명에서 확장자 추출"""
    if not filename:
        return 'UNKNOWN'
    
    # 파일명 정리
    filename = filename.strip().lower()
    
    # 확장자 추출
    if '.' in filename:
        ext = filename.split('.')[-1].upper()
        
        # 알려진 확장자 매핑
        ext_map = {
            'HWP': 'HWP',
            'HWPX': 'HWP',
            'PDF': 'PDF',
            'DOC': 'DOC',
            'DOCX': 'DOCX',
            'XLS': 'XLS',
            'XLSX': 'XLSX',
            'PPT': 'PPT',
            'PPTX': 'PPTX',
            'ZIP': 'ZIP',
            'RAR': 'ZIP',
            'JPG': 'JPG',
            'JPEG': 'JPG',
            'PNG': 'PNG',
            'GIF': 'GIF',
            'TXT': 'TXT',
            'HTML': 'HTML',
            'HTM': 'HTML'
        }
        
        return ext_map.get(ext, ext)
    
    return 'UNKNOWN'

def check_file_signature(url: str) -> Optional[str]:
    """파일 시그니처로 실제 파일 타입 확인"""
    try:
        # HEAD 요청으로 Content-Type 확인
        response = requests.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Content-Type 매핑
        type_map = {
            'application/haansoft-hwp': 'HWP',
            'application/x-hwp': 'HWP',
            'application/pdf': 'PDF',
            'application/msword': 'DOC',
            'application/vnd.openxmlformats-officedocument.wordprocessingml': 'DOCX',
            'application/vnd.ms-excel': 'XLS',
            'application/vnd.openxmlformats-officedocument.spreadsheetml': 'XLSX',
            'application/zip': 'ZIP',
            'image/jpeg': 'JPG',
            'image/jpg': 'JPG',
            'image/png': 'PNG',
            'text/plain': 'TXT',
            'text/html': 'HTML'
        }
        
        for key, value in type_map.items():
            if key in content_type:
                return value
        
        # GET 요청으로 파일 시그니처 확인 (첫 8바이트)
        response = requests.get(url, stream=True, timeout=5)
        header = response.content[:8]
        
        # 파일 시그니처 매핑
        if header[:4] == b'%PDF':
            return 'PDF'
        elif header[:4] == b'\xd0\xcf\x11\xe0':  # MS Office
            return 'DOC'
        elif header[:4] == b'PK\x03\x04':  # ZIP 또는 Office Open XML
            # 더 자세한 확인 필요
            content = response.content[:1000]
            if b'word/' in content:
                return 'DOCX'
            elif b'xl/' in content:
                return 'XLSX'
            elif b'ppt/' in content:
                return 'PPTX'
            else:
                return 'ZIP'
        elif header[:2] == b'\xff\xd8':  # JPEG
            return 'JPG'
        elif header[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
            return 'PNG'
        
    except Exception as e:
        print(f"파일 시그니처 확인 실패: {e}")
    
    return None

def fix_broken_encoding(text: str) -> str:
    """깨진 인코딩 복구"""
    if not text:
        return text
    
    # 이중/삼중 인코딩 패턴
    patterns = {
        'Ã¬': '이',
        'Â°': '°',
        'Â': '',
        'ÃªÂ': '개',
        'Ã­Â': '한',
        'Ã«Â': '라',
        'ì': 'i',
        'ë': 'e',
        'í': 'i',
        'ê': 'e',
        'ã': 'a'
    }
    
    result = text
    for pattern, replacement in patterns.items():
        result = result.replace(pattern, replacement)
    
    # Latin-1로 디코딩 시도
    try:
        # UTF-8 -> Latin-1 -> UTF-8 복구
        if 'Ã' in result or 'Â' in result:
            bytes_text = result.encode('latin-1', errors='ignore')
            result = bytes_text.decode('utf-8', errors='ignore')
    except:
        pass
    
    return result

def process_file_entry(file_entry: dict) -> dict:
    """개별 파일 엔트리 처리"""
    updated = False
    
    # 1. getImageFile 타입 수정
    if file_entry.get('type') == 'getImageFile':
        # URL에서 실제 파일 타입 확인
        url = file_entry.get('url', '')
        
        # display_filename에서 확장자 확인
        display_filename = file_entry.get('display_filename', '')
        if display_filename:
            file_type = get_file_extension_from_filename(display_filename)
        else:
            # original_filename에서 확인
            original_filename = file_entry.get('original_filename', '')
            if original_filename:
                file_type = get_file_extension_from_filename(original_filename)
            else:
                # URL에서 시그니처 확인
                file_type = check_file_signature(url)
                if not file_type:
                    file_type = 'HWP'  # 기본값
        
        file_entry['type'] = file_type
        updated = True
    
    # 2. DOC 타입 검증 및 수정
    elif file_entry.get('type') == 'DOC':
        display_filename = file_entry.get('display_filename', '').lower()
        original_filename = file_entry.get('original_filename', '').lower()
        
        # 실제로 HWP인지 확인
        if '.hwp' in display_filename or '.hwp' in original_filename:
            file_entry['type'] = 'HWP'
            updated = True
        elif not ('.doc' in display_filename or '.doc' in original_filename):
            # 파일 시그니처로 확인
            url = file_entry.get('url', '')
            file_type = check_file_signature(url)
            if file_type:
                file_entry['type'] = file_type
                updated = True
    
    # 3. UNKNOWN 타입 수정
    elif file_entry.get('type') == 'UNKNOWN':
        display_filename = file_entry.get('display_filename', '')
        if display_filename and display_filename != '첨부파일_1.unknown':
            file_type = get_file_extension_from_filename(display_filename)
        else:
            # URL에서 시그니처 확인
            url = file_entry.get('url', '')
            file_type = check_file_signature(url)
            if not file_type:
                file_type = 'HWP'  # 기본값
        
        file_entry['type'] = file_type
        updated = True
    
    # 4. HTML 타입 수정
    elif file_entry.get('type') == 'HTML':
        display_filename = file_entry.get('display_filename', '').lower()
        
        # HTML이 아닌 경우가 많음
        if not ('.html' in display_filename or '.htm' in display_filename):
            url = file_entry.get('url', '')
            file_type = check_file_signature(url)
            if file_type and file_type != 'HTML':
                file_entry['type'] = file_type
                updated = True
    
    # 5. 파일명 인코딩 수정
    display_filename = file_entry.get('display_filename', '')
    if display_filename and ('Ã' in display_filename or 'Â' in display_filename):
        fixed_filename = fix_broken_encoding(display_filename)
        if fixed_filename != display_filename:
            file_entry['display_filename'] = fixed_filename
            updated = True
    
    original_filename = file_entry.get('original_filename', '')
    if original_filename and ('Ã' in original_filename or 'Â' in original_filename):
        fixed_filename = fix_broken_encoding(original_filename)
        if fixed_filename != original_filename:
            file_entry['original_filename'] = fixed_filename
            updated = True
    
    return file_entry, updated

def process_announcement(row: dict) -> Tuple[str, bool, dict]:
    """개별 공고 처리"""
    pblanc_id = row['pblanc_id']
    attachment_urls = row.get('attachment_urls', [])
    
    if not attachment_urls:
        return pblanc_id, False, None
    
    updated_files = []
    has_changes = False
    
    for file_entry in attachment_urls:
        updated_entry, was_updated = process_file_entry(file_entry.copy())
        updated_files.append(updated_entry)
        if was_updated:
            has_changes = True
    
    if has_changes:
        return pblanc_id, True, {'attachment_urls': json.dumps(updated_files, ensure_ascii=False)}
    
    return pblanc_id, False, None

def main():
    print("="*50)
    print("BizInfo 파일 타입 완전 수정 시작")
    print(f"시작 시간: {datetime.now()}")
    print("="*50)
    
    # 문제가 있는 데이터 조회
    print("\n1. 문제 데이터 조회 중...")
    
    query = """
    SELECT pblanc_id, attachment_urls 
    FROM bizinfo_complete 
    WHERE attachment_urls IS NOT NULL 
    AND attachment_urls != '[]'::jsonb
    AND (
        attachment_urls::text LIKE '%"type":"getImageFile"%' OR
        attachment_urls::text LIKE '%"type":"DOC"%' OR
        attachment_urls::text LIKE '%"type":"UNKNOWN"%' OR
        attachment_urls::text LIKE '%"type":"HTML"%' OR
        attachment_urls::text LIKE '%Ã%' OR
        attachment_urls::text LIKE '%Â%'
    )
    """
    
    response = supabase.rpc('execute_sql', {'query': query}).execute()
    
    if not response.data:
        print("수정할 데이터가 없습니다.")
        return
    
    announcements = response.data
    total_count = len(announcements)
    print(f"수정 대상: {total_count}개 공고")
    
    # 병렬 처리
    print("\n2. 파일 타입 수정 시작...")
    
    updates_to_apply = []
    processed = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_announcement, row): row 
            for row in announcements
        }
        
        for future in as_completed(futures):
            pblanc_id, needs_update, update_data = future.result()
            processed += 1
            
            if needs_update:
                updates_to_apply.append({
                    'pblanc_id': pblanc_id,
                    'update_data': update_data
                })
            
            if processed % 100 == 0:
                print(f"처리 진행: {processed}/{total_count}")
    
    # 데이터베이스 업데이트
    if updates_to_apply:
        print(f"\n3. 데이터베이스 업데이트 중... ({len(updates_to_apply)}개)")
        
        success_count = 0
        for item in updates_to_apply:
            try:
                supabase.table('bizinfo_complete').update(
                    item['update_data']
                ).eq('pblanc_id', item['pblanc_id']).execute()
                success_count += 1
                
                if success_count % 50 == 0:
                    print(f"업데이트 진행: {success_count}/{len(updates_to_apply)}")
                    
            except Exception as e:
                print(f"업데이트 실패 ({item['pblanc_id']}): {e}")
        
        print(f"\n업데이트 완료: {success_count}/{len(updates_to_apply)}")
    
    # 결과 확인
    print("\n4. 수정 결과 확인...")
    
    # 파일 타입 분포 재확인
    query = """
    WITH file_types AS (
        SELECT 
            jsonb_array_elements(attachment_urls)->>'type' as file_type
        FROM bizinfo_complete
        WHERE attachment_urls IS NOT NULL AND attachment_urls != '[]'::jsonb
    )
    SELECT 
        file_type,
        COUNT(*) as count
    FROM file_types
    WHERE file_type IN ('getImageFile', 'DOC', 'UNKNOWN', 'HTML')
    GROUP BY file_type
    ORDER BY count DESC
    """
    
    response = supabase.rpc('execute_sql', {'query': query}).execute()
    
    if response.data:
        print("\n남은 문제 파일 타입:")
        for row in response.data:
            print(f"  - {row['file_type']}: {row['count']}개")
    else:
        print("\n✅ 모든 파일 타입 문제가 해결되었습니다!")
    
    print(f"\n완료 시간: {datetime.now()}")

if __name__ == "__main__":
    main()
