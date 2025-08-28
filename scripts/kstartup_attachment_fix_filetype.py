#!/usr/bin/env python3
"""
K-Startup 첨부파일 타입 수정 스크립트
DOC로 잘못 저장된 HWP 파일들을 수정
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

# KST 시간
def get_kst_time():
    """한국 시간(KST) 반환"""
    utc_now = datetime.utcnow()
    kst_now = utc_now + timedelta(hours=9)
    return kst_now

def check_file_signature(url):
    """파일 시그니처를 확인하여 실제 파일 타입 판별"""
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code != 200:
            return None
            
        # 처음 2KB 읽기
        content = response.raw.read(2048)
        
        # OLE 파일 체크 (HWP, DOC 등)
        if content[:4] == b'\xd0\xcf\x11\xe0':
            # OLE 컨테이너 내용 확인
            # HWP 특징 패턴
            hwp_patterns = [
                b'HWP Document', b'Hwp', b'Hancom', 
                b'HwPDocument', b'HwpSummaryInformation'
            ]
            # DOC 특징 패턴  
            doc_patterns = [
                b'Microsoft Word', b'Word.Document', 
                b'WordDocument', b'MSWordDoc'
            ]
            
            # 패턴 매칭
            is_hwp = any(pattern in content for pattern in hwp_patterns)
            is_doc = any(pattern in content for pattern in doc_patterns)
            
            if is_doc and not is_hwp:
                return 'DOC'
            else:
                # 명확하지 않으면 HWP로 간주 (한국 공고는 대부분 HWP)
                return 'HWP'
                
        # HWPX (ZIP 기반)
        elif content[:2] == b'PK':
            # ZIP 파일 내용 확인
            if b'hwpx' in content[:100] or b'Hancom' in content[:500]:
                return 'HWPX'
            elif b'word' in content[:100]:
                return 'DOCX'
            else:
                return 'ZIP'
                
        # PDF
        elif content[:4] == b'%PDF':
            return 'PDF'
            
        return None
        
    except Exception as e:
        print(f"    [ERROR] 파일 시그니처 확인 실패: {e}")
        return None

def fix_attachment_types():
    """DOC로 잘못 저장된 첨부파일 타입 수정"""
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("="*60)
    print("K-Startup 첨부파일 타입 수정")
    print("="*60)
    
    # DOC 타입으로 저장된 첨부파일이 있는 레코드 조회
    print("\n1. DOC 타입 첨부파일 검색...")
    
    result = supabase.table('kstartup_complete').select('*').execute()
    
    if not result.data:
        print("데이터가 없습니다.")
        return
    
    doc_records = []
    for record in result.data:
        att_urls = record.get('attachment_urls')
        if att_urls:
            # attachment_urls가 리스트인 경우
            if isinstance(att_urls, list):
                for att in att_urls:
                    if isinstance(att, dict) and att.get('type') == 'DOC':
                        doc_records.append(record)
                        break
            # attachment_urls가 단일 dict인 경우
            elif isinstance(att_urls, dict) and att_urls.get('type') == 'DOC':
                doc_records.append(record)
    
    print(f"DOC 타입 첨부파일이 있는 레코드: {len(doc_records)}개")
    
    if not doc_records:
        print("수정할 레코드가 없습니다.")
        return
    
    # 각 레코드 수정
    fixed_count = 0
    error_count = 0
    
    print("\n2. 파일 타입 검증 및 수정...")
    # 처리 개수 제한 (처음 10개만)
    for idx, record in enumerate(doc_records[:10]):
        ann_id = record.get('announcement_id')
        print(f"\n[{ann_id}]")
        
        att_urls = record.get('attachment_urls')
        updated = False
        
        if isinstance(att_urls, list):
            for att in att_urls:
                if isinstance(att, dict) and att.get('type') == 'DOC':
                    url = att.get('url', '')
                    
                    # K-Startup URL 형식 확인
                    if 'k-startup.go.kr' in url:
                        print(f"  - 파일 검증: {url[:50]}...")
                        
                        # 파일 시그니처 확인
                        real_type = check_file_signature(url)
                        
                        if real_type and real_type != 'DOC':
                            print(f"    타입 변경: DOC → {real_type}")
                            att['type'] = real_type
                            
                            # MIME 타입도 수정
                            mime_types = {
                                'HWP': 'application/x-hwp',
                                'HWPX': 'application/x-hwpx',
                                'PDF': 'application/pdf',
                                'DOCX': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                            }
                            if real_type in mime_types:
                                att['mime_type'] = mime_types[real_type]
                            
                            # safe_filename도 수정
                            if 'safe_filename' in att:
                                old_name = att['safe_filename']
                                if old_name.endswith('.doc'):
                                    new_name = old_name[:-4] + '.' + real_type.lower()
                                    att['safe_filename'] = new_name
                            
                            updated = True
                        elif real_type == 'DOC':
                            print(f"    타입 확인: 실제 DOC 파일")
                        else:
                            # 시그니처 확인 실패시 HWP로 가정
                            print(f"    타입 추정: DOC → HWP (한국 공고)")
                            att['type'] = 'HWP'
                            att['mime_type'] = 'application/x-hwp'
                            if 'safe_filename' in att and att['safe_filename'].endswith('.doc'):
                                att['safe_filename'] = att['safe_filename'][:-4] + '.hwp'
                            updated = True
        
        elif isinstance(att_urls, dict) and att_urls.get('type') == 'DOC':
            # 단일 dict 형태 처리 (같은 로직)
            url = att_urls.get('url', '')
            if 'k-startup.go.kr' in url:
                real_type = check_file_signature(url)
                if real_type and real_type != 'DOC':
                    att_urls['type'] = real_type
                    updated = True
        
        # DB 업데이트
        if updated:
            try:
                update_result = supabase.table('kstartup_complete').update({
                    'attachment_urls': att_urls
                }).eq('announcement_id', ann_id).execute()
                
                if update_result.data:
                    fixed_count += 1
                    print(f"  ✅ 수정 완료")
                else:
                    error_count += 1
                    print(f"  ❌ 업데이트 실패")
            except Exception as e:
                error_count += 1
                print(f"  ❌ 오류: {e}")
        
        # API 제한 방지
        time.sleep(0.5)
    
    # 결과 출력
    print("\n" + "="*60)
    print("수정 완료!")
    print(f"  - 수정된 레코드: {fixed_count}개")
    print(f"  - 오류: {error_count}개")
    print(f"  - 검토한 레코드: {len(doc_records)}개")
    print("="*60)
    
    # 특정 레코드 확인
    print("\n3. KS_174765 (ID 3905) 확인...")
    check_result = supabase.table('kstartup_complete').select('*').eq('announcement_id', 'KS_174765').execute()
    
    if check_result.data:
        record = check_result.data[0]
        att_urls = record.get('attachment_urls')
        print(f"ID: {record.get('id')}")
        print(f"공고 ID: {record.get('announcement_id')}")
        if att_urls:
            if isinstance(att_urls, list):
                for i, att in enumerate(att_urls, 1):
                    if isinstance(att, dict):
                        print(f"첨부파일 {i}: 타입={att.get('type')}, 파일명={att.get('safe_filename', 'N/A')}")
            elif isinstance(att_urls, dict):
                print(f"첨부파일: 타입={att_urls.get('type')}, 파일명={att_urls.get('safe_filename', 'N/A')}")

if __name__ == "__main__":
    fix_attachment_types()