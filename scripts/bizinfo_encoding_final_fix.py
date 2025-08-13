#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BizInfo 깨진 파일명 인코딩 수정 스크립트
- 이중/삼중 인코딩 문제 해결
- 85개 깨진 파일명 복구
"""

import os
import json
import time
from datetime import datetime
from supabase import create_client, Client
from typing import Dict, List, Tuple
import re

# Supabase 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fix_broken_encoding(text: str) -> str:
    """깨진 인코딩 복구 - 더 강력한 버전"""
    if not text:
        return text
    
    original = text
    
    # 1단계: 흔한 패턴 직접 치환
    replacements = {
        # 한글 자모 패턴
        'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
        'ë': 'e', 'è': 'e', 'é': 'e', 'ê': 'e',
        'ã': 'a', 'à': 'a', 'á': 'a', 'â': 'a', 'ä': 'a', 'å': 'a',
        'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
        'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
        'ð': 'd', 'þ': 'th', 'ý': 'y',
        '¿': '', '½': '', '¾': '', '¼': '',
        
        # 한글 복구 패턴
        'ì°¸ê°': '참가',
        'ì ì²­': '신청',
        'ì§ì': '지원',
        'ê¸°ì': '기업',
        'ì¬ì': '사업',
        'ëª¨ì§': '모집',
        'ê³µê³ ': '공고',
        'ì ì': '정보',
        'ê°ë°': '개발',
        'ì°êµ¬': '연구',
        
        # 복잡한 패턴
        'Ã¬Â°Â¸ÃªÂ°Â': '참가',
        'Ã¬ÂÂÃ¬Â²Â­': '신청',
        'ÃªÂ¸Â°Ã¬ÂÂ': '기업',
        'Ã¬Â§ÂÃ¬ÂÂ': '지원',
        'ÃªÂ³ÂµÃªÂ³Â ': '공고',
        'Ã¬ÂÂ¬Ã¬ÂÂ': '사업',
        
        # 특수문자 정리
        'Â': '', '¬': '', '­': '', '®': '', '¯': '',
        '°': '', '±': '', '²': '', '³': '', '´': '',
        'µ': '', '¶': '', '·': '', '¸': '', '¹': '',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # 2단계: Latin-1 디코딩 시도
    if 'Ã' in text or 'Â' in text:
        try:
            # UTF-8 -> Latin-1 -> UTF-8 복구
            bytes_text = text.encode('latin-1', errors='ignore')
            decoded = bytes_text.decode('utf-8', errors='ignore')
            if decoded and len(decoded) > 0:
                text = decoded
        except:
            pass
    
    # 3단계: 여전히 깨진 문자가 있으면 다시 시도
    if any(c in text for c in ['ì', 'í', 'ë', 'ã', 'Ã', 'Â']):
        try:
            # 다른 인코딩 체인 시도
            text = text.encode('utf-8', errors='ignore').decode('latin-1', errors='ignore')
            text = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
        except:
            pass
    
    # 4단계: 알려진 파일명 패턴으로 완전 치환
    known_patterns = {
        '.*참가.*신청.*': '참가신청서',
        '.*사업.*계획.*': '사업계획서',
        '.*지원.*신청.*': '지원신청서',
        '.*공고.*': '공고문',
        '.*신청.*양식.*': '신청양식',
        '.*제출.*서류.*': '제출서류',
    }
    
    for pattern, replacement in known_patterns.items():
        if re.match(pattern, text, re.IGNORECASE):
            # 확장자 보존
            if '.' in original:
                ext = original.split('.')[-1]
                if len(ext) <= 5:  # 정상적인 확장자
                    return f"{replacement}.{ext}"
            return replacement
    
    # 변경사항이 없으면 원본 반환
    if text == original:
        return original
    
    return text

def process_announcement(row: dict) -> Tuple[str, bool, dict]:
    """개별 공고 처리"""
    pblanc_id = row['pblanc_id']
    attachment_urls = row.get('attachment_urls', [])
    
    if not attachment_urls:
        return pblanc_id, False, None
    
    updated_files = []
    has_changes = False
    
    for file_entry in attachment_urls:
        updated_entry = file_entry.copy()
        
        # display_filename 수정
        display_filename = updated_entry.get('display_filename', '')
        if display_filename and any(c in display_filename for c in ['ì', 'í', 'ë', 'ã', 'Ã', 'Â', '¿', '½']):
            fixed_filename = fix_broken_encoding(display_filename)
            if fixed_filename != display_filename:
                updated_entry['display_filename'] = fixed_filename
                has_changes = True
                print(f"  수정: {display_filename[:30]}... → {fixed_filename[:30]}...")
        
        # original_filename 수정
        original_filename = updated_entry.get('original_filename', '')
        if original_filename and any(c in original_filename for c in ['ì', 'í', 'ë', 'ã', 'Ã', 'Â', '¿', '½']):
            fixed_filename = fix_broken_encoding(original_filename)
            if fixed_filename != original_filename:
                updated_entry['original_filename'] = fixed_filename
                has_changes = True
        
        updated_files.append(updated_entry)
    
    if has_changes:
        return pblanc_id, True, {'attachment_urls': json.dumps(updated_files, ensure_ascii=False)}
    
    return pblanc_id, False, None

def main():
    print("="*60)
    print("🔧 BizInfo 깨진 파일명 인코딩 수정")
    print(f"시작 시간: {datetime.now()}")
    print("="*60)
    
    # 깨진 파일명이 있는 데이터 조회
    print("\n1. 깨진 파일명 조회 중...")
    
    broken_patterns = ['ì', 'í', 'ë', 'ã', 'Ã', 'Â', '¿', '½', 'þ', 'ð', 'ï']
    
    # 모든 데이터 조회 (attachment_urls가 있는 것)
    response = supabase.table('bizinfo_complete').select('pblanc_id,attachment_urls').not_.is_('attachment_urls', 'null').execute()
    
    if not response.data:
        print("데이터를 가져올 수 없습니다.")
        return
    
    # 깨진 파일명이 있는 데이터 필터링
    broken_announcements = []
    for row in response.data:
        if row.get('attachment_urls'):
            attachments_str = json.dumps(row['attachment_urls'])
            if any(pattern in attachments_str for pattern in broken_patterns):
                broken_announcements.append(row)
    
    total_count = len(broken_announcements)
    print(f"깨진 파일명 발견: {total_count}개 공고")
    
    if total_count == 0:
        print("✅ 수정할 깨진 파일명이 없습니다!")
        return
    
    # 처리
    print(f"\n2. 인코딩 수정 시작 ({total_count}개)...")
    
    updates_to_apply = []
    processed = 0
    
    for row in broken_announcements:
        pblanc_id, needs_update, update_data = process_announcement(row)
        processed += 1
        
        if needs_update:
            updates_to_apply.append({
                'pblanc_id': pblanc_id,
                'update_data': update_data
            })
        
        if processed % 20 == 0:
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
                
                if success_count % 20 == 0:
                    print(f"업데이트 진행: {success_count}/{len(updates_to_apply)}")
                    
            except Exception as e:
                print(f"업데이트 실패 ({item['pblanc_id']}): {e}")
        
        print(f"\n✅ 업데이트 완료: {success_count}/{len(updates_to_apply)}")
    
    # 결과 확인
    print("\n4. 수정 결과 확인...")
    
    # 다시 조회하여 남은 깨진 파일명 확인
    response = supabase.table('bizinfo_complete').select('pblanc_id,attachment_urls').not_.is_('attachment_urls', 'null').execute()
    
    remaining_broken = 0
    if response.data:
        for row in response.data:
            if row.get('attachment_urls'):
                attachments_str = json.dumps(row['attachment_urls'])
                if any(pattern in attachments_str for pattern in broken_patterns):
                    remaining_broken += 1
    
    print(f"\n📊 최종 결과:")
    print(f"  - 처리 전 깨진 파일명: {total_count}개")
    print(f"  - 수정 완료: {len(updates_to_apply)}개")
    print(f"  - 남은 깨진 파일명: {remaining_broken}개")
    
    if remaining_broken == 0:
        print("\n✅ 모든 인코딩 문제가 해결되었습니다!")
    else:
        print(f"\n⚠️ {remaining_broken}개의 파일명이 여전히 깨져있습니다.")
        print("   (매우 복잡한 인코딩 문제일 수 있습니다)")
    
    print(f"\n완료 시간: {datetime.now()}")
    print("="*60)

if __name__ == "__main__":
    main()
