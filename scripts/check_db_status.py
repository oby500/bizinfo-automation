#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 상태 확인 스크립트
특정 레코드 PBLN_000000000113724 확인 포함
"""

import os
import sys
import json
from supabase import create_client

print("🔍 데이터베이스 상태 확인")
print("=" * 80)

# Supabase 연결
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')

print(f"📡 Supabase URL: {url[:30]}..." if url else "❌ URL 없음")
print(f"🔑 API Key: {'설정됨' if key else '❌ 없음'}")

if not url or not key:
    print("\n❌ 환경변수가 설정되지 않음")
    print("필요한 환경변수:")
    print("  - SUPABASE_URL")
    print("  - SUPABASE_KEY 또는 SUPABASE_SERVICE_KEY")
    sys.exit(1)

try:
    supabase = create_client(url, key)
    print("✅ Supabase 연결 성공")
except Exception as e:
    print(f"❌ Supabase 연결 실패: {e}")
    sys.exit(1)

# BizInfo 테이블 확인
print("\n📙 BizInfo 테이블 상태")
print("-" * 60)

try:
    # 전체 레코드 수
    total = supabase.table('bizinfo_complete').select('id', count='exact').limit(1).execute()
    total_count = len(total.data) if total.data else 0
    print(f"테이블 접근: ✅ 성공")
    
    # 전체 카운트를 위한 별도 쿼리
    count_result = supabase.table('bizinfo_complete').select('id').execute()
    actual_count = len(count_result.data) if count_result.data else 0
    print(f"전체 레코드: {actual_count}개")
    
    # attachment_urls 있는 레코드
    with_att = supabase.table('bizinfo_complete')\
        .select('id')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .not_.is_('attachment_urls', 'null')\
        .limit(100)\
        .execute()
    with_count = len(with_att.data) if with_att.data else 0
    print(f"attachment_urls 있음: {with_count}개")
    
    # attachment_urls 비어있는 레코드
    empty_att = supabase.table('bizinfo_complete')\
        .select('id')\
        .or_('attachment_urls.eq.,attachment_urls.eq.[]')\
        .limit(100)\
        .execute()
    empty_count = len(empty_att.data) if empty_att.data else 0
    print(f"attachment_urls 비어있음: {empty_count}개")
    
    # 특정 레코드 확인
    print("\n📌 특정 레코드: PBLN_000000000113724")
    print("-" * 60)
    
    specific = supabase.table('bizinfo_complete')\
        .select('pblanc_id, pblanc_nm, attachment_urls, attachment_processing_status, atch_file_url')\
        .eq('pblanc_id', 'PBLN_000000000113724')\
        .execute()
    
    if specific.data and len(specific.data) > 0:
        record = specific.data[0]
        print(f"✅ 레코드 발견!")
        print(f"  공고명: {record.get('pblanc_nm', 'N/A')[:40]}...")
        
        # attachment_urls 확인
        att_urls = record.get('attachment_urls', '')
        if att_urls and att_urls != '' and att_urls != '[]':
            try:
                parsed = json.loads(att_urls) if isinstance(att_urls, str) else att_urls
                if isinstance(parsed, list) and len(parsed) > 0:
                    print(f"  첨부파일: ✅ {len(parsed)}개")
                    for i, att in enumerate(parsed[:3], 1):
                        if isinstance(att, dict):
                            ext = att.get('extension', 'unknown')
                            filename = att.get('filename', 'N/A')
                            print(f"    {i}. {ext} - {filename[:30]}...")
                else:
                    print(f"  첨부파일: ❌ 비어있음")
            except Exception as e:
                print(f"  첨부파일: ❌ 파싱 오류 - {e}")
        else:
            print(f"  첨부파일: ❌ 없음 (빈 문자열 또는 빈 배열)")
            
            # atch_file_url 확인
            atch_url = record.get('atch_file_url', '')
            if atch_url:
                print(f"  atch_file_url: ✅ {atch_url[:50]}...")
            
            # 첨부파일이 없으면 업데이트
            print("\n🔧 첨부파일 정보 추가 시도...")
            new_attachments = [
                {
                    "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000726241&fileSn=0",
                    "filename": "붙임3._R&D_과제기획지원_일정표.hwp",
                    "extension": "hwp",
                    "status": "available"
                },
                {
                    "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000726241&fileSn=1",
                    "filename": "붙임2._지원신청서.hwp",
                    "extension": "hwp",
                    "status": "available"
                },
                {
                    "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000726210&fileSn=0",
                    "filename": "붙임1._2025년도_R&D과제기획_신청_공고문.hwp",
                    "extension": "hwp",
                    "status": "available"
                }
            ]
            
            try:
                update = supabase.table('bizinfo_complete')\
                    .update({
                        'attachment_urls': json.dumps(new_attachments, ensure_ascii=False),
                        'attachment_count': 3,
                        'attachment_processing_status': 'completed'
                    })\
                    .eq('pblanc_id', 'PBLN_000000000113724')\
                    .execute()
                
                if update.data:
                    print("  ✅ 첨부파일 정보 추가 완료! (3개 파일)")
                else:
                    print("  ❌ 업데이트 실패")
            except Exception as e:
                print(f"  ❌ 업데이트 오류: {e}")
        
        # 처리 상태 확인
        status = record.get('attachment_processing_status', '')
        if isinstance(status, dict):
            print(f"  처리상태: ⚠️ 딕셔너리 형식 (수정 필요)")
        else:
            print(f"  처리상태: {status}")
    else:
        print("  ❌ 레코드를 찾을 수 없음")
    
    # 최근 업데이트된 레코드
    print("\n⏰ 최근 업데이트 (attachment_urls 있는 것)")
    print("-" * 60)
    
    recent = supabase.table('bizinfo_complete')\
        .select('pblanc_id, pblanc_nm, attachment_urls, updated_at')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .not_.is_('attachment_urls', 'null')\
        .order('updated_at', desc=True)\
        .limit(5)\
        .execute()
    
    if recent.data:
        for r in recent.data:
            att = r.get('attachment_urls', '')
            count = 0
            if att:
                try:
                    parsed = json.loads(att) if isinstance(att, str) else att
                    count = len(parsed) if isinstance(parsed, list) else 0
                except:
                    count = 0
            updated = r.get('updated_at', 'N/A')[:19]
            print(f"  • {r['pblanc_nm'][:30]}...")
            print(f"    첨부: {count}개 | 업데이트: {updated}")
    else:
        print("  attachment_urls가 있는 레코드가 없음")
    
except Exception as e:
    print(f"❌ 테이블 접근 오류: {e}")
    import traceback
    traceback.print_exc()

# K-Startup 테이블도 확인
print("\n📘 K-Startup 테이블 상태")
print("-" * 60)

try:
    # 테이블 존재 확인
    k_test = supabase.table('kstartup_complete').select('id').limit(1).execute()
    print(f"테이블 접근: ✅ 성공")
    
    # 전체 레코드
    k_total = supabase.table('kstartup_complete').select('id').execute()
    k_total_count = len(k_total.data) if k_total.data else 0
    print(f"전체 레코드: {k_total_count}개")
    
    # attachment_urls 있는 레코드
    k_with = supabase.table('kstartup_complete')\
        .select('id')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .not_.is_('attachment_urls', 'null')\
        .limit(100)\
        .execute()
    k_with_count = len(k_with.data) if k_with.data else 0
    print(f"attachment_urls 있음: {k_with_count}개")
    
except Exception as e:
    print(f"❌ K-Startup 테이블 접근 오류: {e}")

print("\n" + "=" * 80)
print("✅ 데이터베이스 상태 확인 완료")
