#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BizInfo attachment_urls 데이터 타입 정규화 스크립트
- 문자열로 저장된 attachment_urls를 JSON 배열로 변환
- 모든 데이터를 일관된 형식으로 정리
"""

import os
import json
from datetime import datetime
from supabase import create_client, Client

# Supabase 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main():
    print("="*60)
    print("🔧 BizInfo attachment_urls 데이터 타입 정규화")
    print(f"시작 시간: {datetime.now()}")
    print("="*60)
    
    print("\n1. 데이터 조회 중...")
    
    # 모든 attachment_urls 데이터 조회
    response = supabase.table('bizinfo_complete').select(
        'pblanc_id,attachment_urls'
    ).not_.is_('attachment_urls', 'null').execute()
    
    if not response.data:
        print("데이터를 가져올 수 없습니다.")
        return
    
    print(f"전체 데이터: {len(response.data)}개")
    
    # 문자열로 저장된 데이터 찾기
    string_data = []
    broken_data = []
    normal_data = 0
    
    for row in response.data:
        attachments = row.get('attachment_urls')
        pblanc_id = row['pblanc_id']
        
        if attachments is None:
            continue
        
        # 문자열인 경우
        if isinstance(attachments, str):
            try:
                # JSON 파싱 시도
                parsed = json.loads(attachments)
                if isinstance(parsed, list):
                    string_data.append({
                        'pblanc_id': pblanc_id,
                        'parsed': parsed
                    })
                else:
                    broken_data.append(pblanc_id)
            except:
                broken_data.append(pblanc_id)
        
        # 이미 리스트인 경우
        elif isinstance(attachments, list):
            normal_data += 1
        
        # 기타 이상한 타입
        else:
            broken_data.append(pblanc_id)
    
    print(f"\n분석 결과:")
    print(f"  - 정상 (리스트): {normal_data}개")
    print(f"  - 문자열로 저장됨: {len(string_data)}개")
    print(f"  - 파싱 불가: {len(broken_data)}개")
    
    if not string_data and not broken_data:
        print("\n✅ 모든 데이터가 정상입니다!")
        return
    
    # 문자열 데이터 수정
    if string_data:
        print(f"\n2. 문자열 데이터 수정 중... ({len(string_data)}개)")
        
        success_count = 0
        for item in string_data:
            try:
                # JSON 배열로 업데이트
                supabase.table('bizinfo_complete').update({
                    'attachment_urls': item['parsed']
                }).eq('pblanc_id', item['pblanc_id']).execute()
                
                success_count += 1
                
                if success_count % 100 == 0:
                    print(f"  진행: {success_count}/{len(string_data)}")
                    
            except Exception as e:
                print(f"  ❌ 업데이트 실패 ({item['pblanc_id']}): {e}")
        
        print(f"  ✅ 수정 완료: {success_count}/{len(string_data)}")
    
    # 파싱 불가 데이터 처리
    if broken_data:
        print(f"\n3. 파싱 불가 데이터 처리... ({len(broken_data)}개)")
        
        for pblanc_id in broken_data[:10]:  # 처음 10개만 출력
            print(f"  - {pblanc_id}: 빈 배열로 초기화")
        
        # 빈 배열로 초기화
        for pblanc_id in broken_data:
            try:
                supabase.table('bizinfo_complete').update({
                    'attachment_urls': []
                }).eq('pblanc_id', pblanc_id).execute()
            except:
                pass
    
    # 결과 확인
    print("\n4. 최종 확인...")
    
    response = supabase.table('bizinfo_complete').select(
        'attachment_urls'
    ).not_.is_('attachment_urls', 'null').limit(100).execute()
    
    string_count = 0
    for row in response.data:
        if isinstance(row.get('attachment_urls'), str):
            string_count += 1
    
    print(f"\n📊 최종 결과:")
    print(f"  - 샘플 100개 중 문자열: {string_count}개")
    
    if string_count == 0:
        print("\n🎉 모든 attachment_urls가 정규화되었습니다!")
    else:
        print("\n⚠️ 일부 데이터가 여전히 문자열입니다.")
    
    print(f"\n완료 시간: {datetime.now()}")
    print("="*60)

if __name__ == "__main__":
    main()
