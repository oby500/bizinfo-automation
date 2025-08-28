#!/usr/bin/env python3
"""
기업마당(BizInfo) 첨부파일 타입 수정 스크립트
getImageFile 등 잘못된 타입을 실제 파일 타입으로 수정
"""

import os
import sys
import requests
from supabase import create_client
from datetime import datetime, timedelta
import json
import time

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Supabase 설정
SUPABASE_URL = "https://csuziaogycciwgxxmahm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzdXppYW9neWNjaXdneHhtYWhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYxNTc4MCwiZXhwIjoyMDY5MTkxNzgwfQ.HnhM7zSLzi7lHVPd2IVQKIACDq_YA05mBMgZbSN1c9Q"

def get_file_type_from_filename(filename):
    """파일명에서 파일 타입 추출"""
    if not filename:
        return None
        
    filename_lower = filename.lower()
    
    # 확장자 매핑
    ext_map = {
        '.hwp': 'HWP',
        '.hwpx': 'HWPX', 
        '.pdf': 'PDF',
        '.doc': 'DOC',
        '.docx': 'DOCX',
        '.xls': 'XLS',
        '.xlsx': 'XLSX',
        '.ppt': 'PPT',
        '.pptx': 'PPTX',
        '.zip': 'ZIP',
        '.jpg': 'JPG',
        '.jpeg': 'JPG',
        '.png': 'PNG',
        '.gif': 'GIF',
        '.txt': 'TXT'
    }
    
    for ext, file_type in ext_map.items():
        if filename_lower.endswith(ext):
            return file_type
    
    return None

def check_file_signature(url):
    """파일 시그니처를 확인하여 실제 파일 타입 판별"""
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code != 200:
            return None
            
        # 처음 2KB 읽기
        content = response.raw.read(2048)
        
        # 파일 시그니처 체크
        # PDF
        if content[:4] == b'%PDF':
            return 'PDF'
        # OLE 파일 (HWP, DOC 등)
        elif content[:4] == b'\xd0\xcf\x11\xe0':
            # OLE 컨테이너 - 기본적으로 HWP로 간주 (한국 정부 공고)
            return 'HWP'
        # ZIP 기반 (HWPX, DOCX 등)
        elif content[:2] == b'PK':
            content_str = content.decode('latin-1', errors='ignore')
            if 'hwpx' in content_str.lower() or 'hancom' in content_str.lower():
                return 'HWPX'
            elif 'word' in content_str.lower():
                return 'DOCX'
            else:
                return 'ZIP'
        # PNG
        elif content[:8] == b'\x89PNG\r\n\x1a\n':
            return 'PNG'
        # JPG
        elif content[:3] == b'\xff\xd8\xff':
            return 'JPG'
        # GIF
        elif content[:6] == b'GIF87a' or content[:6] == b'GIF89a':
            return 'GIF'
            
        return None
        
    except Exception as e:
        print(f"    [ERROR] 파일 시그니처 확인 실패: {e}")
        return None

