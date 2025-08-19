#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기업마당 레코드 14541 상세 확인
"""

import os
import json
import requests
from supabase import create_client

# Supabase 연결
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')

print(f"🔍 레코드 14541 상세 분석")
print("=" * 80)

supabase = create_client(url, key)

# 1. 레코드 ID로 조회 (숫자 ID)
print("\n📌 ID로 조회")
print("-" * 60)

try:
    result_by_id = supabase.table('bizinfo_complete')\
        .select('*')\
        .eq('id', 14541)\
        .execute()
    
    if result_by_id.data:
        record = result_by_id.data[0]
        print(f"✅ ID 14541 레코드 발견!")
        print(f"   공고ID: {record.get('pblanc_id', 'N/A')}")
        print(f"   공고명: {record.get('pblanc_nm', 'N/A')[:50]}...")
        
        # attachment_urls 상태 확인
        att_urls = record.get('attachment_urls', '')
        print(f"\n📎 attachment_urls 상태:")
        if att_urls and att_urls != '[]' and att_urls != '':
            try:
                parsed = json.loads(att_urls) if isinstance(att_urls, str) else att_urls
                if isinstance(parsed, list) and len(parsed) > 0:
                    print(f"   ✅ {len(parsed)}개 첨부파일:")
                    for i, att in enumerate(parsed[:3], 1):
                        if isinstance(att, dict):
                            filename = att.get('filename', 'N/A')
                            ext = att.get('extension', 'unknown')
                            print(f"      {i}. {ext} - {filename[:40]}...")
                else:
                    print(f"   ❌ 빈 배열: {att_urls}")
            except Exception as e:
                print(f"   ❌ 파싱 오류: {e}")
        else:
            print(f"   ❌ 비어있음: '{att_urls}'")
        
        # atch_file_url 확인
        atch_url = record.get('atch_file_url', '')
        print(f"\n📎 atch_file_url: {atch_url[:80] if atch_url else '없음'}...")
        
        # 처리 상태
        status = record.get('attachment_processing_status', '')
        print(f"\n📊 처리상태: {status}")
        
        # 업데이트 시간
        updated = record.get('updated_at', '')
        print(f"\n⏰ 마지막 업데이트: {updated}")
        
        # atch_file_url이 있으면 실제 웹페이지 확인
        if atch_url:
            print(f"\n🌐 웹페이지 첨부파일 확인 중...")
            pblanc_id = record.get('pblanc_id', '')
            if pblanc_id:
                web_url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}"
                print(f"   웹페이지: {web_url}")
                
                # 웹페이지 크롤링으로 실제 첨부파일 확인
                try:
                    import requests
                    from bs4 import BeautifulSoup
                    
                    response = requests.get(web_url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # 첨부파일 링크 찾기
                        file_links = soup.find_all('a', href=True)
                        attachments_found = []
                        
                        for link in file_links:
                            href = link.get('href', '')
                            if 'getImageFile.do' in href or 'download' in href.lower():
                                text = link.get_text(strip=True)
                                if text and len(text) > 3:
                                    attachments_found.append({
                                        'url': href,
                                        'text': text[:50]
                                    })
                        
                        if attachments_found:
                            print(f"   ✅ 웹페이지에서 {len(attachments_found)}개 첨부파일 발견:")
                            for i, att in enumerate(attachments_found[:5], 1):
                                print(f"      {i}. {att['text']}...")
                        else:
                            print(f"   ❌ 웹페이지에서 첨부파일을 찾을 수 없음")
                    else:
                        print(f"   ❌ 웹페이지 접근 실패: {response.status_code}")
                        
                except Exception as e:
                    print(f"   ❌ 웹페이지 크롤링 오류: {e}")
        
    else:
        print(f"❌ ID {record_id}로 레코드를 찾을 수 없음")
        
        # 비슷한 ID들 검색
        print("\n🔍 비슷한 레코드 검색")
        similar = supabase.table('bizinfo_complete')\
            .select('id, pblanc_id, pblanc_nm')\
            .gte('id', 14541 - 5)\
            .lte('id', 14541 + 5)\
            .execute()
        
        if similar.data:
            for rec in similar.data:
                print(f"   ID {rec['id']}: {rec.get('pblanc_nm', 'N/A')[:40]}...")

except Exception as e:
    print(f"❌ 조회 오류: {e}")

# 2. 전체 테이블에서 attachment_urls 수집 현황
print("\n📊 전체 attachment_urls 수집 현황")
print("-" * 60)

try:
    # 전체 레코드 수
    total = supabase.table('bizinfo_complete').select('id', count='exact').execute()
    total_count = len(total.data) if total.data else 0
    
    # attachment_urls 있는 레코드
    with_att = supabase.table('bizinfo_complete')\
        .select('id')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .not_.is_('attachment_urls', 'null')\
        .execute()
    with_count = len(with_att.data) if with_att.data else 0
    
    # 비어있는 레코드
    empty_count = total_count - with_count
    
    print(f"전체 레코드: {total_count}개")
    print(f"attachment_urls 있음: {with_count}개 ({with_count/total_count*100:.1f}%)")
    print(f"attachment_urls 없음: {empty_count}개 ({empty_count/total_count*100:.1f}%)")
    
    # 최근 업데이트된 레코드 중 attachment_urls 있는 것
    print("\n⏰ 최근 수집 성공 사례")
    recent_success = supabase.table('bizinfo_complete')\
        .select('id, pblanc_nm, attachment_urls, updated_at')\
        .neq('attachment_urls', '')\
        .neq('attachment_urls', '[]')\
        .not_.is_('attachment_urls', 'null')\
        .order('updated_at', desc=True)\
        .limit(3)\
        .execute()
    
    if recent_success.data:
        for rec in recent_success.data:
            att_count = 0
            try:
                att = json.loads(rec['attachment_urls']) if isinstance(rec['attachment_urls'], str) else rec['attachment_urls']
                att_count = len(att) if isinstance(att, list) else 0
            except:
                pass
            print(f"   ID {rec['id']}: {att_count}개 첨부파일 - {rec['updated_at'][:19]}")

except Exception as e:
    print(f"❌ 현황 조회 오류: {e}")

print("\n" + "=" * 80)
print("✅ 분석 완료")
