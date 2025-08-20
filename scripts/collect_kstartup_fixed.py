#!/usr/bin/env python3
"""
K-Startup 수정된 수집 스크립트
- 새로운 XML 형식 대응
- col name 속성으로 데이터 파싱
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
            data['bsns_title'] = value  # 제목 중복 저장
        elif name == 'detl_pg_url':
            data['detl_pg_url'] = value
            data['source_url'] = value
            data['announcement_id'] = extract_id_from_url(value)
        elif name == 'pbanc_ntrp_nm':
            data['pbanc_ntrp_nm'] = value
            data['spnsr_organ_nm'] = value  # 주관기관
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
    
    # 기본값 설정 (테이블에 없는 컬럼 제거)
    data['extraction_date'] = datetime.now().isoformat()
    # data['created_at']은 DB에서 자동 생성
    
    return data

def main():
    print("="*60)
    print("🚀 K-Startup 수집 (새 형식)")
    print("="*60)
    
    params = {
        'ServiceKey': API_KEY,
        'pageNo': 1,
        'numOfRows': 100  # 100개씩 수집
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        print(f"HTTP 상태: {response.status_code}")
        
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            items = root.findall('.//item')
            
            print(f"수집된 항목: {len(items)}개")
            
            saved_count = 0
            for item in items:
                data = parse_item(item)
                
                if data.get('announcement_id') and data.get('biz_pbanc_nm'):
                    print(f"\n📄 공고: {data['biz_pbanc_nm'][:50]}...")
                    print(f"   ID: {data['announcement_id']}")
                    print(f"   상태: {data.get('status', '알 수 없음')}")
                    
                    # 데이터베이스 저장
                    try:
                        # 중복 체크
                        existing = supabase.table('kstartup_complete').select('id').eq('announcement_id', data['announcement_id']).execute()
                        
                        if not existing.data:
                            result = supabase.table('kstartup_complete').insert(data).execute()
                            saved_count += 1
                            print("   ✅ 저장 완료")
                        else:
                            # 업데이트
                            result = supabase.table('kstartup_complete').update(data).eq('announcement_id', data['announcement_id']).execute()
                            print("   🔄 업데이트 완료")
                    except Exception as e:
                        print(f"   ❌ 저장 실패: {e}")
            
            print(f"\n📊 결과: {saved_count}개 신규 저장")
            
    except Exception as e:
        print(f"❌ 오류: {e}")
    
    print("="*60)

if __name__ == "__main__":
    main()