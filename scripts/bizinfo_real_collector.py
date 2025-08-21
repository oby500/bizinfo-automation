#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bizinfo 실제 데이터 수집기 - 구글 시트 로직 기반
GitHub Actions용
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import time
import re
import json

# 환경변수 로드
load_dotenv()

def format_date_time(dt):
    """날짜+시간 포맷 YYYY-MM-DD HH:MM:SS"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def clean_text(text):
    """텍스트 정리"""
    if not text:
        return ""
    # HTML 태그 제거
    clean = re.sub(r'<[^>]*>', '', str(text))
    # 여러 공백을 하나로
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def extract_announcement_id(url):
    """공고 URL에서 ID 추출"""
    if not url:
        return ""
    
    # pblancId 파라미터 추출
    match = re.search(r'pblancId=([A-Z0-9_]+)', url)
    if match:
        return match.group(1)
    return ""

def fetch_bizinfo_excel_data():
    """기업마당 Excel 다운로드 및 파싱"""
    print("📊 기업마당 Excel 데이터 수집 중...")
    
    try:
        # Excel 다운로드 URL (실제 기업마당에서 제공하는 URL로 교체 필요)
        excel_url = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/excel.do"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(excel_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            print("✅ Excel 파일 다운로드 성공")
            # 실제 Excel 파싱 로직 구현 필요
            # pandas를 사용하여 Excel 파싱
            import pandas as pd
            import io
            
            df = pd.read_excel(io.BytesIO(response.content))
            print(f"📋 Excel 데이터: {len(df)}개 행")
            
            return df.to_dict('records')
        else:
            print(f"❌ Excel 다운로드 실패: {response.status_code}")
            return []
    
    except Exception as e:
        print(f"❌ Excel 데이터 수집 실패: {e}")
        return []

def fetch_bizinfo_rss_data():
    """기업마당 RSS 피드 데이터 수집"""
    print("📡 기업마당 RSS 데이터 수집 중...")
    
    try:
        rss_url = "https://www.bizinfo.go.kr/uss/rss/bizinfo.do"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(rss_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # RSS XML 파싱
            root = ET.fromstring(response.text)
            
            items = []
            for item in root.findall('.//item'):
                item_data = {}
                
                # 기본 RSS 필드
                title_elem = item.find('title')
                link_elem = item.find('link')
                desc_elem = item.find('description')
                pubdate_elem = item.find('pubDate')
                
                if title_elem is not None:
                    item_data['title'] = clean_text(title_elem.text)
                if link_elem is not None:
                    item_data['link'] = link_elem.text
                if desc_elem is not None:
                    item_data['description'] = clean_text(desc_elem.text)
                if pubdate_elem is not None:
                    item_data['pubDate'] = pubdate_elem.text
                
                # 공고ID 추출
                if 'link' in item_data:
                    item_data['announcement_id'] = extract_announcement_id(item_data['link'])
                
                items.append(item_data)
            
            print(f"✅ RSS 데이터: {len(items)}개 수집")
            return items
        else:
            print(f"❌ RSS 수집 실패: {response.status_code}")
            return []
    
    except Exception as e:
        print(f"❌ RSS 데이터 수집 실패: {e}")
        return []

def fetch_detail_info(detail_url):
    """상세페이지에서 추가 정보 수집"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(detail_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            detail_info = {
                'supervisor': '',
                'executor': '',
                'support_target': '',
                'support_content': '',
                'application_start_date': '',
                'application_end_date': '',
                'attachment_urls': []
            }
            
            # 각종 정보 추출 로직 구현
            # (실제 기업마당 페이지 구조에 맞춰 조정 필요)
            
            return detail_info
        
        return {}
    
    except Exception as e:
        print(f"⚠️ 상세 정보 수집 실패: {detail_url} - {e}")
        return {}

