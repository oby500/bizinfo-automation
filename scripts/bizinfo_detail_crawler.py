#!/usr/bin/env python3
"""
기업마당 상세페이지 크롤링 및 요약 생성 스크립트
- K-Startup 방식과 동일하게 2단계 처리
- 상세페이지에서 실제 내용 추출
- 의미있는 요약 생성
"""

import os
import json
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from supabase import create_client
from typing import List, Dict, Any, Optional
import time
import re

# Supabase 클라이언트 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("환경변수 오류: SUPABASE_URL 또는 SUPABASE_SERVICE_KEY가 설정되지 않았습니다.")
    exit(1)

supabase = create_client(url, key)

# 세션 재사용
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def calculate_d_day(end_date_str: str) -> str:
    """D-day 계산"""
    try:
        if not end_date_str:
            return ""
        
        # 날짜 파싱 (다양한 형식 대응)
        if isinstance(end_date_str, str):
            # YYYY-MM-DD 형식
            if '-' in end_date_str:
                end_date = datetime.strptime(end_date_str.split('T')[0], '%Y-%m-%d')
            # YYYY.MM.DD 형식
            elif '.' in end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y.%m.%d')
            else:
                return ""
        else:
            return ""
        
        today = datetime.now()
        diff = (end_date - today).days
        
        if diff < 0:
            return "마감"
        elif diff == 0:
            return "🚨 오늘마감"
        elif diff <= 3:
            return f"🚨 마감임박 D-{diff}"
        elif diff <= 7:
            return f"⏰ D-{diff}"
        else:
            return f"📆 D-{diff}"
            
    except:
        return ""

