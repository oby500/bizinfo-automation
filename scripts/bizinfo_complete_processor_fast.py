#!/usr/bin/env python3
"""
기업마당 첨부파일 고속 처리 스크립트
- ThreadPoolExecutor로 병렬 처리
- 배치 업데이트로 DB 부하 감소
- 세션 재사용으로 네트워크 최적화
"""

import os
import json
import hashlib
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from supabase import create_client
from typing import List, Dict, Any

# Supabase 클라이언트 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("환경변수 오류: SUPABASE_URL 또는 SUPABASE_SERVICE_KEY가 설정되지 않았습니다.")
    exit(1)

supabase = create_client(url, key)

# 세션 재사용
session = requests.Session()

def generate_safe_filename(original_filename: str, announcement_id: str, index: int) -> str:
    """안전한 파일명 생성"""
    # 확장자 추출
    if '.' in original_filename:
        ext = original_filename.split('.')[-1].lower()
    else:
        ext = 'unknown'
    
    # 안전한 파일명: PBLN_{공고ID}_{순번}.{확장자}
    safe_name = f"PBLN_{announcement_id}_{index:02d}.{ext}"
    return safe_name

def process_single_announcement(item: Dict[str, Any]) -> Dict[str, Any]:
    """단일 공고 처리"""
    try:
        announcement_id = item.get('pblancId', '')
        attachment_urls = item.get('attachment_urls', [])
        
        if not attachment_urls or not isinstance(attachment_urls, list):
            return None
        
        updated_attachments = []
        has_changes = False
        
        for idx, attachment in enumerate(attachment_urls, 1):
            if isinstance(attachment, dict):
                # 이미 safe_filename이 있으면 스킵
                if attachment.get('safe_filename'):
                    updated_attachments.append(attachment)
                    continue
                
                # 새로운 safe_filename 생성
                original_name = attachment.get('filename', f'attachment_{idx}')
                safe_name = generate_safe_filename(original_name, announcement_id, idx)
                
                attachment['safe_filename'] = safe_name
                attachment['display_filename'] = original_name
                updated_attachments.append(attachment)
                has_changes = True
        
        if has_changes:
            return {
                'id': item['id'],
                'attachment_urls': updated_attachments,
                'attachment_count': len(updated_attachments),
                'attachment_processing_status': {
                    'processed': True,
                    'processed_at': datetime.now().isoformat(),
                    'safe_filename_added': True
                }
            }
        
        return None
        
    except Exception as e:
        print(f"처리 오류 (ID: {item.get('id', 'unknown')}): {e}")
        return None

def batch_update_database(updates: List[Dict[str, Any]]):
    """배치로 데이터베이스 업데이트"""
    if not updates:
        return
    
    try:
        for update in updates:
            supabase.table('bizinfo_complete').update({
                'attachment_urls': update['attachment_urls'],
                'attachment_count': update['attachment_count'],
                'attachment_processing_status': update['attachment_processing_status']
            }).eq('id', update['id']).execute()
        
        print(f"✅ {len(updates)}개 레코드 업데이트 완료")
    except Exception as e:
        print(f"❌ 배치 업데이트 실패: {e}")

def main():
    print("="*60)
    print("   기업마당 첨부파일 고속 처리 시작")
    print("="*60)
    
    # 처리 대상 조회
    print("\n1. 처리 대상 조회 중...")
    
    # safe_filename이 없는 데이터 조회
    response = supabase.table('bizinfo_complete')\
        .select('id,pblancId,attachment_urls')\
        .neq('attachment_urls', '[]')\
        .execute()
    
    if not response.data:
        print("처리할 데이터가 없습니다.")
        return
    
    # safe_filename이 없는 데이터만 필터링
    items_to_process = []
    for item in response.data:
        if item.get('attachment_urls'):
            # safe_filename이 없는 항목 확인
            needs_processing = False
            for att in item['attachment_urls']:
                if isinstance(att, dict) and not att.get('safe_filename'):
                    needs_processing = True
                    break
            
            if needs_processing:
                items_to_process.append(item)
    
    total_count = len(items_to_process)
    print(f"처리 대상: {total_count}개")
    
    if total_count == 0:
        print("모든 데이터가 이미 처리되었습니다.")
        return
    
    # 병렬 처리
    print(f"\n2. 병렬 처리 시작 (Workers: 5)...")
    
    updates = []
    processed_count = 0
    batch_size = 20
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_single_announcement, item): item 
                  for item in items_to_process}
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                updates.append(result)
                processed_count += 1
                
                # 배치 크기에 도달하면 업데이트
                if len(updates) >= batch_size:
                    batch_update_database(updates)
                    updates = []
                
                # 진행상황 표시
                if processed_count % 10 == 0:
                    print(f"진행: {processed_count}/{total_count} ({processed_count*100/total_count:.1f}%)")
    
    # 남은 업데이트 처리
    if updates:
        batch_update_database(updates)
    
    # 최종 통계
    print("\n" + "="*60)
    print("   처리 완료")
    print("="*60)
    print(f"✅ 총 처리: {processed_count}개")
    print(f"⏱️ 예상 시간: {total_count * 0.5:.1f}초 (병렬 처리)")
    
    # Unknown 확장자 통계
    unknown_response = supabase.table('bizinfo_complete')\
        .select('attachment_urls')\
        .neq('attachment_urls', '[]')\
        .execute()
    
    unknown_count = 0
    if unknown_response.data:
        for item in unknown_response.data:
            for att in item.get('attachment_urls', []):
                if isinstance(att, dict) and att.get('safe_filename', '').endswith('.unknown'):
                    unknown_count += 1
    
    if unknown_count > 0:
        print(f"⚠️ Unknown 확장자: {unknown_count}개 (추가 처리 필요)")
    else:
        print("✅ 모든 파일 확장자 정상")

if __name__ == "__main__":
    main()
