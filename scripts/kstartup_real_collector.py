#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
K-Startup 실제 데이터 수집기 (완전 수정판)
- 올바른 XML 파싱: <col name="필드명">값</col> 구조
- Daily 모드: 연속 50개 중복 시 종료 (구글시트와 동일)
- numOfRows=100으로 효율적 수집
"""

import os
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Supabase 설정
try:
    from supabase import create_client
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("환경변수 오류: SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다.")
        sys.exit(1)
        
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase 연결 성공")
    
except Exception as e:
    print(f"Supabase 연결 실패: {e}")
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
                    existing_ids.add(str(announcement_id))
            print(f"기존 데이터: {len(existing_ids)}개")
            return existing_ids
        return set()
    except Exception as e:
        print(f"기존 데이터 조회 실패: {e}")
        return set()

def parse_named_columns(item):
    """name 속성이 있는 col 태그 파싱"""
    cols = item.findall('col')
    field_data = {}
    
    for col in cols:
        name = col.get('name')
        text = col.text if col.text else ''
        if name:
            field_data[name] = text.strip()
    
    return field_data

def create_kstartup_data(field_data):
    """필드 데이터로부터 K-Startup 데이터 객체 생성"""
    try:
        # 필수 필드 확인
        biz_pbanc_nm = field_data.get('biz_pbanc_nm', '').strip()  # 사업공고명
        pbanc_sn = field_data.get('pbanc_sn', '').strip()         # 공고일련번호
        
        if not biz_pbanc_nm or not pbanc_sn:
            return None
        
        announcement_id = f"KS_{pbanc_sn}"
        
        # 데이터 구성
        data = {
            'announcement_id': announcement_id,
            'title': biz_pbanc_nm,
            'business_summary': field_data.get('pbanc_ctnt', ''),           # 공고내용
            'organization': field_data.get('pbanc_ntrp_nm', ''),            # 공고기업명
            'organization_type': field_data.get('sprv_inst', ''),           # 감독기관
            'application_start_date': field_data.get('pbanc_rcpt_bgng_dt', ''),  # 공고접수시작일
            'application_end_date': field_data.get('pbanc_rcpt_end_dt', ''),     # 공고접수종료일
            'target_category': field_data.get('aply_trgt', ''),             # 신청대상
            'target_description': field_data.get('aply_trgt_ctnt', ''),     # 신청대상내용
            'region': field_data.get('supt_regin', ''),                     # 지원지역
            'support_type': field_data.get('supt_biz_clsfc', ''),           # 지원사업분류
            'contact_phone': field_data.get('prch_cnpl_no', ''),            # 조달연락처번호
            'detail_url': field_data.get('detl_pg_url', ''),                # 상세페이지URL
            'application_url': field_data.get('aply_mthd_onli_rcpt_istc', ''),  # 신청방법온라인접수기관
            'guidance_url': field_data.get('biz_gdnc_url', ''),             # 사업안내URL
            'target_stage': field_data.get('biz_enyy', ''),                 # 사업연혁
            'age_limit': field_data.get('biz_trgt_age', ''),                # 사업대상연령
            'status': '접수중' if field_data.get('rcrt_prgs_yn', '') == 'Y' else '마감',
            'collected_at': datetime.now().isoformat(),
            'collection_mode': COLLECTION_MODE
        }
        
        return data
        
    except Exception as e:
        print(f"   데이터 생성 오류: {e}")
        return None

def fetch_kstartup_data(page, num_rows=100):
    """K-Startup API에서 데이터 조회"""
    params = {
        'ServiceKey': API_KEY,
        'pageNo': page,
        'numOfRows': num_rows
    }
    
    try:
        print(f"페이지 {page} 요청 중... (numOfRows={num_rows})")
        response = requests.get(BASE_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"HTTP 오류: {response.status_code}")
            return None
            
        # XML 파싱
        root = ET.fromstring(response.content)
        
        # 아이템 추출
        items = root.findall('.//item')
        print(f"   {len(items)}개 아이템 수신")
        
        collected_data = []
        for item in items:
            # name 속성이 있는 col 태그들 파싱
            field_data = parse_named_columns(item)
            
            # K-Startup 데이터 생성
            data = create_kstartup_data(field_data)
            if data:
                collected_data.append(data)
        
        print(f"   {len(collected_data)}개 유효 데이터 파싱")
        return collected_data
        
    except requests.RequestException as e:
        print(f"네트워크 오류: {e}")
        return None
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
        return None
    except Exception as e:
        print(f"예상치 못한 오류: {e}")
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
                print(f"   저장: {data['announcement_id']} - {data['title'][:50]}...")
            else:
                print(f"   중복: {data['announcement_id']}")
                
        except Exception as e:
            print(f"   저장 실패 {data.get('announcement_id', 'UNKNOWN')}: {e}")
            continue
    
    return saved_count

def check_page_duplicates(data_list, existing_ids):
    """페이지 내 데이터가 모두 중복인지 확인"""
    if not data_list:
        return True
        
    duplicate_count = 0
    for data in data_list:
        announcement_id = data.get('announcement_id', '')
        if announcement_id in existing_ids:
            duplicate_count += 1
    
    # 페이지 내 80% 이상이 중복이면 중복 페이지로 판단
    duplicate_ratio = duplicate_count / len(data_list)
    print(f"   중복률: {duplicate_count}/{len(data_list)} ({duplicate_ratio:.1%})")
    
    return duplicate_ratio >= 0.8

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("K-Startup 실제 데이터 수집 시작 (완전 수정판)")
    print("=" * 60)
    print(f"수집 모드: {COLLECTION_MODE.upper()}")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 기존 데이터 조회
    existing_ids = get_existing_ids()
    
    # 모드별 설정
    if COLLECTION_MODE == 'daily':
        print("Daily 모드: 최신 데이터 확인")
        max_duplicate_count = 50  # 연속 중복 50개면 종료
        max_pages = 5  # 5페이지까지 확인 (500개)
    else:
        print("Full 모드: 전체 데이터 수집")
        max_duplicate_count = 100  # 연속 중복 100개면 종료 
        max_pages = 20  # 20페이지까지 확인 (2000개)
    
    print(f"설정: 연속 중복 {max_duplicate_count}개 시 종료, 최대 {max_pages}페이지")
    print()
    
    # 수집 시작
    page = 1
    total_collected = 0
    total_saved = 0
    consecutive_duplicates = 0
    
    while page <= max_pages:
        print(f"페이지 {page}/{max_pages} 처리 중...")
        
        # 데이터 조회
        data_list = fetch_kstartup_data(page, num_rows=100)
        if not data_list:
            print(f"   페이지 {page} 데이터 조회 실패")
            break
        
        total_collected += len(data_list)
        
        # 페이지 단위 중복 체크
        is_duplicate_page = check_page_duplicates(data_list, existing_ids)
        
        if is_duplicate_page:
            consecutive_duplicates += len(data_list)
            print(f"   중복 페이지 감지 (연속 중복: {consecutive_duplicates}개)")
        else:
            consecutive_duplicates = 0
            
        # 데이터베이스 저장
        saved_count = save_to_database(data_list)
        total_saved += saved_count
        
        # 새로 저장된 데이터를 existing_ids에 추가
        for data in data_list:
            if data['announcement_id'] not in existing_ids:
                existing_ids.add(data['announcement_id'])
        
        print(f"   이번 페이지: 수집 {len(data_list)}개, 저장 {saved_count}개")
        print()
        
        # 종료 조건 확인
        if consecutive_duplicates >= max_duplicate_count:
            print(f"연속 중복 {consecutive_duplicates}개 감지 - 수집 종료")
            break
            
        # 다음 페이지
        page += 1
        time.sleep(0.5)  # API 호출 간격
    
    # 결과 보고
    print("=" * 60)
    print("K-Startup 수집 완료 보고서 (완전 수정판)")
    print("=" * 60)
    print(f"완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"처리된 페이지: {page - 1}개")
    print(f"총 수집: {total_collected}개")
    print(f"새로 저장: {total_saved}개")
    print(f"연속 중복: {consecutive_duplicates}개")
    print()
    print("주요 개선사항:")
    print("  - 올바른 XML 파싱 (<col name='필드명'>값</col>)")
    print("  - 구글시트와 동일한 데이터 구조")
    print("  - 연속 50개 중복 시 자동 종료")
    print("  - 페이지 단위 중복 체크")
    print("=" * 60)
    
    if total_saved > 0:
        print(f"성공: {total_saved}개 새 데이터 저장 완료!")
    else:
        print("새로운 데이터가 없었습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")
        sys.exit(1)