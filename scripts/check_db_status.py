#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 상태 확인 스크립트
특정 레코드 PBLN_000000000113724 확인 포함
"""

import os
import json
from supabase import create_client

# Supabase 연결
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

print(f"📡 Supabase URL: {url}")
print("=" * 80)

supabase = create_client(url, key)

# BizInfo 테이블 확인
print("\n📙 BizInfo 테이블 상태")
print("-" * 60)

try:
    # 전체 레코드 수
    total = supabase.table('bizinfo_complete').select('id', count='exact').execute()
    print(f"전체 레코드: {len(total.data)}개")
    
    # attachment_urls 있는 레코드
    with_att = supabase.table('bizinfo_complete')\
        .select('id')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .limit(100)\
        .execute()
    print(f"attachment_urls 있음: {len(with_att.data)}개")
    
    # 특정 레코드 확인
    print("\n📌 특정 레코드: PBLN_000000000113724")
    specific = supabase.table('bizinfo_complete')\
        .select('pblanc_id, pblanc_nm, attachment_urls, attachment_processing_status')\
        .eq('pblanc_id', 'PBLN_000000000113724')\
        .execute()
    
    if specific.data:
        record = specific.data[0]
        print(f"  공고명: {record.get('pblanc_nm', 'N/A')[:40]}...")
        
        att_urls = record.get('attachment_urls', '')
        if att_urls and att_urls != '[]':
            try:
                parsed = json.loads(att_urls) if isinstance(att_urls, str) else att_urls
                print(f"  첨부파일: {len(parsed)}개")
                for att in parsed[:3]:
                    if isinstance(att, dict):
                        print(f"    • {att.get('extension', 'unknown')} - {att.get('filename', 'N/A')[:30]}")
            except:
                print(f"  첨부파일: 파싱 오류")
        else:
            print(f"  첨부파일: ❌ 없음")
            
            # 첨부파일이 없으면 업데이트
            print("\n🔧 첨부파일 정보 추가 중...")
            new_attachments = [
                {
                    "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000726241&fileSn=0",
                    "filename": "붙임3._R&D_과제기획지원_일정표.hwp",
                    "extension": "hwp"
                },
                {
                    "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000726241&fileSn=1",
                    "filename": "붙임2._지원신청서.hwp",
                    "extension": "hwp"
                },
                {
                    "url": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_000000000726210&fileSn=0",
                    "filename": "붙임1._2025년도_R&D과제기획_신청_공고문.hwp",
                    "extension": "hwp"
                }
            ]
            
            update = supabase.table('bizinfo_complete')\
                .update({
                    'attachment_urls': json.dumps(new_attachments, ensure_ascii=False),
                    'attachment_count': 3,
                    'attachment_processing_status': 'completed'
                })\
                .eq('pblanc_id', 'PBLN_000000000113724')\
                .execute()
            
            if update.data:
                print("  ✅ 첨부파일 정보 추가 완료!")
    else:
        print("  ❌ 레코드를 찾을 수 없음")
    
    # 최근 업데이트된 레코드
    print("\n⏰ 최근 업데이트 (attachment_urls 있는 것)")
    recent = supabase.table('bizinfo_complete')\
        .select('pblanc_id, pblanc_nm, attachment_urls, updated_at')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .order('updated_at', desc=True)\
        .limit(5)\
        .execute()
    
    for r in recent.data:
        att = r.get('attachment_urls', '')
        if att:
            try:
                parsed = json.loads(att) if isinstance(att, str) else att
                count = len(parsed) if isinstance(parsed, list) else 0
            except:
                count = 0
            print(f"  • {r['pblanc_nm'][:30]}... - {count}개 첨부파일")
    
except Exception as e:
    print(f"❌ 오류: {e}")

print("\n✅ 확인 완료")
