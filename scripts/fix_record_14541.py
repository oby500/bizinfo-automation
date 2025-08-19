#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
레코드 14541 (PBLN_000000000113724) 직접 수정
"""

import os
import json
from supabase import create_client

# Supabase 연결
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')

print("🔧 레코드 14541 직접 수정")
print("=" * 80)

supabase = create_client(url, key)

# 레코드 확인 및 수정
pblanc_id = "PBLN_000000000113724"
record_id = 14541

try:
    # 현재 상태 확인
    current = supabase.table('bizinfo_complete')\
        .select('*')\
        .eq('id', record_id)\
        .execute()
    
    if current.data:
        record = current.data[0]
        print(f"✅ 레코드 발견: {record.get('pblanc_nm', 'N/A')[:50]}...")
        
        # 실제 첨부파일 정보 (웹페이지에서 확인)
        attachments = [
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
        
        # 업데이트
        update_data = {
            'attachment_urls': json.dumps(attachments, ensure_ascii=False),
            'attachment_count': len(attachments),
            'attachment_processing_status': 'completed',
            'atch_file_url': 'https://www.bizinfo.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000726241&fileSn=0',
            'updated_at': 'now()'
        }
        
        result = supabase.table('bizinfo_complete')\
            .update(update_data)\
            .eq('id', record_id)\
            .execute()
        
        if result.data:
            print(f"✅ 레코드 14541 수정 완료!")
            print(f"   - {len(attachments)}개 첨부파일 추가")
            print(f"   - status: completed")
            
            # 확인
            check = supabase.table('bizinfo_complete')\
                .select('attachment_urls, attachment_processing_status')\
                .eq('id', record_id)\
                .execute()
            
            if check.data:
                att = check.data[0].get('attachment_urls', '')
                if att and att != '[]':
                    print(f"✅ 검증 완료: attachment_urls가 정상적으로 설정됨")
                else:
                    print(f"❌ 검증 실패: attachment_urls가 여전히 비어있음")
        else:
            print("❌ 업데이트 실패")
    else:
        print(f"❌ 레코드 {record_id}를 찾을 수 없음")
        
except Exception as e:
    print(f"❌ 오류: {e}")

print("\n" + "=" * 80)
print("✅ 작업 완료")
