#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
attachment_urls 수집률 검증 및 보고
"""

import os
import json
from supabase import create_client
from datetime import datetime

# Supabase 연결
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')

print("📊 Attachment URLs 수집률 검증")
print("=" * 80)
print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

supabase = create_client(url, key)

# 전체 통계
print("📈 전체 수집 현황")
print("-" * 60)

try:
    # 전체 레코드
    all_records = supabase.table('bizinfo_complete').select('id').execute()
    total = len(all_records.data) if all_records.data else 0
    
    # attachment_urls 있는 레코드
    with_attachments = supabase.table('bizinfo_complete')\
        .select('id, attachment_urls')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .not_.is_('attachment_urls', 'null')\
        .execute()
    
    with_count = 0
    total_files = 0
    
    if with_attachments.data:
        for record in with_attachments.data:
            att = record.get('attachment_urls', '')
            if att:
                try:
                    parsed = json.loads(att) if isinstance(att, str) else att
                    if isinstance(parsed, list) and len(parsed) > 0:
                        with_count += 1
                        total_files += len(parsed)
                except:
                    pass
    
    empty_count = total - with_count
    collection_rate = (with_count / total * 100) if total > 0 else 0
    
    print(f"전체 레코드: {total}개")
    print(f"첨부파일 있음: {with_count}개 ({collection_rate:.1f}%)")
    print(f"첨부파일 없음: {empty_count}개 ({100-collection_rate:.1f}%)")
    print(f"총 첨부파일 수: {total_files}개")
    print(f"평균 첨부파일: {total_files/with_count:.1f}개/레코드" if with_count > 0 else "N/A")
    
    # 상태별 분포
    print("\n📊 처리 상태별 분포")
    print("-" * 60)
    
    statuses = ['completed', 'pending', 'error', 'processing']
    for status in statuses:
        status_records = supabase.table('bizinfo_complete')\
            .select('id')\
            .eq('attachment_processing_status', status)\
            .execute()
        count = len(status_records.data) if status_records.data else 0
        print(f"{status}: {count}개")
    
    # 딕셔너리 형식 status 확인 (문제 있는 레코드)
    print("\n⚠️ 문제 있는 레코드")
    print("-" * 60)
    
    problem_records = supabase.table('bizinfo_complete')\
        .select('id, attachment_processing_status')\
        .like('attachment_processing_status', '%{%')\
        .limit(10)\
        .execute()
    
    if problem_records.data:
        print(f"딕셔너리 형식 status: {len(problem_records.data)}개 발견")
        for rec in problem_records.data[:3]:
            print(f"  ID {rec['id']}: {str(rec['attachment_processing_status'])[:50]}...")
    else:
        print("✅ 딕셔너리 형식 status 없음")
    
    # 최근 성공 사례
    print("\n✅ 최근 수집 성공 (최근 5개)")
    print("-" * 60)
    
    recent_success = supabase.table('bizinfo_complete')\
        .select('id, pblanc_nm, attachment_urls, updated_at')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .order('updated_at', desc=True)\
        .limit(5)\
        .execute()
    
    if recent_success.data:
        for rec in recent_success.data:
            att_count = 0
            try:
                att = json.loads(rec['attachment_urls']) if isinstance(rec['attachment_urls'], str) else rec['attachment_urls']
                att_count = len(att) if isinstance(att, list) else 0
            except:
                pass
            print(f"ID {rec['id']}: {att_count}개 파일 - {rec['pblanc_nm'][:30]}...")
    
    # 결과 평가
    print("\n" + "=" * 80)
    print("📋 평가 결과")
    print("=" * 80)
    
    if collection_rate >= 80:
        print(f"🟢 우수: {collection_rate:.1f}% 수집률")
    elif collection_rate >= 60:
        print(f"🟡 양호: {collection_rate:.1f}% 수집률 (개선 필요)")
    else:
        print(f"🔴 미흡: {collection_rate:.1f}% 수집률 (즉시 조치 필요)")
    
    print("\n💡 권장사항:")
    if empty_count > 100:
        print(f"• {empty_count}개 레코드의 attachment_urls 수집 필요")
    if len(problem_records.data) if problem_records.data else 0 > 0:
        print(f"• 딕셔너리 형식 status 수정 필요")
    if collection_rate < 80:
        print("• BizInfo 워크플로우 재실행 권장")

except Exception as e:
    print(f"❌ 검증 오류: {e}")

print("\n✅ 검증 완료")