def extract_detail_content(pblanc_id: str) -> Dict[str, Any]:
    """상세페이지에서 내용 추출"""
    try:
        # 상세페이지 URL 구성
        detail_url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122S/AS/74/view.do?pblancId={pblanc_id}"
        
        response = session.get(detail_url, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 공고 내용 추출
        content_sections = {}
        
        # 사업목적
        purpose_elem = soup.find('th', text=re.compile('사업목적'))
        if purpose_elem:
            purpose_td = purpose_elem.find_next_sibling('td')
            if purpose_td:
                content_sections['purpose'] = purpose_td.get_text(strip=True)
        
        # 지원내용
        support_elem = soup.find('th', text=re.compile('지원내용|지원규모'))
        if support_elem:
            support_td = support_elem.find_next_sibling('td')
            if support_td:
                content_sections['support'] = support_td.get_text(strip=True)
        
        # 지원대상
        target_elem = soup.find('th', text=re.compile('지원대상|신청자격'))
        if target_elem:
            target_td = target_elem.find_next_sibling('td')
            if target_td:
                content_sections['target'] = target_td.get_text(strip=True)
        
        # 신청방법
        method_elem = soup.find('th', text=re.compile('신청방법|접수방법'))
        if method_elem:
            method_td = method_elem.find_next_sibling('td')
            if method_td:
                content_sections['method'] = method_td.get_text(strip=True)
        
        # 첨부파일 정보 추출
        attachments = []
        file_section = soup.find('div', class_='file_area') or soup.find('ul', class_='file_list')
        if file_section:
            for link in file_section.find_all('a'):
                file_name = link.get_text(strip=True)
                file_url = link.get('href', '')
                if file_name and file_url:
                    # 파일 확장자 추출
                    ext = 'unknown'
                    if '.' in file_name:
                        ext = file_name.split('.')[-1].lower()
                    
                    attachments.append({
                        'filename': file_name,
                        'url': f"https://www.bizinfo.go.kr{file_url}" if file_url.startswith('/') else file_url,
                        'extension': ext
                    })
        
        return {
            'content_sections': content_sections,
            'attachments': attachments,
            'crawled_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"상세페이지 크롤링 실패 ({pblanc_id}): {e}")
        return None

def generate_summary(item: Dict[str, Any], detail_content: Dict[str, Any]) -> str:
    """의미있는 요약 생성"""
    try:
        summary_parts = []
        
        # 제목
        title = item.get('pblanc_nm', '').strip()
        summary_parts.append(f"📋 {title}")
        
        # 주관기관
        organ = item.get('organ_nm', '') or item.get('spnsr_organ_nm', '')
        if organ:
            summary_parts.append(f"🏢 주관: {organ}")
        
        # 신청 기간
        start_date = item.get('reqst_begin_ymd', '')
        end_date = item.get('reqst_end_ymd', '')
        if start_date and end_date:
            # 날짜 형식 통일
            if 'T' in str(start_date):
                start_date = start_date.split('T')[0]
            if 'T' in str(end_date):
                end_date = end_date.split('T')[0]
            
            summary_parts.append(f"📅 기간: {start_date} ~ {end_date}")
            
            # D-day 추가
            d_day = calculate_d_day(end_date)
            if d_day:
                summary_parts.append(d_day)
        
        # 상세 내용에서 추출한 정보
        if detail_content and detail_content.get('content_sections'):
            sections = detail_content['content_sections']
            
            # 주요 내용 요약
            if sections.get('purpose'):
                purpose = sections['purpose'][:200]  # 최대 200자
                summary_parts.append(f"▶ 목적: {purpose}")
            
            if sections.get('support'):
                support = sections['support'][:200]
                summary_parts.append(f"▶ 지원: {support}")
            
            if sections.get('target'):
                target = sections['target'][:200]
                summary_parts.append(f"▶ 대상: {target}")
        
        # 첨부파일 정보
        if detail_content and detail_content.get('attachments'):
            attach_count = len(detail_content['attachments'])
            file_types = set()
            for att in detail_content['attachments']:
                ext = att.get('extension', 'unknown').upper()
                if ext != 'UNKNOWN':
                    file_types.add(ext)
            
            if file_types:
                summary_parts.append(f"📎 첨부: {', '.join(file_types)} ({attach_count}개)")
            else:
                summary_parts.append(f"📎 첨부: {attach_count}개")
        
        # 분야 태그
        categories = []
        if item.get('bsns_lclas_nm'):
            categories.append(item['bsns_lclas_nm'])
        if item.get('bsns_mlsfc_nm'):
            categories.append(item['bsns_mlsfc_nm'])
        
        if categories:
            summary_parts.append(f"🏷️ {' / '.join(categories)}")
        
        return '\n'.join(summary_parts)
        
    except Exception as e:
        print(f"요약 생성 실패: {e}")
        # 최소한의 요약 반환
        return f"📋 {item.get('pblanc_nm', '공고')} (상세 정보 처리 실패)"

def process_single_announcement(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """단일 공고 처리"""
    try:
        pblanc_id = item.get('pblanc_id', '')
        
        if not pblanc_id:
            return None
        
        # 상세페이지 크롤링
        detail_content = extract_detail_content(pblanc_id)
        
        # 요약 생성
        summary = generate_summary(item, detail_content)
        
        # 업데이트할 데이터 구성
        update_data = {
            'id': item['id'],
            'bsns_sumry': summary
        }
        
        # 첨부파일 정보가 있으면 추가
        if detail_content and detail_content.get('attachments'):
            update_data['attachment_urls'] = detail_content['attachments']
            update_data['attachment_count'] = len(detail_content['attachments'])
        
        return update_data
        
    except Exception as e:
        print(f"처리 오류 (ID: {item.get('id', 'unknown')}): {e}")
        return None

def batch_update_database(updates: List[Dict[str, Any]]):
    """배치로 데이터베이스 업데이트"""
    if not updates:
        return
    
    try:
        for update in updates:
            update_fields = {
                'bsns_sumry': update['bsns_sumry']
            }
            
            # 첨부파일 정보가 있으면 추가
            if 'attachment_urls' in update:
                update_fields['attachment_urls'] = update['attachment_urls']
                update_fields['attachment_count'] = update['attachment_count']
            
            supabase.table('bizinfo_complete').update(update_fields).eq('id', update['id']).execute()
        
        print(f"✅ {len(updates)}개 레코드 업데이트 완료")
    except Exception as e:
        print(f"❌ 배치 업데이트 실패: {e}")

def main():
    print("="*60)
    print("   기업마당 상세페이지 크롤링 및 요약 생성")
    print("="*60)
    
    # 처리 대상 조회 - bsns_sumry가 없거나 짧은 것
    print("\n1. 처리 대상 조회 중...")
    
    response = supabase.table('bizinfo_complete')\
        .select('id,pblanc_id,pblanc_nm,organ_nm,spnsr_organ_nm,reqst_begin_ymd,reqst_end_ymd,bsns_lclas_nm,bsns_mlsfc_nm,bsns_sumry')\
        .or_('bsns_sumry.is.null,bsns_sumry.eq.')\
        .execute()
    
    # 추가로 짧은 요약 (20자 미만) 조회
    short_response = supabase.table('bizinfo_complete')\
        .select('id,pblanc_id,pblanc_nm,organ_nm,spnsr_organ_nm,reqst_begin_ymd,reqst_end_ymd,bsns_lclas_nm,bsns_mlsfc_nm,bsns_sumry')\
        .execute()
    
    items_to_process = []
    
    # NULL이거나 빈 것 추가
    if response.data:
        items_to_process.extend(response.data)
    
    # 짧은 요약 필터링하여 추가
    if short_response.data:
        for item in short_response.data:
            sumry = item.get('bsns_sumry', '')
            if sumry and len(sumry) < 20:  # 20자 미만인 경우
                if item not in items_to_process:  # 중복 방지
                    items_to_process.append(item)
    
    total_count = len(items_to_process)
    print(f"처리 대상: {total_count}개")
    
    if total_count == 0:
        print("모든 데이터가 이미 처리되었습니다.")
        return
    
    # 병렬 처리
    print(f"\n2. 병렬 처리 시작 (Workers: 10)...")
    
    updates = []
    processed_count = 0
    batch_size = 20
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_single_announcement, item): item 
                  for item in items_to_process}
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                updates.append(result)
                processed_count += 1
                
                # 배치 크기에 도달하면 업데이트
                if len(updates) >= batch_size:
                    batch_update_database(updates)
                    updates = []
                
                # 진행상황 표시
                if processed_count % 10 == 0:
                    print(f"진행: {processed_count}/{total_count} ({processed_count*100/total_count:.1f}%)")
    
    # 남은 업데이트 처리
    if updates:
        batch_update_database(updates)
    
    # 최종 통계
    print("\n" + "="*60)
    print("   처리 완료")
    print("="*60)
    print(f"✅ 총 처리: {processed_count}개")
    
    # 처리 후 통계
    stats_response = supabase.table('bizinfo_complete')\
        .select('id,bsns_sumry')\
        .execute()
    
    if stats_response.data:
        total = len(stats_response.data)
        with_summary = sum(1 for item in stats_response.data 
                          if item.get('bsns_sumry') and len(item['bsns_sumry']) > 50)
        
        print(f"\n📊 전체 통계:")
        print(f"   - 전체 레코드: {total}개")
        print(f"   - 정상 요약 보유: {with_summary}개 ({with_summary*100/total:.1f}%)")
        print(f"   - 요약 필요: {total - with_summary}개")

if __name__ == "__main__":
    main()
