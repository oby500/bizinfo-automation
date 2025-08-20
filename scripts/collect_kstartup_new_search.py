#!/usr/bin/env python3
"""
K-Startup 새로운 데이터 검색 스크립트
- 날짜순 정렬 시도
- 다른 API 파라미터 테스트
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
import os
import xml.etree.ElementTree as ET
import re
import json

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# API 설정
API_KEY = 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=='
BASE_URL = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'

def test_api_params():
    """API 파라미터 테스트"""
    print("🔬 API 파라미터 테스트")
    print("-"*40)
    
    # 다양한 파라미터 조합 테스트
    test_params = [
        {
            'ServiceKey': API_KEY,
            'pageNo': 1,
            'numOfRows': 10,
            'resultType': 'xml'
        },
        {
            'ServiceKey': API_KEY,
            'pageNo': 1,
            'numOfRows': 10,
            'sort': 'regDt',  # 등록일순
            'resultType': 'xml'
        },
        {
            'ServiceKey': API_KEY,
            'pageNo': 1,
            'numOfRows': 10,
            'srchBgngDt': (datetime.now() - timedelta(days=7)).strftime('%Y%m%d'),  # 최근 7일
            'srchEndDt': datetime.now().strftime('%Y%m%d'),
            'resultType': 'xml'
        }
    ]
    
    for idx, params in enumerate(test_params, 1):
        print(f"\n테스트 {idx}: {params}")
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                # 결과 정보 출력
                result_code = root.find('.//resultCode')
                result_msg = root.find('.//resultMsg')
                total_count = root.find('.//totalCount')
                
                if result_code is not None:
                    print(f"   결과코드: {result_code.text}")
                if result_msg is not None:
                    print(f"   결과메시지: {result_msg.text}")
                if total_count is not None:
                    print(f"   전체개수: {total_count.text}")
                
                # 첫 번째 아이템 확인
                items = root.findall('.//item')
                if items:
                    print(f"   아이템수: {len(items)}개")
                    first_item = items[0]
                    
                    # col 태그 확인
                    cols = first_item.findall('col')
                    if cols:
                        print(f"   첫 아이템 필드수: {len(cols)}개")
                        # 제목 찾기
                        for col in cols:
                            if col.get('name') == 'biz_pbanc_nm':
                                print(f"   첫 아이템 제목: {col.text[:50]}...")
                                break
                    
            else:
                print(f"   ❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ 오류: {e}")

def extract_id_from_url(url):
    """URL에서 공고 ID 추출"""
    if url:
        match = re.search(r'pbancSn=(\d+)', url)
        if match:
            return f"KS_{match.group(1)}"
    return None

def parse_item(item):
    """새로운 XML 형식 파싱"""
    data = {}
    
    # col 태그들을 순회하며 데이터 추출
    for col in item.findall('col'):
        name = col.get('name')
        value = col.text
        
        # 모든 필드 저장
        if name == 'biz_pbanc_nm':
            data['biz_pbanc_nm'] = value
            data['bsns_title'] = value
        elif name == 'detl_pg_url':
            data['detl_pg_url'] = value
            data['source_url'] = value
            data['announcement_id'] = extract_id_from_url(value)
        elif name == 'pbanc_ntrp_nm':
            data['pbanc_ntrp_nm'] = value
            data['spnsr_organ_nm'] = value
        elif name == 'rcrt_prgs_yn':
            data['status'] = '모집중' if value == 'Y' else '마감'
        elif name == 'sprv_inst':
            data['program_type'] = value
        elif name == 'biz_trgt_age':
            data['target_age'] = value
        elif name == 'supt_regin':
            data['supt_regin'] = value
            data['region'] = value
        elif name == 'aply_trgt':
            data['aply_trgt_ctnt'] = value
            data['target_business'] = value
        elif name == 'biz_gdnc_url':
            data['biz_gdnc_url'] = value
        elif name == 'aply_mthd_onli_rcpt_istc':
            data['biz_aply_url'] = value
        elif name == 'aply_excl_trgt_ctnt':
            data['pbanc_ctnt'] = value
        elif name == 'pbanc_rcpt_bgng_dt':
            if value:
                data['recept_begin_dt'] = value
        elif name == 'pbanc_rcpt_end_dt':
            if value:
                data['recept_end_dt'] = value
    
    # bsns_sumry 추가
    if 'pbanc_ctnt' in data:
        data['bsns_sumry'] = data['pbanc_ctnt']
    elif 'biz_pbanc_nm' in data:
        data['bsns_sumry'] = data['biz_pbanc_nm']
    
    # 기본값 설정
    data['extraction_date'] = datetime.now().isoformat()
    
    return data

def search_new_data():
    """새로운 데이터 검색"""
    print("\n🔍 새로운 데이터 검색")
    print("-"*40)
    
    # 기존 ID 가져오기
    try:
        result = supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = set(item['announcement_id'] for item in result.data if item.get('announcement_id'))
        print(f"기존 저장된 공고: {len(existing_ids)}개")
    except:
        existing_ids = set()
    
    # 최근 데이터 검색 (날짜 파라미터 사용)
    today = datetime.now()
    params = {
        'ServiceKey': API_KEY,
        'pageNo': 1,
        'numOfRows': 100,
        'srchBgngDt': (today - timedelta(days=30)).strftime('%Y%m%d'),  # 최근 30일
        'srchEndDt': today.strftime('%Y%m%d'),
        'resultType': 'xml'
    }
    
    print(f"\n최근 30일 데이터 검색...")
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            items = root.findall('.//item')
            
            if items:
                print(f"발견된 항목: {len(items)}개")
                
                new_count = 0
                for item in items:
                    data = parse_item(item)
                    if data.get('announcement_id'):
                        if data['announcement_id'] not in existing_ids:
                            # 새 데이터 발견
                            try:
                                result = supabase.table('kstartup_complete').insert(data).execute()
                                new_count += 1
                                print(f"✅ 신규 저장: {data['biz_pbanc_nm'][:50]}...")
                                existing_ids.add(data['announcement_id'])
                            except Exception as e:
                                if 'duplicate' not in str(e).lower():
                                    print(f"❌ 저장 실패: {e}")
                
                if new_count > 0:
                    print(f"\n🎉 총 {new_count}개 신규 데이터 저장!")
                else:
                    print("\n모든 데이터가 이미 저장되어 있습니다.")
            else:
                print("검색 결과가 없습니다.")
    except Exception as e:
        print(f"검색 오류: {e}")

def main():
    print("="*60)
    print("🚀 K-Startup 새로운 데이터 검색")
    print("="*60)
    
    # API 파라미터 테스트
    test_api_params()
    
    # 새로운 데이터 검색
    search_new_data()
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()