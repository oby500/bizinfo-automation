#!/usr/bin/env python3
"""
첨부파일 수집 정밀도 검증 스크립트
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
import random

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
})

def verify_attachment_types():
    """FILE 타입이 남아있는지 확인"""
    print("="*70)
    print("📊 1. FILE 타입 잔존 확인")
    print("="*70)
    
    # K-Startup에서 FILE 타입 확인 (전체 조회 후 필터링)
    ks_all = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, attachment_urls')\
        .gt('attachment_count', 0)\
        .limit(1000)\
        .execute()
    
    ks_with_file_data = []
    for record in ks_all.data:
        attachment_urls = record.get('attachment_urls')
        if attachment_urls:
            try:
                if isinstance(attachment_urls, str):
                    if '"type":"FILE"' in attachment_urls:
                        ks_with_file_data.append(record)
                else:
                    attachments = attachment_urls
                    for att in attachments:
                        if att.get('type') == 'FILE':
                            ks_with_file_data.append(record)
                            break
            except:
                pass
    
    ks_with_file = type('obj', (object,), {'data': ks_with_file_data})
    
    print(f"\n🎯 K-Startup:")
    print(f"   FILE 타입 있는 레코드: {len(ks_with_file.data)}개")
    
    if ks_with_file.data:
        print("\n   샘플 (최대 5개):")
        for record in ks_with_file.data[:5]:
            print(f"   - {record['announcement_id']}: {record.get('biz_pbanc_nm', 'No Title')[:30]}...")
            attachment_urls = record.get('attachment_urls')
            if attachment_urls:
                try:
                    if isinstance(attachment_urls, str):
                        attachments = json.loads(attachment_urls)
                    else:
                        attachments = attachment_urls
                    
                    file_types = [att.get('type') for att in attachments]
                    print(f"     타입들: {file_types}")
                except:
                    pass
    
    # BizInfo에서 FILE 타입 확인 (전체 조회 후 필터링)
    bi_all = supabase.table('bizinfo_complete')\
        .select('announcement_id, pblanc_nm, attachment_urls')\
        .not_.is_('attachment_urls', 'null')\
        .limit(1000)\
        .execute()
    
    bi_with_file_data = []
    for record in bi_all.data:
        attachment_urls = record.get('attachment_urls')
        if attachment_urls:
            try:
                if isinstance(attachment_urls, str):
                    if '"type":"FILE"' in attachment_urls:
                        bi_with_file_data.append(record)
                else:
                    attachments = attachment_urls
                    for att in attachments:
                        if att.get('type') == 'FILE':
                            bi_with_file_data.append(record)
                            break
            except:
                pass
    
    bi_with_file = type('obj', (object,), {'data': bi_with_file_data})
    
    print(f"\n🏢 BizInfo:")
    print(f"   FILE 타입 있는 레코드: {len(bi_with_file.data)}개")
    
    if bi_with_file.data:
        print("\n   샘플 (최대 5개):")
        for record in bi_with_file.data[:5]:
            print(f"   - {record.get('announcement_id', 'N/A')}: {record.get('pblanc_nm', 'No Title')[:30]}...")
            attachment_urls = record.get('attachment_urls')
            if attachment_urls:
                try:
                    if isinstance(attachment_urls, str):
                        attachments = json.loads(attachment_urls)
                    else:
                        attachments = attachment_urls
                    
                    file_types = [att.get('type') for att in attachments]
                    print(f"     타입들: {file_types}")
                except:
                    pass
    
    return len(ks_with_file.data), len(bi_with_file.data)

def verify_type_distribution():
    """전체 파일 타입 분포 확인"""
    print("\n" + "="*70)
    print("📊 2. 전체 파일 타입 분포")
    print("="*70)
    
    # K-Startup 전체 타입 분포
    print("\n🎯 K-Startup 파일 타입 분포:")
    ks_sample = supabase.table('kstartup_complete')\
        .select('attachment_urls')\
        .gt('attachment_count', 0)\
        .limit(500)\
        .execute()
    
    ks_type_counts = {}
    ks_total_files = 0
    
    for record in ks_sample.data:
        attachment_urls = record.get('attachment_urls')
        if not attachment_urls:
            continue
            
        try:
            if isinstance(attachment_urls, str):
                attachments = json.loads(attachment_urls)
            else:
                attachments = attachment_urls
        except:
            continue
        
        for att in attachments:
            file_type = att.get('type', 'UNKNOWN')
            ks_type_counts[file_type] = ks_type_counts.get(file_type, 0) + 1
            ks_total_files += 1
    
    print(f"   분석된 파일: {ks_total_files}개 (500개 레코드)")
    for file_type, count in sorted(ks_type_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / ks_total_files * 100) if ks_total_files > 0 else 0
        print(f"   - {file_type}: {count}개 ({percentage:.1f}%)")
    
    # BizInfo 전체 타입 분포
    print("\n🏢 BizInfo 파일 타입 분포:")
    bi_sample = supabase.table('bizinfo_complete')\
        .select('attachment_urls')\
        .not_.is_('attachment_urls', 'null')\
        .limit(500)\
        .execute()
    
    bi_type_counts = {}
    bi_total_files = 0
    
    for record in bi_sample.data:
        attachment_urls = record.get('attachment_urls')
        if not attachment_urls:
            continue
            
        try:
            if isinstance(attachment_urls, str):
                attachments = json.loads(attachment_urls)
            else:
                attachments = attachment_urls
        except:
            continue
        
        for att in attachments:
            file_type = att.get('type', 'UNKNOWN')
            bi_type_counts[file_type] = bi_type_counts.get(file_type, 0) + 1
            bi_total_files += 1
    
    print(f"   분석된 파일: {bi_total_files}개 (500개 레코드)")
    for file_type, count in sorted(bi_type_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / bi_total_files * 100) if bi_total_files > 0 else 0
        print(f"   - {file_type}: {count}개 ({percentage:.1f}%)")
    
    return ks_type_counts, bi_type_counts

def random_spot_check():
    """무작위 샘플링으로 실제 파일 타입 검증"""
    print("\n" + "="*70)
    print("📊 3. 무작위 샘플 정밀 검증")
    print("="*70)
    
    # K-Startup 무작위 5개 선택
    print("\n🎯 K-Startup 무작위 검증:")
    ks_random = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, attachment_urls, detl_pg_url')\
        .gt('attachment_count', 0)\
        .limit(200)\
        .execute()
    
    if ks_random.data:
        # 무작위로 5개 선택
        random_samples = random.sample(ks_random.data, min(5, len(ks_random.data)))
        
        for i, record in enumerate(random_samples, 1):
            print(f"\n   샘플 {i}: {record['announcement_id']}")
            print(f"   제목: {record.get('biz_pbanc_nm', 'No Title')[:40]}...")
            
            attachment_urls = record.get('attachment_urls')
            if attachment_urls:
                try:
                    if isinstance(attachment_urls, str):
                        attachments = json.loads(attachment_urls)
                    else:
                        attachments = attachment_urls
                    
                    print(f"   저장된 첨부파일: {len(attachments)}개")
                    for j, att in enumerate(attachments[:3], 1):
                        print(f"     {j}. 타입: {att.get('type')} | 이름: {att.get('text', 'N/A')[:30]}...")
                        
                        # 실제 파일 시그니처 확인 (첫 번째 파일만)
                        if j == 1 and att.get('url'):
                            try:
                                response = session.get(att['url'], stream=True, timeout=5)
                                chunk = response.raw.read(100)
                                
                                actual_type = 'UNKNOWN'
                                if chunk[:4] == b'%PDF':
                                    actual_type = 'PDF'
                                elif chunk[:8] == b'\x89PNG\r\n\x1a\n':
                                    actual_type = 'IMAGE(PNG)'
                                elif chunk[:2] == b'\xff\xd8':
                                    actual_type = 'IMAGE(JPG)'
                                elif b'HWP Document' in chunk:
                                    actual_type = 'HWP'
                                elif chunk[:2] == b'PK':
                                    actual_type = 'ZIP/OFFICE'
                                
                                stored_type = att.get('type')
                                match = "✅" if actual_type.startswith(stored_type) or stored_type in actual_type else "❌"
                                print(f"        실제 타입: {actual_type} {match}")
                                response.close()
                            except:
                                print(f"        실제 타입: 확인 실패")
                except:
                    print(f"   첨부파일 파싱 실패")

def calculate_accuracy():
    """정확도 계산"""
    print("\n" + "="*70)
    print("📊 4. 수집 정확도 요약")
    print("="*70)
    
    # K-Startup 통계
    ks_total = supabase.table('kstartup_complete')\
        .select('id', count='exact')\
        .execute()
    
    ks_with_attachments = supabase.table('kstartup_complete')\
        .select('id', count='exact')\
        .gt('attachment_count', 0)\
        .execute()
    
    # FILE 타입 검색 (샘플링으로 추정)
    ks_sample_for_file = supabase.table('kstartup_complete')\
        .select('attachment_urls')\
        .gt('attachment_count', 0)\
        .limit(500)\
        .execute()
    
    ks_file_count = 0
    for record in ks_sample_for_file.data:
        attachment_urls = record.get('attachment_urls')
        if attachment_urls:
            try:
                if isinstance(attachment_urls, str):
                    if '"type":"FILE"' in attachment_urls:
                        ks_file_count += 1
                else:
                    attachments = attachment_urls
                    for att in attachments:
                        if att.get('type') == 'FILE':
                            ks_file_count += 1
                            break
            except:
                pass
    
    # 비율로 전체 추정
    ks_file_estimated = int((ks_file_count / len(ks_sample_for_file.data)) * ks_with_attachments.count) if ks_sample_for_file.data else 0
    ks_with_file = type('obj', (object,), {'count': ks_file_estimated})
    
    ks_accuracy = ((ks_with_attachments.count - ks_with_file.count) / ks_with_attachments.count * 100) if ks_with_attachments.count > 0 else 0
    
    print(f"\n🎯 K-Startup:")
    print(f"   전체 공고: {ks_total.count}개")
    print(f"   첨부파일 있음: {ks_with_attachments.count}개")
    print(f"   FILE 타입 있음: {ks_with_file.count}개")
    print(f"   정확도: {ks_accuracy:.1f}% (FILE 타입 제외)")
    
    # BizInfo 통계
    bi_total = supabase.table('bizinfo_complete')\
        .select('id', count='exact')\
        .execute()
    
    bi_with_attachments = supabase.table('bizinfo_complete')\
        .select('id', count='exact')\
        .not_.is_('attachment_urls', 'null')\
        .execute()
    
    bi_with_file = supabase.table('bizinfo_complete')\
        .select('id', count='exact')\
        .like('attachment_urls', '%"type":"FILE"%')\
        .execute()
    
    bi_accuracy = ((bi_with_attachments.count - bi_with_file.count) / bi_with_attachments.count * 100) if bi_with_attachments.count > 0 else 0
    
    print(f"\n🏢 BizInfo:")
    print(f"   전체 공고: {bi_total.count}개")
    print(f"   첨부파일 있음: {bi_with_attachments.count}개")
    print(f"   FILE 타입 있음: {bi_with_file.count}개")
    print(f"   정확도: {bi_accuracy:.1f}% (FILE 타입 제외)")
    
    overall_accuracy = ((ks_with_attachments.count + bi_with_attachments.count - ks_with_file.count - bi_with_file.count) / 
                       (ks_with_attachments.count + bi_with_attachments.count) * 100) if (ks_with_attachments.count + bi_with_attachments.count) > 0 else 0
    
    print(f"\n📈 전체 정확도: {overall_accuracy:.1f}%")
    
    if overall_accuracy < 100:
        print(f"\n⚠️  개선 필요:")
        print(f"   - FILE 타입 파일: 약 {ks_with_file.count + bi_with_file.count}개")
        print(f"   - 재수집 권장")

def main():
    """메인 실행"""
    print("="*70)
    print("🔍 첨부파일 수집 정밀도 검증")
    print("="*70)
    
    # 1. FILE 타입 확인
    ks_file_count, bi_file_count = verify_attachment_types()
    
    # 2. 타입 분포 확인
    verify_type_distribution()
    
    # 3. 무작위 샘플 검증
    random_spot_check()
    
    # 4. 정확도 계산
    calculate_accuracy()
    
    print("\n" + "="*70)
    print("✅ 검증 완료")
    print("="*70)

if __name__ == "__main__":
    main()