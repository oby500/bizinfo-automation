#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
K-Startup 실제 데이터 수집기 (개선된 로직)
- Daily 모드: 연속 50개 중복 시 종료 (구글시트와 동일)
- perPage=200으로 더 많은 데이터 확인
- 페이지 단위 중복 체크로 효율성 개선
"""

import os
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import json
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Supabase 설정
try:
    from supabase import create_client
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ 환경변수 오류: SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다.")
        sys.exit(1)
        
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"✅ Supabase 연결 성공: {SUPABASE_URL[:30]}...")
    
except Exception as e:
    print(f"❌ Supabase 연결 실패: {e}")
    sys.exit(1)

# K-Startup API 설정
API_KEY = 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=='
BASE_URL = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'

# 모드 설정
COLLECTION_MODE = os.getenv('COLLECTION_MODE', 'daily')

def get_existing_ids():
    """기존 데이터의 announcement_id 목록 조회"""
    try:
        result = supabase.table('kstartup_complete').select('announcement_id').execute()
        if result.data:
            existing_ids = set()
            for item in result.data:
                announcement_id = item.get('announcement_id')
                if announcement_id:
                    # 마지막 6자리만 사용 (중복 체크용)
                    existing_ids.add(str(announcement_id)[-6:])
            print(f"📊 기존 데이터: {len(existing_ids)}개 ID (마지막 6자리 기준)")
            return existing_ids
        return set()
    except Exception as e:
        print(f"⚠️ 기존 데이터 조회 실패: {e}")
        return set()

def fetch_kstartup_data(page, per_page=200):
    """K-Startup API에서 데이터 조회"""
    params = {
        'ServiceKey': API_KEY,
        'page': page,
        'perPage': per_page
    }
    
    try:
        print(f"📄 페이지 {page} 요청 중... (perPage={per_page})")
        response = requests.get(BASE_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ HTTP 오류: {response.status_code}")
            return None
            
        # XML 파싱
        root = ET.fromstring(response.content)
        
        # 헤더 확인
        header = root.find('.//header')
        if header is None:
            print("❌ XML 헤더를 찾을 수 없습니다")
            return None
            
        result_code = header.find('resultCode')
        if result_code is None or result_code.text != '00':
            result_msg = header.find('resultMsg')
            error_msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
            print(f"❌ API 오류: {error_msg}")
            return None
        
        # 데이터 추출
        items = root.findall('.//item')
        print(f"   📊 {len(items)}개 아이템 수신")
        
        collected_data = []
        for item in items:
            try:
                # 필수 필드 추출
                announcement_id = item.find('pblancId')
                title = item.find('pblancNm')
                status = item.find('pblancStts')
                
                if announcement_id is not None and title is not None:
                    data = {
                        'announcement_id': announcement_id.text,
                        'title': title.text,
                        'status': status.text if status is not None else '상태미정',
                        'collected_at': datetime.now().isoformat(),
                        'collection_mode': COLLECTION_MODE
                    }
                    
                    # 추가 필드 (있으면 포함)
                    additional_fields = [
                        ('aplyBgnDe', 'application_start_date'),
                        ('aplyEndDe', 'application_end_date'), 
                        ('rceptBgnDe', 'reception_start_date'),
                        ('rceptEndDe', 'reception_end_date'),
                        ('bsnsSumry', 'business_summary'),
                        ('aplyTrgetCn', 'application_target'),
                        ('sprtCn', 'support_content'),
                        ('inqryTelno', 'inquiry_phone'),
                        ('inqryEml', 'inquiry_email'),
                        ('dtlUrl', 'detail_url')
                    ]
                    
                    for xml_field, db_field in additional_fields:
                        element = item.find(xml_field)
                        if element is not None and element.text:
                            data[db_field] = element.text
                    
                    collected_data.append(data)
                    
            except Exception as e:
                print(f"   ⚠️ 아이템 파싱 오류: {e}")
                continue
        
        return collected_data
        
    except requests.RequestException as e:
        print(f"❌ 네트워크 오류: {e}")
        return None
    except ET.ParseError as e:
        print(f"❌ XML 파싱 오류: {e}")
        return None
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return None

def save_to_database(data_list):
    """데이터베이스에 저장"""
    if not data_list:
        return 0
        
    saved_count = 0
    for data in data_list:
        try:
            # 중복 체크 (전체 announcement_id로)
            existing = supabase.table('kstartup_complete').select('announcement_id').eq('announcement_id', data['announcement_id']).execute()
            
            if not existing.data:
                # 새 데이터 삽입
                supabase.table('kstartup_complete').insert(data).execute()
                saved_count += 1
                print(f"   ✅ 저장: {data['announcement_id']} - {data['title'][:50]}...")
            else:
                print(f"   ⏭️ 중복: {data['announcement_id']}")
                
        except Exception as e:
            print(f"   ❌ 저장 실패: {e}")
            continue
    
    return saved_count

def check_page_duplicates(data_list, existing_ids):
    """페이지 내 데이터가 모두 중복인지 확인 (마지막 6자리 기준)"""
    if not data_list:
        return True
        
    duplicate_count = 0
    for data in data_list:
        announcement_id = data.get('announcement_id', '')
        # 마지막 6자리로 중복 체크
        id_suffix = str(announcement_id)[-6:]
        if id_suffix in existing_ids:
            duplicate_count += 1
    
    # 페이지 내 80% 이상이 중복이면 중복 페이지로 판단
    duplicate_ratio = duplicate_count / len(data_list)
    print(f"   📊 중복률: {duplicate_count}/{len(data_list)} ({duplicate_ratio:.1%})")
    
    return duplicate_ratio >= 0.8

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚀 K-Startup 실제 데이터 수집 시작 (개선된 로직)")
    print("=" * 60)
    print(f"📅 수집 모드: {COLLECTION_MODE.upper()}")
    print(f"🕐 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 기존 데이터 조회
    existing_ids = get_existing_ids()
    
    # 모드별 설정
    if COLLECTION_MODE == 'daily':
        print("📅 Daily 모드: 최신 데이터 확인")
        max_duplicate_count = 50  # 연속 중복 50개면 종료
        max_pages = 5  # 5페이지까지 확인 (1000개)
    else:
        print("🔍 Full 모드: 전체 데이터 수집")
        max_duplicate_count = 100  # 연속 중복 100개면 종료 
        max_pages = 50  # 50페이지까지 확인 (10000개)
    
    print(f"📊 설정: 연속 중복 {max_duplicate_count}개 시 종료, 최대 {max_pages}페이지")
    print()
    
    # 수집 시작
    page = 1
    total_collected = 0
    total_saved = 0
    consecutive_duplicates = 0
    
    while page <= max_pages:
        print(f"📄 페이지 {page}/{max_pages} 처리 중...")
        
        # 데이터 조회
        data_list = fetch_kstartup_data(page, per_page=200)
        if not data_list:
            print(f"   ❌ 페이지 {page} 데이터 조회 실패")
            break
        
        total_collected += len(data_list)
        
        # 페이지 단위 중복 체크
        is_duplicate_page = check_page_duplicates(data_list, existing_ids)
        
        if is_duplicate_page:
            consecutive_duplicates += len(data_list)
            print(f"   🔄 중복 페이지 감지 (연속 중복: {consecutive_duplicates}개)")
        else:
            consecutive_duplicates = 0
            
        # 데이터베이스 저장
        saved_count = save_to_database(data_list)
        total_saved += saved_count
        
        print(f"   📊 이번 페이지: 수집 {len(data_list)}개, 저장 {saved_count}개")
        print()
        
        # 종료 조건 확인
        if consecutive_duplicates >= max_duplicate_count:
            print(f"🛑 연속 중복 {consecutive_duplicates}개 감지 - 수집 종료")
            break
            
        # 다음 페이지
        page += 1
        time.sleep(0.5)  # API 호출 간격
    
    # 결과 보고
    print("=" * 60)
    print("📊 K-Startup 수집 완료 보고서 (개선된 로직)")
    print("=" * 60)
    print(f"🕐 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📄 처리된 페이지: {page - 1}개")
    print(f"📊 총 수집: {total_collected}개")
    print(f"💾 새로 저장: {total_saved}개")
    print(f"🔄 연속 중복: {consecutive_duplicates}개")
    print()
    print("📌 개선 사항:")
    print("  - perPage=200 (구글시트와 동일)")
    print("  - 연속 50개 중복 시 자동 종료")
    print("  - 페이지 단위 중복 체크")
    print("=" * 60)
    
    if total_saved > 0:
        print(f"✅ 성공: {total_saved}개 새 데이터 저장 완료!")
    else:
        print("ℹ️ 새로운 데이터가 없었습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        sys.exit(1)