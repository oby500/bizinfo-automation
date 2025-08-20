#!/usr/bin/env python3
"""
K-Startup 완전 전체 수집 스크립트
- 모든 페이지 검토
- 누락된 데이터 찾기
- 정확한 통계
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
import os
import xml.etree.ElementTree as ET
import re
import time

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# API 설정
API_KEY = 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=='
BASE_URL = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'

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
        
        # 모든 필드 매핑
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
        elif name == 'aply_mthd':
            data['aply_mthd'] = value
        elif name == 'biz_enyy':
            data['biz_enyy'] = value
        elif name == 'intg_pbanc_yn':
            data['intg_pbanc_yn'] = value
        elif name == 'rcrt_prgs_yn':
            data['rcrt_prgs_yn'] = value
    
    # bsns_sumry 추가
    if 'pbanc_ctnt' in data:
        data['bsns_sumry'] = data['pbanc_ctnt']
    elif 'biz_pbanc_nm' in data:
        data['bsns_sumry'] = data['biz_pbanc_nm']
    
    # 기본값 설정
    data['extraction_date'] = datetime.now().isoformat()
    
    return data

def get_total_pages():
    """전체 페이지 수 확인"""
    params = {
        'ServiceKey': API_KEY,
        'pageNo': 1,
        'numOfRows': 1
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            # totalCount 찾기
            total_count_elem = root.find('.//totalCount')
            if total_count_elem is not None and total_count_elem.text:
                total_count = int(total_count_elem.text)
                total_pages = (total_count + 99) // 100  # 100개씩이므로
                return total_pages, total_count
    except Exception as e:
        print(f"전체 페이지 확인 실패: {e}")
    
    return 50, 5000  # 기본값

def collect_page(page_no):
    """특정 페이지 수집"""
    params = {
        'ServiceKey': API_KEY,
        'pageNo': page_no,
        'numOfRows': 100
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            items = root.findall('.//item')
            return items
        else:
            return []
    except Exception as e:
        return []

def main():
    print("="*60)
    print("🚀 K-Startup 완전 전체 수집")
    print("="*60)
    
    # 전체 페이지 수 확인
    total_pages, total_count = get_total_pages()
    print(f"\n📊 API 정보:")
    print(f"   전체 데이터: 약 {total_count}개")
    print(f"   전체 페이지: 약 {total_pages}페이지")
    
    # 기존 ID 목록 가져오기
    print("\n📋 기존 데이터 확인 중...")
    try:
        result = supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = set(item['announcement_id'] for item in result.data if item.get('announcement_id'))
        print(f"   DB 저장된 공고: {len(existing_ids)}개")
    except Exception as e:
        print(f"   ❌ 기존 데이터 조회 실패: {e}")
        existing_ids = set()
    
    total_saved = 0
    total_updated = 0
    total_skipped = 0
    empty_pages = 0
    
    print("\n📦 수집 시작...")
    print("-"*40)
    
    # 최대 100페이지까지만 (안전을 위해)
    max_pages = min(total_pages, 100)
    
    for page_no in range(1, max_pages + 1):
        items = collect_page(page_no)
        
        if not items:
            empty_pages += 1
            if empty_pages >= 5:
                print(f"\n⚠️ 페이지 {page_no}: 연속 5페이지 데이터 없음 - 수집 종료")
                break
            continue
        
        empty_pages = 0
        
        page_saved = 0
        page_updated = 0
        page_skipped = 0
        
        for item in items:
            data = parse_item(item)
            
            if data.get('announcement_id') and data.get('biz_pbanc_nm'):
                announcement_id = data['announcement_id']
                
                # 이미 있는 데이터인지 확인
                if announcement_id in existing_ids:
                    page_skipped += 1
                    continue
                
                try:
                    # 새 데이터 저장
                    result = supabase.table('kstartup_complete').insert(data).execute()
                    page_saved += 1
                    existing_ids.add(announcement_id)
                    print(f"✅ [{page_no:3d}] 신규: {data['biz_pbanc_nm'][:50]}...")
                except Exception as e:
                    if 'duplicate' in str(e).lower():
                        # 중복 데이터 업데이트
                        try:
                            result = supabase.table('kstartup_complete').update(data).eq('announcement_id', announcement_id).execute()
                            page_updated += 1
                        except:
                            pass
        
        total_saved += page_saved
        total_updated += page_updated
        total_skipped += page_skipped
        
        # 진행 상황 표시 (10페이지마다)
        if page_no % 10 == 0:
            print(f"   📄 진행: {page_no}/{max_pages} 페이지 | 누적 - 신규: {total_saved}, 업데이트: {total_updated}, 스킵: {total_skipped}")
        
        # API 부하 방지
        if page_saved > 0 or page_updated > 0:
            time.sleep(0.5)  # 데이터가 있을 때는 좀 더 대기
        else:
            time.sleep(0.2)
    
    print("\n" + "="*60)
    print(f"📊 최종 결과:")
    print(f"   ✅ 신규 저장: {total_saved}개")
    print(f"   🔄 업데이트: {total_updated}개")
    print(f"   ⏭️ 스킵 (중복): {total_skipped}개")
    print(f"   📋 총 처리: {total_saved + total_updated + total_skipped}개")
    print(f"   💾 현재 DB 총: {len(existing_ids)}개")
    print("="*60)

if __name__ == "__main__":
    main()