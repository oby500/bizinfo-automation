#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
K-Startup 수집기 (API 구조 변경 대응)
- 새로운 API 응답 형태: <col> 태그 기반
- 필드 순서 매핑으로 데이터 추출
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
    print(f"✅ Supabase 연결 성공")
    
except Exception as e:
    print(f"❌ Supabase 연결 실패: {e}")
    sys.exit(1)

# K-Startup API 설정
API_KEY = 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=='
BASE_URL = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'

# 모드 설정
COLLECTION_MODE = os.getenv('COLLECTION_MODE', 'daily')

# 새로운 API 응답 구조의 필드 순서 (첫 번째 테스트 결과 기준)
FIELD_MAPPING = {
    0: 'unknown1',
    1: 'target_description',  # 대상 설명
    2: 'form_url',           # 신청 URL
    3: 'contact_phone',      # 연락처
    4: 'unknown5',
    5: 'unknown6', 
    6: 'unknown7',
    7: 'registration_date',  # 등록일
    8: 'status_flag',        # 상태 플래그
    9: 'detail_url',         # 상세 URL
    10: 'unknown11',
    11: 'target_category',   # 대상 카테고리
    12: 'organization',      # 주관기관
    13: 'unknown14',
    14: 'unknown15',
    15: 'support_type',      # 지원형태
    16: 'unknown17',
    17: 'business_summary',  # 사업 요약
    18: 'organization_name', # 기관명
    19: 'application_url',   # 신청 URL (중복?)
    20: 'target_stage',      # 창업 단계
    21: 'title',             # 공고명
    22: 'organization_type', # 기관 유형
    23: 'unknown24',
    24: 'priority',          # 우선순위?
    25: 'end_date',          # 마감일
    26: 'region',            # 지역
    27: 'age_limit',         # 연령 제한
    28: 'title_duplicate',   # 공고명 (중복)
    29: 'announcement_id_raw' # 공고 ID (숫자만)
}

def get_existing_ids():
    """기존 데이터의 announcement_id 목록 조회"""
    try:
        result = supabase.table('kstartup_complete').select('announcement_id').execute()
        if result.data:
            existing_ids = set()
            for item in result.data:
                announcement_id = item.get('announcement_id')
                if announcement_id:
                    existing_ids.add(str(announcement_id))
            print(f"📊 기존 데이터: {len(existing_ids)}개")
            return existing_ids
        return set()
    except Exception as e:
        print(f"⚠️ 기존 데이터 조회 실패: {e}")
        return set()

def parse_new_api_format(item):
    """새로운 API 형태의 <col> 태그 파싱"""
    cols = item.findall('col')
    if len(cols) < 30:
        return None
    
    try:
        # 공고 ID 구성 (마지막 col 태그에서 숫자 추출)
        raw_id = cols[29].text if cols[29].text else ''
        announcement_id = f"KS_{raw_id}" if raw_id else None
        
        if not announcement_id:
            return None
        
        # 데이터 구성
        data = {
            'announcement_id': announcement_id,
            'title': cols[21].text if cols[21].text else '',
            'business_summary': cols[17].text if cols[17].text else '',
            'organization': cols[12].text if cols[12].text else '',
            'organization_type': cols[22].text if cols[22].text else '',
            'support_type': cols[15].text if cols[15].text else '',
            'target_category': cols[11].text if cols[11].text else '',
            'target_stage': cols[20].text if cols[20].text else '',
            'region': cols[26].text if cols[26].text else '',
            'registration_date': cols[7].text if cols[7].text else '',
            'end_date': cols[25].text if cols[25].text else '',
            'detail_url': cols[9].text if cols[9].text else '',
            'application_url': cols[2].text if cols[2].text else '',
            'contact_phone': cols[3].text if cols[3].text else '',
            'status': '접수중' if cols[8].text == 'Y' else '마감',
            'collected_at': datetime.now().isoformat(),
            'collection_mode': COLLECTION_MODE
        }
        
        return data
        
    except Exception as e:
        print(f"   ⚠️ 파싱 오류: {e}")
        return None

def fetch_kstartup_data(page, num_rows=100):
    """K-Startup API에서 데이터 조회 (새 형태)"""
    params = {
        'ServiceKey': API_KEY,
        'pageNo': page,
        'numOfRows': num_rows
    }
    
    try:
        print(f"📄 페이지 {page} 요청 중... (numOfRows={num_rows})")
        response = requests.get(BASE_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ HTTP 오류: {response.status_code}")
            return None
            
        # XML 파싱
        root = ET.fromstring(response.content)
        
        # 아이템 추출
        items = root.findall('.//item')
        print(f"   📊 {len(items)}개 아이템 수신")
        
        collected_data = []
        for item in items:
            data = parse_new_api_format(item)
            if data:
                collected_data.append(data)
        
        print(f"   📊 {len(collected_data)}개 유효 데이터 파싱")
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
            # 중복 체크
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

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚀 K-Startup 수집기 (API 구조 변경 대응)")
    print("=" * 60)
    print(f"📅 수집 모드: {COLLECTION_MODE.upper()}")
    print(f"🕐 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 기존 데이터 조회
    existing_ids = get_existing_ids()
    
    # 모드별 설정
    if COLLECTION_MODE == 'daily':
        print("📅 Daily 모드: 최신 3페이지 확인")
        max_pages = 3
    else:
        print("🔍 Full 모드: 10페이지 확인")
        max_pages = 10
    
    print(f"📊 설정: 최대 {max_pages}페이지 처리")
    print()
    
    # 수집 시작
    page = 1
    total_collected = 0
    total_saved = 0
    
    while page <= max_pages:
        print(f"📄 페이지 {page}/{max_pages} 처리 중...")
        
        # 데이터 조회
        data_list = fetch_kstartup_data(page, num_rows=100)
        if not data_list:
            print(f"   ❌ 페이지 {page} 데이터 조회 실패")
            break
        
        total_collected += len(data_list)
        
        # 데이터베이스 저장
        saved_count = save_to_database(data_list)
        total_saved += saved_count
        
        print(f"   📊 이번 페이지: 수집 {len(data_list)}개, 저장 {saved_count}개")
        print()
        
        # 다음 페이지
        page += 1
        time.sleep(0.5)  # API 호출 간격
    
    # 결과 보고
    print("=" * 60)
    print("📊 K-Startup 수집 완료 보고서 (API 구조 변경 대응)")
    print("=" * 60)
    print(f"🕐 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📄 처리된 페이지: {page - 1}개")
    print(f"📊 총 수집: {total_collected}개")
    print(f"💾 새로 저장: {total_saved}개")
    print()
    print("📌 주요 변경사항:")
    print("  - 새로운 API 응답 구조 (<col> 태그) 대응")
    print("  - 필드 순서 매핑으로 정확한 데이터 추출")
    print("  - pageNo/numOfRows 파라미터 사용")
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