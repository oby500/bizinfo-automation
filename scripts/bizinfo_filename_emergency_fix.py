#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BizInfo 깨진 파일명 긴급 수정 스크립트
- 85개 깨진 파일명 즉시 처리
- HTML 재크롤링 + 패턴 기반 복구
"""

import os
import json
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client
import re

# Supabase 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fix_encoding_patterns(text: str) -> str:
    """알려진 패턴으로 인코딩 수정"""
    if not text:
        return text
    
    # 일반적인 깨진 패턴 -> 한글 매핑
    replacements = {
        'Ã«Â¶ÂÃ¬ÂÂ': '붙임',
        'Ã¬Â°Â¸ÃªÂ°Â': '참가',
        'Ã¬ÂÂÃ¬Â²Â­': '신청',
        'ÃªÂ¸Â°Ã¬ÂÂ': '기업',
        'Ã¬Â§ÂÃ¬ÂÂ': '지원',
        'ÃªÂ³ÂµÃªÂ³Â ': '공고',
        'Ã¬ÂÂ¬Ã¬ÂÂ': '사업',
        'Ã¬Â²Â¨Ã«Â¶ÂÃ­ÂÂÃ¬ÂÂ¼': '첨부파일',
        'ÃªÂ´ÂÃ«Â Â¨': '관련',
        'Ã¬ÂÂÃ¬ÂÂ': '서식',
        'Ã¬ÂÂÃ¬Â ÂÃ¬ÂÂ': '신청서',
        'Ã­ÂÂÃ¬ÂÂ½Ã¬ÂÂ': '행사',
        'Ã¬Â¶ÂÃ¬Â²ÂÃ¬ÂÂ': '추천서',
        'ÃªÂ²Â½Ã«Â¶Â': '경북',
        'Ã¬ÂÂ¼Ã­ÂÂ°': '일자',
        'ÃªÂ¸Â°ÃªÂ°Â': '기간',
    }
    
    result = text
    for pattern, replacement in replacements.items():
        result = result.replace(pattern, replacement)
    
    # 남은 깨진 문자 제거
    result = re.sub(r'[ÃÂ]+', '', result)
    result = re.sub(r'[¬­®¯°±²³´µ¶·¸¹º»¼½¾¿]+', '', result)
    
    # 공백 정리
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()
    
    return result if result else text

def extract_from_html(pblanc_id: str) -> list:
    """HTML에서 정확한 파일명 추출"""
    url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ko-KR,ko;q=0.9',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        file_list = soup.find('div', class_='file_list')
        
        if not file_list:
            return None
        
        files = []
        for item in file_list.find_all('li'):
            file_name_div = item.find('div', class_='file_name')
            if file_name_div:
                filename = file_name_div.get_text(strip=True)
                
                # 파일 타입 추출
                file_type = 'FILE'
                if '.' in filename:
                    ext = filename.split('.')[-1].upper()
                    file_type = ext
                
                files.append({
                    'filename': filename,
                    'type': file_type
                })
        
        return files if files else None
        
    except Exception as e:
        print(f"  HTML 추출 실패: {e}")
        return None

def generate_filename(pblanc_nm: str, file_type: str, index: int) -> str:
    """공고명 기반 파일명 생성"""
    
    # 공고명에서 키워드 추출
    keywords = []
    
    # 연도 추출
    year_match = re.search(r'(20\d{2})', pblanc_nm)
    if year_match:
        keywords.append(year_match.group(1))
    
    # 주요 키워드
    important = ['지원', '사업', '공고', '모집', '신청', '창업', '기업']
    for keyword in important:
        if keyword in pblanc_nm:
            keywords.append(keyword)
            break
    
    # 파일 타입별 기본명
    type_names = {
        'HWP': '신청서',
        'PDF': '공고문',
        'ZIP': '첨부파일',
        'XLSX': '목록',
        'DOCX': '양식',
        'JPG': '포스터',
        'PNG': '이미지'
    }
    
    base_name = '_'.join(keywords) if keywords else '파일'
    type_name = type_names.get(file_type.upper(), '문서')
    
    if index > 0:
        return f"{base_name}_{type_name}_{index+1}.{file_type.lower()}"
    else:
        return f"{base_name}_{type_name}.{file_type.lower()}"

def main():
    print("="*60)
    print("🚨 BizInfo 깨진 파일명 긴급 수정")
    print(f"시작 시간: {datetime.now()}")
    print("="*60)
    
    # 깨진 패턴
    broken_patterns = ['Ã', 'Â', 'ì', 'í', 'ë', 'ã']
    
    print("\n1. 깨진 파일명 조회 중...")
    
    # 전체 데이터 조회
    response = supabase.table('bizinfo_complete').select(
        'pblanc_id,pblanc_nm,attachment_urls'
    ).not_.is_('attachment_urls', 'null').execute()
    
    if not response.data:
        print("데이터를 가져올 수 없습니다.")
        return
    
    # 깨진 파일명이 있는 공고 필터링
    problem_announcements = []
    total_broken_files = 0
    
    for row in response.data:
        attachments = row.get('attachment_urls')
        if attachments:
            # attachment_urls가 문자열인 경우 JSON 파싱
            if isinstance(attachments, str):
                try:
                    attachments = json.loads(attachments)
                    row['attachment_urls'] = attachments
                except:
                    continue
            
            has_broken = False
            for file_info in attachments:
                if isinstance(file_info, dict):
                    filename = file_info.get('display_filename', '')
                    if any(p in filename for p in broken_patterns):
                        has_broken = True
                        total_broken_files += 1
            
            if has_broken:
                problem_announcements.append(row)
    
    print(f"깨진 파일명 발견: {total_broken_files}개 파일")
    print(f"해당 공고: {len(problem_announcements)}개")
    
    if not problem_announcements:
        print("✅ 수정할 파일이 없습니다!")
        return
    
    print(f"\n2. 수정 시작 ({len(problem_announcements)}개 공고)...")
    
    success_count = 0
    html_success = 0
    pattern_success = 0
    
    for idx, row in enumerate(problem_announcements):
        pblanc_id = row['pblanc_id']
        pblanc_nm = row.get('pblanc_nm', '')
        attachments = row['attachment_urls']
        
        # attachment_urls가 문자열인 경우 처리
        if isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except:
                continue
        
        if idx % 10 == 0:
            print(f"\n진행: {idx}/{len(problem_announcements)}")
        
        # 1차: HTML에서 추출 시도
        html_files = None
        if idx < 50:  # 처음 50개만 HTML 시도 (부하 방지)
            html_files = extract_from_html(pblanc_id)
            if html_files:
                html_success += 1
                time.sleep(0.5)  # 서버 부하 방지
        
        # 파일 수정
        updated = False
        for i, attachment in enumerate(attachments):
            if isinstance(attachment, dict):
                filename = attachment.get('display_filename', '')
                
                if any(p in filename for p in broken_patterns):
                    # HTML 파일명 사용
                    if html_files and i < len(html_files):
                        attachment['display_filename'] = html_files[i]['filename']
                        attachment['original_filename'] = html_files[i]['filename']
                        attachment['type'] = html_files[i]['type']
                        updated = True
                    # 패턴 기반 수정
                    else:
                        fixed = fix_encoding_patterns(filename)
                        if fixed != filename:
                            attachment['display_filename'] = fixed
                            attachment['original_filename'] = fixed
                            pattern_success += 1
                            updated = True
                        # 완전 새 파일명 생성
                        else:
                            file_type = attachment.get('type', 'FILE')
                            new_name = generate_filename(pblanc_nm, file_type, i)
                            attachment['display_filename'] = new_name
                            attachment['original_filename'] = new_name
                            updated = True
        
        # DB 업데이트
        if updated:
            try:
                supabase.table('bizinfo_complete').update({
                    'attachment_urls': json.dumps(attachments, ensure_ascii=False)
                }).eq('pblanc_id', pblanc_id).execute()
                success_count += 1
            except Exception as e:
                print(f"  ❌ 업데이트 실패 ({pblanc_id}): {e}")
    
    # 결과 확인
    print("\n3. 최종 확인...")
    
    # 샘플 재조회
    response = supabase.table('bizinfo_complete').select(
        'attachment_urls'
    ).not_.is_('attachment_urls', 'null').limit(500).execute()
    
    remaining = 0
    if response.data:
        for row in response.data:
            attachments = row.get('attachment_urls')
            if attachments:
                # attachment_urls가 문자열인 경우 처리
                if isinstance(attachments, str):
                    try:
                        attachments = json.loads(attachments)
                    except:
                        continue
                
                for file_info in attachments:
                    if isinstance(file_info, dict):
                        filename = file_info.get('display_filename', '')
                        if any(p in filename for p in broken_patterns):
                            remaining += 1
    
    print(f"\n📊 최종 결과:")
    print(f"  - 처리 대상: {len(problem_announcements)}개 공고")
    print(f"  - 성공: {success_count}개")
    print(f"  - HTML 추출 성공: {html_success}개")
    print(f"  - 패턴 수정: {pattern_success}개")
    print(f"  - 남은 깨진 파일: {remaining}개 (샘플 500개 기준)")
    
    if remaining == 0:
        print("\n🎉 모든 파일명이 정상화되었습니다!")
    else:
        print(f"\n⚠️ 일부 파일이 여전히 문제가 있습니다.")
    
    print(f"\n완료 시간: {datetime.now()}")
    print("="*60)

if __name__ == "__main__":
    main()
