#!/usr/bin/env python3
"""
기업마당 실제 API 데이터 수집 스크립트
- 실제 웹사이트에서 데이터 수집
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
import os
import json
from bs4 import BeautifulSoup

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("환경변수 오류: SUPABASE_URL, SUPABASE_KEY 필요")
    exit(1)

supabase = create_client(url, key)

def get_bizinfo_list():
    """기업마당 목록 가져오기"""
    # 기업마당 API 엔드포인트
    api_url = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"
    
    # AJAX 요청 시뮬레이션
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Referer': 'https://www.bizinfo.go.kr/'
    }
    
    # POST 파라미터
    data = {
        'pageIndex': '1',
        'pageUnit': '50',  # 한 번에 50개
        'searchCondition': '',
        'searchKeyword': ''
    }
    
    try:
        print("🌐 기업마당 웹사이트 접속 중...")
        response = requests.post(api_url, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            print("✅ 접속 성공")
            return parse_bizinfo_html(response.text)
        else:
            print(f"❌ 접속 실패: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ 오류: {e}")
        return []

def parse_bizinfo_html(html_content):
    """HTML에서 공고 정보 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    announcements = []
    
    # 테이블에서 공고 정보 찾기
    table = soup.find('table', class_='tbl_list')
    if not table:
        print("테이블을 찾을 수 없습니다")
        return announcements
    
    rows = table.find('tbody').find_all('tr')
    
    for row in rows:
        try:
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
            
            # 제목과 링크
            title_elem = cols[1].find('a')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            onclick = title_elem.get('onclick', '')
            
            # pblancId 추출
            pblanc_id = None
            if 'pblancId=' in onclick:
                start = onclick.find('pblancId=') + 10
                end = onclick.find("'", start)
                pblanc_id = onclick[start:end]
            
            if not pblanc_id:
                pblanc_id = f"PBLN_{datetime.now().strftime('%Y%m%d')}_{len(announcements):04d}"
            
            # 기관명
            organ = cols[2].get_text(strip=True)
            
            # 신청기간
            period = cols[3].get_text(strip=True)
            dates = period.split('~') if '~' in period else [None, None]
            
            # 등록일
            reg_date = cols[4].get_text(strip=True)
            
            announcement = {
                'pblanc_id': f"PBLN_{pblanc_id}" if not pblanc_id.startswith('PBLN_') else pblanc_id,
                'pblanc_nm': title,
                'organ_nm': organ,
                'reqst_period': period,
                'reqst_begin_ymd': dates[0].strip() if dates[0] else None,
                'reqst_end_ymd': dates[1].strip() if dates[1] else None,
                'regist_dt': reg_date,
                'announcement_id': f"PBLN_{pblanc_id}" if not pblanc_id.startswith('PBLN_') else pblanc_id,
                'bsns_title': title,
                'bsns_sumry': f"📋 {title}\n🏢 주관: {organ}\n📅 기간: {period}",
                'detail_url': f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}",
                'attachment_urls': [],
                'attachment_processing_status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            announcements.append(announcement)
            
        except Exception as e:
            print(f"행 파싱 오류: {e}")
            continue
    
    return announcements

def main():
    print("="*60)
    print("🏢 기업마당 실제 데이터 수집")
    print("="*60)
    
    # 기존 데이터 확인
    print("\n📋 기존 데이터 확인 중...")
    try:
        result = supabase.table('bizinfo_complete').select('pblanc_id').execute()
        existing_ids = set(item['pblanc_id'] for item in result.data)
        print(f"   기존 공고: {len(existing_ids)}개")
    except Exception as e:
        print(f"   ❌ 오류: {e}")
        existing_ids = set()
    
    # 데이터 수집
    announcements = get_bizinfo_list()
    
    if not announcements:
        print("\n수집된 데이터가 없습니다.")
        return
    
    print(f"\n📊 수집된 공고: {len(announcements)}개")
    
    saved = 0
    skipped = 0
    
    for ann in announcements:
        if ann['pblanc_id'] in existing_ids:
            skipped += 1
            continue
        
        try:
            result = supabase.table('bizinfo_complete').insert(ann).execute()
            saved += 1
            print(f"✅ 저장: {ann['pblanc_nm'][:40]}...")
        except Exception as e:
            print(f"❌ 저장 실패: {e}")
    
    print(f"\n📊 결과:")
    print(f"   신규 저장: {saved}개")
    print(f"   중복 제외: {skipped}개")
    print("="*60)

if __name__ == "__main__":
    main()