def fix_bizinfo_attachment_types():
    """기업마당 첨부파일 타입 수정"""
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("="*60)
    print("기업마당(BizInfo) 첨부파일 타입 수정")
    print("="*60)
    
    # 문제가 있는 타입들
    problem_types = ['getImageFile', 'DOC', 'UNKNOWN', 'HTML']
    
    # 문제 있는 레코드 찾기
    print("\n1. 문제가 있는 첨부파일 검색...")
    
    result = supabase.table('bizinfo_complete').select('*').execute()
    
    if not result.data:
        print("데이터가 없습니다.")
        return
    
    problem_records = []
    for record in result.data:
        att_urls = record.get('attachment_urls')
        if att_urls and isinstance(att_urls, list):
            has_problem = False
            for att in att_urls:
                if isinstance(att, dict) and att.get('type') in problem_types:
                    has_problem = True
                    break
            if has_problem:
                problem_records.append(record)
    
    print(f"문제가 있는 레코드: {len(problem_records)}개")
    
    if not problem_records:
        print("수정할 레코드가 없습니다.")
        return
    
    # 각 레코드 수정
    fixed_count = 0
    error_count = 0
    
    print(f"\n2. 파일 타입 검증 및 수정... (전체 {len(problem_records)}개)")
    
    for idx, record in enumerate(problem_records, 1):
        ann_id = record.get('announcement_id')
        
        # 진행 상황 표시
        if idx % 10 == 0 or idx == 1:
            print(f"\n진행: {idx}/{len(problem_records)} ({idx*100//len(problem_records)}%)")
        
        # 상세 로그는 처음 5개만
        verbose = idx <= 5
        
        att_urls = record.get('attachment_urls')
        updated = False
        
        if att_urls and isinstance(att_urls, list):
            for att in att_urls:
                if isinstance(att, dict) and att.get('type') in problem_types:
                    current_type = att.get('type')
                    url = att.get('url', '')
                    filename = att.get('safe_filename') or att.get('display_filename', '')
                    
                    new_type = None
                    
                    # 1. 파일명에서 타입 추출
                    if filename:
                        new_type = get_file_type_from_filename(filename)
                    
                    # 2. 파일명에서 못 찾으면 시그니처 체크
                    if not new_type and url:
                        if verbose:
                            print(f"  [{ann_id}] 파일 시그니처 검증...")
                        new_type = check_file_signature(url)
                    
                    # 3. 그래도 못 찾으면 기본값 (HWP)
                    if not new_type:
                        if 'bizinfo.go.kr' in url:
                            new_type = 'HWP'  # 기업마당은 대부분 HWP
                    
                    # 타입 변경
                    if new_type and new_type != current_type:
                        if verbose:
                            print(f"    타입 변경: {current_type} → {new_type}")
                        
                        att['type'] = new_type
                        
                        # MIME 타입도 수정
                        mime_types = {
                            'HWP': 'application/x-hwp',
                            'HWPX': 'application/x-hwpx',
                            'PDF': 'application/pdf',
                            'DOC': 'application/msword',
                            'DOCX': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                            'ZIP': 'application/zip',
                            'JPG': 'image/jpeg',
                            'PNG': 'image/png',
                            'GIF': 'image/gif'
                        }
                        if new_type in mime_types:
                            att['mime_type'] = mime_types[new_type]
                        
                        updated = True
        
        # DB 업데이트
        if updated:
            try:
                update_result = supabase.table('bizinfo_complete').update({
                    'attachment_urls': att_urls
                }).eq('announcement_id', ann_id).execute()
                
                if update_result.data:
                    fixed_count += 1
                    if verbose:
                        print(f"  ✅ 수정 완료")
                else:
                    error_count += 1
                    if verbose or error_count <= 5:
                        print(f"  ❌ [{ann_id}] 업데이트 실패")
            except Exception as e:
                error_count += 1
                if verbose or error_count <= 5:
                    print(f"  ❌ [{ann_id}] 오류: {e}")
        
        # API 제한 방지
        if updated:
            time.sleep(0.2)
    
    # 결과 출력
    print("\n" + "="*60)
    print("수정 완료!")
    print(f"  - 수정된 레코드: {fixed_count}개")
    print(f"  - 오류: {error_count}개")
    print(f"  - 검토한 레코드: {len(problem_records)}개")
    print("="*60)
    
    # 현재 상태 확인
    print("\n3. 수정 후 상태 확인...")
    check_result = supabase.table('bizinfo_complete').select('attachment_urls').execute()
    
    type_counts = {}
    if check_result.data:
        for record in check_result.data:
            att_urls = record.get('attachment_urls')
            if att_urls and isinstance(att_urls, list):
                for att in att_urls:
                    if isinstance(att, dict):
                        file_type = att.get('type', 'UNKNOWN')
                        type_counts[file_type] = type_counts.get(file_type, 0) + 1
    
    print("\n파일 타입별 분포:")
    for file_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {file_type}: {count}개")
    
    # 문제 타입 확인
    remaining_problems = sum(type_counts.get(t, 0) for t in problem_types)
    if remaining_problems > 0:
        print(f"\n⚠️ 아직 {remaining_problems}개의 문제가 남아있습니다.")
    else:
        print("\n✅ 모든 문제가 해결되었습니다!")

if __name__ == "__main__":
    fix_bizinfo_attachment_types()