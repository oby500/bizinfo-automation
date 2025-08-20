#!/usr/bin/env python3
"""
K-Startup 심층 수집 스크립트
- 30페이지 이후 데이터 수집
- 누락된 데이터 찾기
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
        
        # 필드 매핑
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
            # 접수 시작일
            if value:
                data['recept_begin_dt'] = value
        elif name == 'pbanc_rcpt_end_dt':
            # 접수 종료일
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
    print("🚀 K-Startup 심층 수집 (30-35 페이지)")
    print("="*60)
    
    # 기존 ID 목록 가져오기
    print("\n📋 기존 데이터 확인 중...")
    try:
        result = supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = set(item['announcement_id'] for item in result.data if item.get('announcement_id'))
        print(f"   기존 공고: {len(existing_ids)}개")
    except Exception as e:
        print(f"   ❌ 기존 데이터 조회 실패: {e}")
        existing_ids = set()
    
    total_saved = 0
    total_updated = 0
    total_skipped = 0
    empty_pages = 0
    
    # 30-35 페이지 수집
    for page_no in range(30, 36):
        print(f"\n📄 페이지 {page_no} 수집 중...")
        items = collect_page(page_no)
        
        if not items:
            print(f"   페이지 {page_no}: 데이터 없음")
            empty_pages += 1
            if empty_pages >= 3:
                print("   ⚠️ 연속 3페이지 데이터 없음 - 수집 종료")
                break
            continue
        
        empty_pages = 0  # 데이터가 있으면 리셋
        print(f"   페이지 {page_no}: {len(items)}개 항목 발견")
        
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
                    print(f"      ✅ 신규: {data['biz_pbanc_nm'][:40]}...")
                    if 'recept_end_dt' in data:
                        print(f"         마감일: {data['recept_end_dt']}")
                except Exception as e:
                    if 'duplicate' in str(e).lower():
                        # 중복 데이터 업데이트
                        try:
                            result = supabase.table('kstartup_complete').update(data).eq('announcement_id', announcement_id).execute()
                            page_updated += 1
                            print(f"      🔄 업데이트: {data['biz_pbanc_nm'][:40]}...")
                        except:
                            pass
        
        total_saved += page_saved
        total_updated += page_updated
        total_skipped += page_skipped
        
        print(f"   페이지 {page_no} 결과: 신규 {page_saved}개, 업데이트 {page_updated}개, 스킵 {page_skipped}개")
        
        # API 부하 방지
        time.sleep(0.3)
    
    print("\n" + "="*60)
    print(f"📊 전체 결과:")
    print(f"   신규 저장: {total_saved}개")
    print(f"   업데이트: {total_updated}개")
    print(f"   스킵: {total_skipped}개")
    print(f"   총 처리: {total_saved + total_updated + total_skipped}개")
    print("="*60)

if __name__ == "__main__":
    main()