def collect_bizinfo_data():
    """기업마당 데이터 수집 메인 함수"""
    print("="*60)
    print("🏢 기업마당 실제 데이터 수집 시작")
    print("="*60)
    
    # 수집 모드 확인
    collection_mode = os.getenv('COLLECTION_MODE', 'daily')
    print(f"📋 수집 모드: {collection_mode}")
    
    if collection_mode == 'daily':
        print("📅 Daily 모드: 최근 RSS 피드만 수집")
        max_items = 20  # 최대 20개 항목
    else:
        print("🔄 Full 모드: 전체 RSS 피드 + 추가 소스 수집")
        max_items = 100  # 최대 100개 항목
    
    # Supabase 연결
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase 환경변수가 설정되지 않았습니다.")
        return
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase 연결 성공")
    
    # 기존 공고ID 조회
    try:
        existing_result = supabase.table('bizinfo_complete').select('announcement_id').execute()
        existing_ids = set()
        if existing_result.data:
            existing_ids = {str(item['announcement_id']).strip() for item in existing_result.data if item.get('announcement_id')}
        print(f"📋 기존 공고 수: {len(existing_ids)}개")
    except Exception as e:
        print(f"⚠️ 기존 데이터 조회 실패, 계속 진행: {e}")
        existing_ids = set()
    
    # 데이터 수집
    new_items = []
    
    # 1. RSS 데이터 수집
    rss_items = fetch_bizinfo_rss_data()
    
    # 2. 각 항목 처리 (모드별 제한)
    processed_count = 0
    for item in rss_items:
        if processed_count >= max_items:
            print(f"📊 최대 처리 항목 수 ({max_items}) 도달 - 수집 종료")
            break
        
        processed_count += 1
        announcement_id = item.get('announcement_id', '')
        
        if not announcement_id:
            print("⚠️ 공고ID 없음 - 건너뜀")
            continue
        
        if announcement_id in existing_ids:
            print(f"⚠️ 중복: {announcement_id}")
            continue
        
        print(f"🔍 새 공고 처리: {announcement_id}")
        
        # 상세 정보 수집
        detail_url = item.get('link', '')
        detail_info = fetch_detail_info(detail_url) if detail_url else {}
        
        # 수집 시간
        collected_time = format_date_time(datetime.now())
        
        # 데이터 구성
        new_item = {
            'announcement_id': announcement_id,
            'title': item.get('title', ''),
            'description': item.get('description', ''),
            'announcement_url': item.get('link', ''),
            'supervisor': detail_info.get('supervisor', ''),
            'executor': detail_info.get('executor', ''),
            'support_target': detail_info.get('support_target', ''),
            'support_content': detail_info.get('support_content', ''),
            'application_start_date': detail_info.get('application_start_date', ''),
            'application_end_date': detail_info.get('application_end_date', ''),
            'attachment_urls': json.dumps(detail_info.get('attachment_urls', []), ensure_ascii=False),
            'source': '기업마당',
            'status': '수집완료',
            'created_at': collected_time,
            'updated_at': collected_time
        }
        
        new_items.append(new_item)
        existing_ids.add(announcement_id)
        
        # 요청 간 딜레이
        time.sleep(0.2)
    
    # 데이터베이스 저장
    if new_items:
        print(f"\n💾 데이터베이스에 {len(new_items)}개 저장 중...")
        try:
            # 배치로 삽입
            batch_size = 10
            for i in range(0, len(new_items), batch_size):
                batch = new_items[i:i+batch_size]
                result = supabase.table('bizinfo_complete').insert(batch).execute()
                print(f"📝 배치 {i//batch_size + 1}: {len(batch)}개 저장 완료")
                time.sleep(0.5)  # 배치 간 딜레이
            
            print(f"✅ 총 {len(new_items)}개 새로운 공고 저장 완료!")
            
        except Exception as e:
            print(f"❌ 데이터베이스 저장 오류: {e}")
    else:
        print("ℹ️ 저장할 새로운 데이터가 없습니다.")
    
    print("\n" + "="*60)
    print("🎉 기업마당 수집 완료")
    print(f"📊 새로운 공고: {len(new_items)}개")
    print("="*60)

if __name__ == "__main__":
    collect_bizinfo_data()