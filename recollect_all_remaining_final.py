#!/usr/bin/env python3
"""
모든 첨부파일 재수집 (페이지네이션 포함) - 100% 정확도 달성
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from supabase import create_client
from dotenv import load_dotenv
import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# HTTP 세션 설정
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
})

def detect_file_type_by_signature(url, filename=''):
    """파일 시그니처로 정확한 타입 감지"""
    try:
        # 파일명 기반 사전 필터링
        filename_lower = filename.lower()
        
        # 한글 파일은 특별 처리
        if '한글' in filename or filename_lower.endswith(('.hwp', '.hwpx')):
            if '.hwpx' in filename_lower:
                return 'HWPX', 'hwpx'
            return 'HWP', 'hwp'
        
        # 이미지 파일 확장자 체크
        if filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            ext = filename_lower.split('.')[-1]
            if ext in ['jpg', 'jpeg']:
                return 'JPG', 'jpg'
            elif ext == 'png':
                return 'PNG', 'png'
            return 'IMAGE', ext
        
        # 기타 파일 확장자 체크
        if filename_lower.endswith('.pdf'):
            return 'PDF', 'pdf'
        if filename_lower.endswith('.zip'):
            return 'ZIP', 'zip'
        if filename_lower.endswith('.xlsx'):
            return 'XLSX', 'xlsx'
        if filename_lower.endswith('.xls'):
            return 'XLS', 'xls'
        if filename_lower.endswith('.docx'):
            return 'DOCX', 'docx'
        if filename_lower.endswith('.doc'):
            return 'DOC', 'doc'
        if filename_lower.endswith('.pptx'):
            return 'PPTX', 'pptx'
        if filename_lower.endswith('.ppt'):
            return 'PPT', 'ppt'
        
        # URL에서 실제 다운로드하여 시그니처 확인
        response = session.get(url, stream=True, timeout=10)
        chunk = response.raw.read(1024)
        response.close()
        
        # 파일 시그니처 체크
        if chunk[:4] == b'%PDF':
            return 'PDF', 'pdf'
        elif chunk[:8] == b'\x89PNG\r\n\x1a\n':
            return 'PNG', 'png'
        elif chunk[:2] == b'\xff\xd8':
            return 'JPG', 'jpg'
        elif b'HWP Document' in chunk or chunk[:4] == b'\xd0\xcf\x11\xe0':
            # HWP 문서 시그니처
            return 'HWP', 'hwp'
        elif chunk[:2] == b'PK':
            # ZIP 기반 파일 (DOCX, XLSX, PPTX, HWPX 등)
            if b'word' in chunk.lower():
                return 'DOCX', 'docx'
            elif b'xl/' in chunk or b'excel' in chunk.lower():
                return 'XLSX', 'xlsx'
            elif b'ppt' in chunk.lower():
                return 'PPTX', 'pptx'
            elif filename_lower.endswith('.hwpx'):
                return 'HWPX', 'hwpx'
            return 'ZIP', 'zip'
        
        # 특별 케이스: getImageFile
        if 'getImageFile' in url:
            return 'IMAGE', 'jpg'
        
        return 'FILE', ''
        
    except Exception as e:
        print(f"        타입 감지 실패: {str(e)[:50]}")
        return 'FILE', ''

def process_kstartup_batch(offset=0, limit=1000):
    """K-Startup 배치 처리"""
    print(f"\n📦 K-Startup 배치 처리 (offset: {offset}, limit: {limit})")
    
    # 데이터 조회
    result = supabase.table('kstartup_complete')\
        .select('*')\
        .gt('attachment_count', 0)\
        .range(offset, offset + limit - 1)\
        .execute()
    
    if not result.data:
        return 0
    
    updated_count = 0
    file_count = 0
    
    for record in result.data:
        announcement_id = record['announcement_id']
        attachment_urls = record.get('attachment_urls')
        
        if not attachment_urls:
            continue
        
        # 이미 정확한 타입이 있는지 확인
        try:
            if isinstance(attachment_urls, str):
                attachments = json.loads(attachment_urls)
            else:
                attachments = attachment_urls
        except:
            continue
        
        # FILE 타입이 있는지 확인
        has_file_type = any(att.get('type') == 'FILE' for att in attachments)
        
        if not has_file_type:
            continue  # 이미 정확한 타입이 있음
        
        print(f"\n  🔄 {announcement_id}: {record.get('biz_pbanc_nm', 'No Title')[:30]}...")
        
        # 타입 재감지
        updated_attachments = []
        for att in attachments:
            if att.get('type') == 'FILE':
                # 재감지 필요
                url = att.get('url', '')
                filename = att.get('text', att.get('display_filename', ''))
                
                file_type, file_ext = detect_file_type_by_signature(url, filename)
                
                att['type'] = file_type
                if file_ext:
                    att['file_extension'] = file_ext
                
                file_count += 1
                print(f"      ✅ {filename[:30]}... → {file_type}")
            
            updated_attachments.append(att)
        
        # 데이터베이스 업데이트
        try:
            supabase.table('kstartup_complete')\
                .update({'attachment_urls': json.dumps(updated_attachments, ensure_ascii=False)})\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            updated_count += 1
        except Exception as e:
            print(f"      ❌ 업데이트 실패: {str(e)[:50]}")
    
    print(f"\n  📊 배치 결과: {updated_count}개 업데이트, {file_count}개 파일 타입 수정")
    return updated_count

def process_bizinfo_batch(offset=0, limit=1000):
    """BizInfo 배치 처리"""
    print(f"\n📦 BizInfo 배치 처리 (offset: {offset}, limit: {limit})")
    
    # 데이터 조회
    result = supabase.table('bizinfo_complete')\
        .select('*')\
        .not_.is_('attachment_urls', 'null')\
        .range(offset, offset + limit - 1)\
        .execute()
    
    if not result.data:
        return 0
    
    updated_count = 0
    file_count = 0
    
    for record in result.data:
        announcement_id = record.get('announcement_id', 'N/A')
        attachment_urls = record.get('attachment_urls')
        
        if not attachment_urls:
            continue
        
        # 이미 정확한 타입이 있는지 확인
        try:
            if isinstance(attachment_urls, str):
                attachments = json.loads(attachment_urls)
            else:
                attachments = attachment_urls
        except:
            continue
        
        # FILE 타입이 있는지 확인
        has_file_type = any(att.get('type') == 'FILE' for att in attachments)
        
        if not has_file_type:
            continue  # 이미 정확한 타입이 있음
        
        print(f"\n  🔄 {announcement_id}: {record.get('pblanc_nm', 'No Title')[:30]}...")
        
        # 타입 재감지
        updated_attachments = []
        for att in attachments:
            if att.get('type') == 'FILE':
                # 재감지 필요
                url = att.get('url', '')
                filename = att.get('text', att.get('display_filename', ''))
                
                file_type, file_ext = detect_file_type_by_signature(url, filename)
                
                att['type'] = file_type
                if file_ext:
                    att['file_extension'] = file_ext
                
                file_count += 1
                print(f"      ✅ {filename[:30]}... → {file_type}")
            
            updated_attachments.append(att)
        
        # 데이터베이스 업데이트
        try:
            supabase.table('bizinfo_complete')\
                .update({'attachment_urls': json.dumps(updated_attachments, ensure_ascii=False)})\
                .eq('announcement_id', announcement_id)\
                .execute()
            
            updated_count += 1
        except Exception as e:
            print(f"      ❌ 업데이트 실패: {str(e)[:50]}")
    
    print(f"\n  📊 배치 결과: {updated_count}개 업데이트, {file_count}개 파일 타입 수정")
    return updated_count

def main():
    """메인 실행"""
    print("="*70)
    print("🚀 전체 첨부파일 재수집 (100% 정확도 목표)")
    print("="*70)
    
    start_time = time.time()
    
    # 전체 카운트 확인
    ks_total = supabase.table('kstartup_complete')\
        .select('id', count='exact')\
        .execute()
    
    bi_total = supabase.table('bizinfo_complete')\
        .select('id', count='exact')\
        .execute()
    
    print(f"\n📊 전체 데이터:")
    print(f"   K-Startup: {ks_total.count}개")
    print(f"   BizInfo: {bi_total.count}개")
    print(f"   총계: {ks_total.count + bi_total.count}개")
    
    # K-Startup 전체 처리
    print(f"\n{'='*70}")
    print(f"🎯 K-Startup 처리 시작")
    print(f"{'='*70}")
    
    ks_updated_total = 0
    batch_size = 1000
    
    for offset in range(0, ks_total.count, batch_size):
        updated = process_kstartup_batch(offset, batch_size)
        ks_updated_total += updated
        
        if updated == 0:
            print(f"   스킵: offset {offset} (이미 처리됨)")
    
    print(f"\n✅ K-Startup 처리 완료: 총 {ks_updated_total}개 업데이트")
    
    # BizInfo 전체 처리
    print(f"\n{'='*70}")
    print(f"🏢 BizInfo 처리 시작")
    print(f"{'='*70}")
    
    bi_updated_total = 0
    
    for offset in range(0, bi_total.count, batch_size):
        updated = process_bizinfo_batch(offset, batch_size)
        bi_updated_total += updated
        
        if updated == 0:
            print(f"   스킵: offset {offset} (이미 처리됨)")
    
    print(f"\n✅ BizInfo 처리 완료: 총 {bi_updated_total}개 업데이트")
    
    # 최종 통계
    elapsed_time = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f"📊 최종 결과")
    print(f"{'='*70}")
    print(f"   K-Startup 업데이트: {ks_updated_total}개")
    print(f"   BizInfo 업데이트: {bi_updated_total}개")
    print(f"   총 업데이트: {ks_updated_total + bi_updated_total}개")
    print(f"   소요 시간: {elapsed_time:.1f}초")
    print(f"\n✅ 전체 재수집 완료!")

if __name__ == "__main__":
    main()