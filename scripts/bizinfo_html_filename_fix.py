#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BizInfo 파일명 HTML 재크롤링 스크립트
- HTML에서 div.file_name 직접 추출하여 깨진 파일명 완전 해결
"""

import os
import json
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client
from typing import Dict, List, Optional
import re

# Supabase 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_filename_broken(filename: str) -> bool:
    """파일명이 깨졌는지 확인"""
    if not filename:
        return True
    
    # 깨진 문자 패턴
    broken_patterns = ['Ã', 'Â', 'ì', 'í', 'ë', 'ã', 'ð', 'þ', 'ï', '¿', '½']
    
    for pattern in broken_patterns:
        if pattern in filename:
            return True
    
    # '다운로드'만 있는 경우도 문제
    if filename in ['다운로드', '첨부파일']:
        return True
    
    return False

def extract_filename_from_html(pblanc_id: str) -> List[Dict]:
    """HTML에서 정확한 파일명 추출"""
    
    detail_url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(detail_url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 첨부파일 영역 찾기
        file_list = soup.find('div', class_='file_list')
        if not file_list:
            return None
        
        files = []
        file_items = file_list.find_all('li')
        
        for item in file_items:
            # file_name div에서 실제 파일명 추출
            file_name_div = item.find('div', class_='file_name')
            if file_name_div:
                actual_filename = file_name_div.get_text(strip=True)
                
                # 다운로드 링크에서 파라미터 추출
                download_link = item.find('a')
                if download_link:
                    onclick = download_link.get('onclick', '')
                    
                    # fnDownload('FILE_000000000721244', '0'); 패턴에서 추출
                    match = re.search(r"fnDownload\('([^']+)',\s*'([^']+)'\)", onclick)
                    if match:
                        atch_file_id = match.group(1)
                        file_sn = match.group(2)
                        
                        # 파일 타입 추출
                        file_type = 'FILE'
                        if '.' in actual_filename:
                            ext = actual_filename.split('.')[-1].upper()
                            file_type = ext
                        
                        files.append({
                            'filename': actual_filename,
                            'type': file_type,
                            'atchFileId': atch_file_id,
                            'fileSn': file_sn
                        })
        
        return files if files else None
        
    except Exception as e:
        return None

def process_announcement(row: dict) -> bool:
    """개별 공고 처리"""
    pblanc_id = row['pblanc_id']
    current_attachments = row.get('attachment_urls', [])
    
    if not current_attachments:
        return False
    
    # 깨진 파일명이 있는지 확인
    has_broken = False
    for file_info in current_attachments:
        if is_filename_broken(file_info.get('display_filename', '')):
            has_broken = True
            break
    
    if not has_broken:
        return False
    
    # HTML에서 정확한 파일명 추출
    new_files = extract_filename_from_html(pblanc_id)
    
    if not new_files:
        return False
    
    # 기존 첨부파일과 매칭하여 업데이트
    updated = False
    for i, attachment in enumerate(current_attachments):
        # URL에서 atchFileId와 fileSn 추출
        url = attachment.get('url', '')
        
        for new_file in new_files:
            if new_file['atchFileId'] in url and new_file['fileSn'] in url:
                # 파일명 업데이트
                attachment['display_filename'] = new_file['filename']
                attachment['original_filename'] = new_file['filename']
                attachment['type'] = new_file['type']
                updated = True
                break
        
        # URL 매칭 실패시 순서대로 매칭
        if not updated and i < len(new_files):
            attachment['display_filename'] = new_files[i]['filename']
            attachment['original_filename'] = new_files[i]['filename']
            attachment['type'] = new_files[i]['type']
            updated = True
    
    if updated:
        try:
            supabase.table('bizinfo_complete').update({
                'attachment_urls': json.dumps(current_attachments, ensure_ascii=False)
            }).eq('pblanc_id', pblanc_id).execute()
            return True
        except:
            return False
    
    return False

def main():
    print("="*60)
    print("🔧 BizInfo 파일명 HTML 재크롤링")
    print("📝 div.file_name에서 정확한 파일명 추출")
    print(f"시작 시간: {datetime.now()}")
    print("="*60)
    
    # 깨진 파일명 패턴
    broken_patterns = ['Ã', 'Â', 'ì', 'í', 'ë', 'ã', 'ð', 'þ', 'ï', '¿', '½']
    
    # 깨진 파일명이 있는 데이터 조회
    print("\n1. 문제 데이터 조회 중...")
    
    # 모든 데이터 조회
    response = supabase.table('bizinfo_complete').select(
        'pblanc_id,attachment_urls'
    ).not_.is_('attachment_urls', 'null').execute()
    
    if not response.data:
        print("데이터를 가져올 수 없습니다.")
        return
    
    # 깨진 파일명이 있는 공고 필터링
    problem_announcements = []
    for row in response.data:
        if row.get('attachment_urls'):
            attachments_str = json.dumps(row['attachment_urls'])
            if any(pattern in attachments_str for pattern in broken_patterns):
                problem_announcements.append(row)
    
    print(f"깨진 파일명이 있는 공고: {len(problem_announcements)}개")
    
    if not problem_announcements:
        print("✅ 수정할 파일이 없습니다!")
        return
    
    # 처리
    print(f"\n2. HTML 재크롤링 시작 ({len(problem_announcements)}개)...")
    
    success_count = 0
    fail_count = 0
    
    # 배치 처리 (10개씩)
    batch_size = 10
    for i in range(0, len(problem_announcements), batch_size):
        batch = problem_announcements[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(problem_announcements) + batch_size - 1) // batch_size
        
        print(f"\n배치 {batch_num}/{total_batches} 처리 중...")
        
        for row in batch:
            if process_announcement(row):
                success_count += 1
                print(f"  ✅ 성공: {row['pblanc_id']}")
            else:
                fail_count += 1
            
            # 서버 부하 방지
            time.sleep(0.5)
        
        # 배치 간 휴식
        if i + batch_size < len(problem_announcements):
            print(f"  배치 {batch_num} 완료. 잠시 대기...")
            time.sleep(2)
    
    # 최종 결과 확인
    print("\n3. 결과 확인 중...")
    
    # 다시 조회하여 남은 깨진 파일명 확인
    response = supabase.table('bizinfo_complete').select(
        'pblanc_id,attachment_urls'
    ).not_.is_('attachment_urls', 'null').limit(1000).execute()
    
    remaining_broken = 0
    if response.data:
        for row in response.data:
            if row.get('attachment_urls'):
                attachments_str = json.dumps(row['attachment_urls'])
                if any(pattern in attachments_str for pattern in broken_patterns):
                    remaining_broken += 1
    
    print(f"\n📊 최종 결과:")
    print(f"  - 처리 대상: {len(problem_announcements)}개")
    print(f"  - 성공: {success_count}개")
    print(f"  - 실패: {fail_count}개")
    print(f"  - 남은 깨진 파일명: {remaining_broken}개 (샘플 1000개 기준)")
    
    if remaining_broken == 0:
        print("\n🎉 모든 파일명 문제가 해결되었습니다!")
    else:
        print(f"\n⚠️ 일부 파일명이 여전히 문제가 있을 수 있습니다.")
    
    print(f"\n완료 시간: {datetime.now()}")
    print("="*60)

if __name__ == "__main__":
    main()
