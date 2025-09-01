#!/usr/bin/env python3
"""
현재 첨부파일 데이터 상태 확인
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from dotenv import load_dotenv
from supabase import create_client
import json

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

def check_attachment_status():
    """첨부파일 데이터 현황 확인"""
    print("="*70)
    print("📊 전체 첨부파일 데이터 현황 (K-Startup + BizInfo)")
    print("="*70)
    
    # K-Startup 데이터
    print("\n🎯 K-Startup 현황:")
    ks_total = supabase.table('kstartup_complete')\
        .select('id', count='exact')\
        .execute()
    
    ks_with_attachments = supabase.table('kstartup_complete')\
        .select('id', count='exact')\
        .gt('attachment_count', 0)\
        .execute()
    
    print(f"   전체 공고: {ks_total.count}개")
    print(f"   첨부파일 있음: {ks_with_attachments.count}개")
    print(f"   첨부파일 없음: {ks_total.count - ks_with_attachments.count}개")
    
    # BizInfo 데이터
    print("\n🏢 BizInfo (기업마당) 현황:")
    bi_total = supabase.table('bizinfo_complete')\
        .select('id', count='exact')\
        .execute()
    
    bi_with_attachments = supabase.table('bizinfo_complete')\
        .select('id', count='exact')\
        .not_.is_('attachment_urls', 'null')\
        .execute()
    
    print(f"   전체 공고: {bi_total.count}개")
    print(f"   첨부파일 있음: {bi_with_attachments.count}개")
    print(f"   첨부파일 없음: {bi_total.count - bi_with_attachments.count}개")
    
    print(f"\n📊 전체 통계:")
    print(f"   총 공고: {ks_total.count + bi_total.count}개")
    print(f"   총 첨부파일 있음: {ks_with_attachments.count + bi_with_attachments.count}개")
    
    # K-Startup 타입 분석
    print(f"\n🔍 K-Startup 첨부파일 타입 분석 (샘플 100개):")
    
    ks_sample = supabase.table('kstartup_complete')\
        .select('announcement_id, attachment_urls')\
        .gt('attachment_count', 0)\
        .limit(100)\
        .execute()
    
    ks_type_counts = {}
    ks_total_files = 0
    ks_records_with_file_type = 0
    
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
        
        has_file_type = False
        for att in attachments:
            file_type = att.get('type', 'UNKNOWN')
            if file_type == 'FILE':
                has_file_type = True
            ks_type_counts[file_type] = ks_type_counts.get(file_type, 0) + 1
            ks_total_files += 1
        
        if has_file_type:
            ks_records_with_file_type += 1
    
    print(f"   분석된 파일: {ks_total_files}개")
    print(f"   타입별 분포:")
    for file_type, count in sorted(ks_type_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / ks_total_files * 100) if ks_total_files > 0 else 0
        print(f"   - {file_type}: {count}개 ({percentage:.1f}%)")
    
    # BizInfo 타입 분석
    print(f"\n🔍 BizInfo 첨부파일 타입 분석 (샘플 100개):")
    
    bi_sample = supabase.table('bizinfo_complete')\
        .select('announcement_id, attachment_urls')\
        .not_.is_('attachment_urls', 'null')\
        .limit(100)\
        .execute()
    
    bi_type_counts = {}
    bi_total_files = 0
    bi_records_with_file_type = 0
    
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
        
        has_file_type = False
        for att in attachments:
            file_type = att.get('type', 'UNKNOWN')
            if file_type == 'FILE':
                has_file_type = True
            bi_type_counts[file_type] = bi_type_counts.get(file_type, 0) + 1
            bi_total_files += 1
        
        if has_file_type:
            bi_records_with_file_type += 1
    
    print(f"   분석된 파일: {bi_total_files}개")
    print(f"   타입별 분포:")
    for file_type, count in sorted(bi_type_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / bi_total_files * 100) if bi_total_files > 0 else 0
        print(f"   - {file_type}: {count}개 ({percentage:.1f}%)")
    
    print(f"\n⚠️  재수집 필요 레코드:")
    print(f"   K-Startup 'FILE' 타입: {ks_records_with_file_type}개 / {len(ks_sample.data)}개 샘플")
    print(f"   K-Startup 예상 재수집: 약 {int(ks_with_attachments.count * (ks_records_with_file_type/len(ks_sample.data)) if len(ks_sample.data) > 0 else 0)}개")
    print(f"   BizInfo 'FILE' 타입: {bi_records_with_file_type}개 / {len(bi_sample.data) if bi_sample.data else 0}개 샘플")
    print(f"   BizInfo 예상 재수집: 약 {int(bi_with_attachments.count * (bi_records_with_file_type/len(bi_sample.data)) if bi_sample.data and len(bi_sample.data) > 0 else 0)}개")
    
    # 최근 수정된 레코드 확인
    print(f"\n📅 최근 업데이트된 레코드 (정확한 타입 있는지 확인):")
    
    print("\nK-Startup 최근 레코드:")
    ks_recent = supabase.table('kstartup_complete')\
        .select('announcement_id, biz_pbanc_nm, attachment_urls, created_at')\
        .gt('attachment_count', 0)\
        .order('created_at', desc=True)\
        .limit(3)\
        .execute()
    
    for record in ks_recent.data:
        print(f"   {record['announcement_id']}: {record.get('biz_pbanc_nm', 'No Title')[:30]}...")
        attachment_urls = record.get('attachment_urls')
        if attachment_urls:
            try:
                if isinstance(attachment_urls, str):
                    attachments = json.loads(attachment_urls)
                else:
                    attachments = attachment_urls
                
                types = {}
                for att in attachments:
                    t = att.get('type', 'UNKNOWN')
                    types[t] = types.get(t, 0) + 1
                
                print(f"      타입: {types}")
            except:
                print(f"      타입: 파싱 실패")
    
    print("\nBizInfo 최근 레코드:")
    bi_recent = supabase.table('bizinfo_complete')\
        .select('announcement_id, pblanc_nm, attachment_urls, created_at')\
        .not_.is_('attachment_urls', 'null')\
        .order('created_at', desc=True)\
        .limit(3)\
        .execute()
    
    for record in bi_recent.data:
        print(f"   {record['announcement_id']}: {record.get('pblanc_nm', 'No Title')[:30]}...")
        attachment_urls = record.get('attachment_urls')
        if attachment_urls:
            try:
                if isinstance(attachment_urls, str):
                    attachments = json.loads(attachment_urls)
                else:
                    attachments = attachment_urls
                
                types = {}
                for att in attachments:
                    t = att.get('type', 'UNKNOWN')
                    types[t] = types.get(t, 0) + 1
                
                print(f"      타입: {types}")
            except:
                print(f"      타입: 파싱 실패")

def main():
    """메인 실행"""
    check_attachment_status()
    
    print("\n" + "="*70)
    print("💡 권장사항:")
    print("="*70)
    print("1. K-Startup + BizInfo 전체 첨부파일 재수집 필요")
    print("2. 파일 타입 정확히 감지 (FILE → 정확한 타입)")
    print("3. 병렬 처리로 속도 향상 (30개 동시 실행)")
    print("4. 재수집 후 HWP/HWPX 파일만 PDF 변환")

if __name__ == "__main__":
    main()