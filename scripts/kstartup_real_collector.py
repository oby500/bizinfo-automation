#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K-Startup 실제 데이터 수집기 - 구글 시트 로직 기반
GitHub Actions용
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import time
import re
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경변수 로드
load_dotenv()

def format_date_time(dt):
    """날짜+시간 포맷 YYYY-MM-DD HH:MM:SS"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def pad_number(n):
    """숫자 보정 (1 → 01)"""
    return str(n).zfill(2)

def clean_text(html_text):
    """HTML 태그 제거 + 정리"""
    if not html_text:
        return ""
    # HTML 태그 제거
    clean = re.sub(r'<[^>]*>', '', str(html_text))
    # 여러 공백을 하나로
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def fetch_detail_info(detail_url):
    """상세페이지에서 신청기간, 지원내용, 첨부파일 추출"""
    try:
        response = requests.get(detail_url, timeout=10)
        html = response.text
        
        # 기본값
        result = {
            'applicationStartDate': '',
            'applicationEndDate': '',
            'supportTarget': '',
            'supportContent': '',
            'attachmentLinks': ''
        }
        
        # 1. JavaScript 변수에서 날짜 추출 (가장 정확한 방법)
        js_dates = re.findall(r"getDayOfTheWeek\('(\d{4})\.(\d{1,2})\.(\d{1,2})", html)
        if len(js_dates) >= 2:
            # 시작일과 종료일 모두 찾은 경우
            year1, month1, day1 = js_dates[0]
            year2, month2, day2 = js_dates[1]
            result['applicationStartDate'] = f"{year1}-{pad_number(month1)}-{pad_number(day1)}"
            result['applicationEndDate'] = f"{year2}-{pad_number(month2)}-{pad_number(day2)}"
        elif len(js_dates) == 1:
            # 하나만 찾은 경우 시작일로 설정
            year1, month1, day1 = js_dates[0]
            result['applicationStartDate'] = f"{year1}-{pad_number(month1)}-{pad_number(day1)}"
            
            # 추가 날짜 패턴 검색
            additional_dates = re.findall(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", html)
            if len(additional_dates) >= 2:
                year2, month2, day2 = additional_dates[1]
                result['applicationEndDate'] = f"{year2}-{pad_number(month2)}-{pad_number(day2)}"
        
        # JavaScript에서 찾지 못했다면 기존 HTML 패턴 사용
        if not result['applicationStartDate']:
            # 공백 제거
            cleaned_html = re.sub(r'\s+', '', html).replace('&nbsp;', '')
            
            # 2. HTML에서 YYYY.MM.DD ~ YYYY.MM.DD 패턴
            date_match = re.search(r'(20\d{2})[.\-/년](\d{1,2})[.\-/월](\d{1,2})[일]?[^\d]*(20\d{2})[.\-/년](\d{1,2})[.\-/월](\d{1,2})[일]?', cleaned_html)
            if date_match:
                result['applicationStartDate'] = f"{date_match.group(1)}-{pad_number(date_match.group(2))}-{pad_number(date_match.group(3))}"
                result['applicationEndDate'] = f"{date_match.group(4)}-{pad_number(date_match.group(5))}-{pad_number(date_match.group(6))}"
            else:
                # 3. MM.DD ~ MM.DD 패턴 (현재 연도)
                date_match2 = re.search(r'(\d{1,2})[.\-/월](\d{1,2})[일]?[~\-](\d{1,2})[.\-/월](\d{1,2})[일]?', cleaned_html)
                if date_match2:
                    current_year = datetime.now().year
                    result['applicationStartDate'] = f"{current_year}-{pad_number(date_match2.group(1))}-{pad_number(date_match2.group(2))}"
                    result['applicationEndDate'] = f"{current_year}-{pad_number(date_match2.group(3))}-{pad_number(date_match2.group(4))}"
        
        # 지원대상 추출
        target_match = re.search(r'지원대상\s*:?([\s\S]*?)</div>', html, re.IGNORECASE)
        if target_match:
            result['supportTarget'] = clean_text(target_match.group(1))
        
        # 지원내용 추출
        content_match = re.search(r'지원내용\s*:?([\s\S]*?)</div>', html, re.IGNORECASE)
        if content_match:
            result['supportContent'] = clean_text(content_match.group(1))
        
        # 첨부파일 링크 추출
        attachment_matches = re.findall(r'<a[^>]*href="([^"]+)"[^>]*download', html, re.IGNORECASE)
        if attachment_matches:
            base_url = "https://www.k-startup.go.kr"
            result['attachmentLinks'] = ", ".join([base_url + link for link in attachment_matches])
        
        return result
        
    except Exception as e:
        print(f"❌ 상세페이지 파싱 실패: {detail_url} - {e}")
        return {
            'applicationStartDate': '',
            'applicationEndDate': '',
            'supportTarget': '',
            'supportContent': '',
            'attachmentLinks': ''
        }

def collect_kstartup_data():
    """K-Startup 데이터 수집 메인 함수"""
    print("="*60)
    print("🚀 K-Startup 실제 데이터 수집 시작")
    print("="*60)
    
    # 수집 모드 확인
    collection_mode = os.getenv('COLLECTION_MODE', 'daily')
    print(f"📋 수집 모드: {collection_mode}")
    
    if collection_mode == 'daily':
        print("📅 Daily 모드: 최대 10페이지까지 데이터 수집")
        max_duplicate_count = 50  # 연속 중복 50개까지 허용
        max_pages = 10  # 10페이지까지 시도
        min_check_count = 100  # 최소 100개 검토
    else:
        print("🔄 Full 모드: 전체 데이터 수집")
        max_duplicate_count = 50  # 중복 50건에서 중지 
        max_pages = 100  # 최대 100페이지
        min_check_count = 0  # 제한 없음
    
    # Supabase 연결
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase 환경변수가 설정되지 않았습니다.")
        return
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase 연결 성공")
    
    # 기존 공고ID 조회 (뒤 6자리만 추출하여 비교)
    try:
        existing_result = supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = set()
        if existing_result.data:
            # announcement_id에서 뒤 6자리 숫자만 추출 (KS_ 접두사 무시)
            for item in existing_result.data:
                if item.get('announcement_id'):
                    full_id = str(item['announcement_id']).strip()
                    # 뒤에서 6자리 숫자 추출 (예: "KS_174689" → "174689", "174689" → "174689")
                    if len(full_id) >= 6:
                        last_6_digits = full_id[-6:]
                        if last_6_digits.isdigit():
                            existing_ids.add(last_6_digits)
        print(f"📋 기존 공고 수: {len(existing_ids)}개 (뒤 6자리 기준)")
    except Exception as e:
        print(f"⚠️ 기존 데이터 조회 실패, 계속 진행: {e}")
        existing_ids = set()
    
    # API 설정 - HTTP로 시도
    service_key = "rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=="
    base_url = "http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
    
    # 데이터 수집
    page = 1
    per_page = 100  # API가 실제로 지원하는 크기
    duplicate_count = 0
    new_items = []
    total_checked = 0  # 총 검토한 데이터 수
    
    while True:
        print(f"\n📄 페이지 {page} 수집 중...")
        
        params = {
            'ServiceKey': service_key,  # 대문자 S
            'page': page,               # page로 수정 (pageNo가 아님)
            'perPage': per_page         # perPage로 수정 (numOfRows가 아님)
        }
        
        try:
            # SSL 검증 우회 및 헤더 추가
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/xml, text/xml, */*',
                'Connection': 'keep-alive'
            }
            
            response = requests.get(base_url, params=params, headers=headers, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"❌ HTTP 오류: {response.status_code}")
                break
            
            # XML 파싱
            root = ET.fromstring(response.text)
            
            # data/item 구조 확인
            data_element = root.find('data')
            if data_element is None:
                print("❌ XML에서 data 요소를 찾을 수 없습니다.")
                break
                
            items = data_element.findall('item')
            
            if len(items) == 0:
                print(f"✅ 페이지 {page}: 데이터 없음 - 수집 완료")
                break
            
            print(f"📊 페이지 {page}: {len(items)}개 항목 발견")
            
            for item in items:
                cols = item.findall('col')
                total_checked += 1  # 검토한 데이터 수 증가
                
                # 데이터 추출
                row_data = {
                    'id': '',
                    'title': '',
                    'org': '',
                    'supervisor': '',
                    'executor': '',
                    'url': ''
                }
                
                for col in cols:
                    name_attr = col.get('name')
                    value = col.text or ''
                    
                    if name_attr == 'pbanc_sn':
                        row_data['id'] = value
                    elif name_attr == 'biz_pbanc_nm':
                        row_data['title'] = value
                    elif name_attr == 'pbanc_ntrp_nm':
                        row_data['org'] = value
                    elif name_attr == 'sprv_inst':
                        row_data['supervisor'] = value
                    elif name_attr == 'biz_prch_dprt_nm':
                        row_data['executor'] = value
                    elif name_attr == 'detl_pg_url':
                        row_data['url'] = value
                
                # 중복 체크 (뒤 6자리만 비교)
                id_trimmed = str(row_data['id']).strip()
                # API ID에서도 뒤 6자리만 추출
                id_last_6 = id_trimmed[-6:] if len(id_trimmed) >= 6 and id_trimmed[-6:].isdigit() else id_trimmed
                
                if id_last_6 in existing_ids:
                    duplicate_count += 1
                    print(f"⚠️ 중복: {id_trimmed} → {id_last_6} ({duplicate_count}연속, 총 {total_checked}개 검토)")
                    
                    # 최소 검토 개수를 만족했고 연속 중복이 많을 때만 종료
                    if total_checked >= min_check_count and duplicate_count >= max_duplicate_count:
                        print(f"🔄 최소 {min_check_count}개 검토 완료 + 연속 중복 {max_duplicate_count}건 도달 - 수집 종료")
                        break
                    continue
                
                # URL 검증
                if not row_data['url'] or not row_data['url'].strip():
                    print(f"⚠️ URL 누락 - 건너뜀: {row_data['id']}")
                    continue
                
                duplicate_count = 0  # 새 데이터 발견 시 리셋
                existing_ids.add(id_last_6)  # 중복 방지용 추가 (뒤 6자리만)
                
                # 상세 정보 수집
                print(f"🔍 상세 정보 수집: {id_trimmed}")
                detail_info = fetch_detail_info(row_data['url'])
                
                # 수집 시간
                collected_time = format_date_time(datetime.now())
                
                # 데이터 구성 (기존 테이블 컬럼명에 맞춤)
                new_item = {
                    'announcement_id': row_data['id'],
                    'biz_pbanc_nm': row_data['title'],
                    'pbanc_ntrp_nm': row_data['org'],
                    'spnsr_organ_nm': row_data['supervisor'],
                    'exctv_organ_nm': row_data['executor'],
                    'extraction_date': collected_time,
                    'aply_trgt_ctnt': detail_info['supportTarget'],
                    'pbanc_ctnt': detail_info['supportContent'],
                    'attachment_urls': detail_info['attachmentLinks'],
                    'detl_pg_url': row_data['url'],
                    'status': '수집완료',
                    'created_at': collected_time
                }
                
                # 날짜 필드는 빈 값이 아닐 때만 추가 (올바른 컬럼명 사용)
                if detail_info['applicationStartDate']:
                    new_item['pbanc_rcpt_bgng_dt'] = detail_info['applicationStartDate']
                if detail_info['applicationEndDate']:
                    new_item['pbanc_rcpt_end_dt'] = detail_info['applicationEndDate']
                
                new_items.append(new_item)
                print(f"✅ 수집 완료: {row_data['title'][:30]}...")
                
                # 요청 간 딜레이
                time.sleep(0.1)
            
            # 루프 종료 조건 개선: 최소 검토 개수 + 중복 패턴 확인
            if total_checked >= min_check_count and duplicate_count >= max_duplicate_count:
                break
            
            # 페이지 제한 체크
            if page >= max_pages:
                print(f"📄 최대 페이지 수 ({max_pages}) 도달 - 수집 종료")
                break
                
            page += 1
            
        except Exception as e:
            print(f"❌ 페이지 {page} 처리 오류: {e}")
            break
    
    # 데이터베이스 저장
    if new_items:
        print(f"\n💾 데이터베이스에 {len(new_items)}개 저장 중...")
        try:
            # 배치로 삽입
            batch_size = 10
            for i in range(0, len(new_items), batch_size):
                batch = new_items[i:i+batch_size]
                result = supabase.table('kstartup_complete').insert(batch).execute()
                print(f"📝 배치 {i//batch_size + 1}: {len(batch)}개 저장 완료")
                time.sleep(0.5)  # 배치 간 딜레이
            
            print(f"✅ 총 {len(new_items)}개 새로운 공고 저장 완료!")
            
        except Exception as e:
            print(f"❌ 데이터베이스 저장 오류: {e}")
    else:
        print("ℹ️ 저장할 새로운 데이터가 없습니다.")
    
    print("\n" + "="*60)
    print("🎉 K-Startup 수집 완료")
    print(f"📊 총 검토: {total_checked}개")
    print(f"📊 새로운 공고: {len(new_items)}개")
    print(f"📋 수집 모드: {collection_mode} (최소 {min_check_count}개 검토)")
    print("="*60)

if __name__ == "__main__":
    collect_kstartup_data()