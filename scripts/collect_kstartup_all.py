#!/usr/bin/env python3
"""
K-Startup 전체 데이터 수집 스크립트
- 중복 체크하면서 새로운 데이터만 수집
- 이미 있는 데이터를 만나면 중단
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
        
        # 필드 매핑 (테이블 컬럼명과 일치하도록)
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
            data['pbanc_ctnt'] = value  # 내용
    
    # bsns_sumry 추가 (제목이나 내용 사용)
    if 'pbanc_ctnt' in data:
        data['bsns_sumry'] = data['pbanc_ctnt']
    elif 'biz_pbanc_nm' in data:
        data['bsns_sumry'] = data['biz_pbanc_nm']
    
    # 기본값 설정
    data['extraction_date'] = datetime.now().isoformat()
    
    return data

def get_existing_ids():
    """기존 공고 ID 목록 가져오기"""
    try:
        result = supabase.table('kstartup_complete').select('announcement_id').execute()
        return set(item['announcement_id'] for item in result.data if item.get('announcement_id'))
    except Exception as e:
        print(f"기존 ID 조회 실패: {e}")
        return set()

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
            print(f"   ❌ 페이지 {page_no}: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"   ❌ 페이지 {page_no} 오류: {e}")
        return []

def main():
    print("="*60)
    print("🚀 K-Startup 전체 데이터 수집")
    print("="*60)
    
    # 기존 ID 목록 가져오기
    print("\n📋 기존 데이터 확인 중...")
    existing_ids = get_existing_ids()
    print(f"   기존 공고: {len(existing_ids)}개")
    
    total_saved = 0
    total_updated = 0
    total_skipped = 0
    consecutive_duplicates = 0
    max_consecutive_duplicates = 50  # 연속 50개 중복이면 중단
    
    page_no = 1
    max_pages = 100  # 최대 100페이지까지
    
    while page_no <= max_pages:
        print(f"\n📄 페이지 {page_no} 수집 중...")
        items = collect_page(page_no)
        
        if not items:
            print(f"   페이지 {page_no}: 데이터 없음 - 수집 종료")
            break
            
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
                    consecutive_duplicates += 1
                    continue
                else:
                    consecutive_duplicates = 0  # 새 데이터 발견 시 리셋
                
                try:
                    # 새 데이터 저장
                    result = supabase.table('kstartup_complete').insert(data).execute()
                    page_saved += 1
                    existing_ids.add(announcement_id)  # 저장된 ID 추가
                    print(f"      ✅ 신규: {data['biz_pbanc_nm'][:40]}...")
                except Exception as e:
                    if 'duplicate' in str(e).lower():
                        # 중복 데이터 업데이트
                        try:
                            result = supabase.table('kstartup_complete').update(data).eq('announcement_id', announcement_id).execute()
                            page_updated += 1
                        except:
                            pass
                    else:
                        print(f"      ❌ 저장 실패: {e}")
        
        total_saved += page_saved
        total_updated += page_updated
        total_skipped += page_skipped
        
        print(f"   페이지 {page_no} 결과: 신규 {page_saved}개, 업데이트 {page_updated}개, 스킵 {page_skipped}개")
        
        # 연속 중복 체크
        if consecutive_duplicates >= max_consecutive_duplicates:
            print(f"\n📌 연속 {consecutive_duplicates}개 중복 발견 - 수집 종료")
            break
        
        # 다음 페이지로
        page_no += 1
        
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