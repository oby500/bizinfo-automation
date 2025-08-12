#!/usr/bin/env python3
"""
기업마당 상세페이지 크롤링 - Selenium 버전
브라우저를 통한 실제 접근으로 차단 우회
"""

import os
import json
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from supabase import create_client
from typing import List, Dict, Any, Optional

# Supabase 클라이언트 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')

if not url or not key:
    print("환경변수 오류: SUPABASE_URL 또는 SUPABASE_SERVICE_KEY가 설정되지 않았습니다.")
    exit(1)

supabase = create_client(url, key)

def setup_driver():
    """Selenium 드라이버 설정"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver

def calculate_d_day(end_date_str: str) -> str:
    """D-day 계산"""
    try:
        if not end_date_str:
            return ""
        
        if isinstance(end_date_str, str):
            if '-' in end_date_str:
                end_date = datetime.strptime(end_date_str.split('T')[0], '%Y-%m-%d')
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

def extract_detail_content(driver, pblanc_id: str) -> Dict[str, Any]:
    """Selenium으로 상세페이지 크롤링"""
    try:
        # 상세페이지 URL
        detail_url = f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pblanc_id}"
        
        # 페이지 로드
        driver.get(detail_url)
        time.sleep(2)  # 페이지 로딩 대기
        
        # 내용 추출
        content_sections = {}
        attachments = []
        
        try:
            # 테이블에서 주요 정보 추출
            table = driver.find_element(By.CLASS_NAME, "view_table")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                try:
                    th = row.find_element(By.TAG_NAME, "th")
                    td = row.find_element(By.TAG_NAME, "td")
                    
                    th_text = th.text.strip()
                    td_text = td.text.strip()
                    
                    # 주요 필드 매핑
                    if '목적' in th_text or '개요' in th_text:
                        content_sections['purpose'] = td_text[:500]
                    elif '지원' in th_text and '내용' in th_text:
                        content_sections['support'] = td_text[:500]
                    elif '대상' in th_text or '자격' in th_text:
                        content_sections['target'] = td_text[:500]
                    elif '방법' in th_text or '접수' in th_text:
                        content_sections['method'] = td_text[:200]
                except:
                    continue
        except:
            print(f"테이블 파싱 실패: {pblanc_id}")
        
        # 첨부파일 추출
        try:
            # 다양한 선택자 시도
            file_elements = []
            
            # 방법 1: file_area
            try:
                file_area = driver.find_element(By.CLASS_NAME, "file_area")
                file_elements.extend(file_area.find_elements(By.TAG_NAME, "a"))
            except:
                pass
            
            # 방법 2: file_list
            try:
                file_list = driver.find_element(By.CLASS_NAME, "file_list")
                file_elements.extend(file_list.find_elements(By.TAG_NAME, "a"))
            except:
                pass
            
            # 방법 3: 다운로드 링크
            if not file_elements:
                file_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'atchFileId')]")
            
            for idx, elem in enumerate(file_elements, 1):
                try:
                    file_name = elem.text.strip()
                    file_url = elem.get_attribute('href')
                    
                    if file_name and file_url:
                        # 확장자 추출
                        ext = 'unknown'
                        if '.' in file_name:
                            ext = file_name.split('.')[-1].lower()
                        
                        attachments.append({
                            'filename': file_name,
                            'url': file_url,
                            'extension': ext,
                            'safe_filename': f"{pblanc_id}_{idx:02d}.{ext}",
                            'display_filename': file_name
                        })
                except:
                    continue
                    
        except Exception as e:
            print(f"첨부파일 추출 실패: {pblanc_id} - {e}")
        
        return {
            'content_sections': content_sections,
            'attachments': attachments,
            'crawled_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"상세페이지 크롤링 실패 ({pblanc_id}): {e}")
        return None

def generate_summary(item: Dict[str, Any], detail_content: Dict[str, Any]) -> str:
    """상세 요약 생성"""
    try:
        summary_parts = []
        
        # 제목
        title = item.get('pblanc_nm', '').strip()
        if title:
            summary_parts.append(f"📋 {title}")
        
        # 주관기관
        organ = item.get('organ_nm', '') or item.get('spnsr_organ_nm', '')
        if organ and organ != 'nan':
            summary_parts.append(f"🏢 주관: {organ}")
        
        # 신청 기간
        start_date = item.get('reqst_begin_ymd', '')
        end_date = item.get('reqst_end_ymd', '')
        if start_date and end_date:
            summary_parts.append(f"📅 기간: {start_date} ~ {end_date}")
            
            # D-day 추가
            d_day = calculate_d_day(end_date)
            if d_day:
                summary_parts.append(d_day)
        
        # 상세 내용 추가
        if detail_content and detail_content.get('content_sections'):
            sections = detail_content['content_sections']
            
            if sections.get('purpose'):
                summary_parts.append(f"\n▶ 목적: {sections['purpose'][:150]}...")
            
            if sections.get('support'):
                summary_parts.append(f"▶ 지원: {sections['support'][:150]}...")
            
            if sections.get('target'):
                summary_parts.append(f"▶ 대상: {sections['target'][:150]}...")
        
        # 첨부파일 정보
        if detail_content and detail_content.get('attachments'):
            attach_count = len(detail_content['attachments'])
            file_types = set()
            for att in detail_content['attachments']:
                ext = att.get('extension', '').upper()
                if ext and ext != 'UNKNOWN':
                    file_types.add(ext)
            
            if file_types:
                summary_parts.append(f"\n📎 첨부: {', '.join(file_types)} ({attach_count}개)")
            else:
                summary_parts.append(f"\n📎 첨부: {attach_count}개")
        
        return '\n'.join(summary_parts)
        
    except Exception as e:
        print(f"요약 생성 실패: {e}")
        return item.get('bsns_sumry', '')  # 기존 요약 유지

def main():
    print("="*60)
    print("   기업마당 상세페이지 크롤링 (Selenium)")
    print("="*60)
    
    # 처리 대상 조회
    print("\n1. 처리 대상 조회 중...")
    
    # 요약이 짧거나 첨부파일이 없는 데이터
    response = supabase.table('bizinfo_complete')\
        .select('id,pblanc_id,pblanc_nm,organ_nm,spnsr_organ_nm,reqst_begin_ymd,reqst_end_ymd,bsns_sumry')\
        .or_('attachment_urls.eq.[]')\
        .limit(50)\
        .execute()
    
    if not response.data:
        print("처리할 데이터가 없습니다.")
        return
    
    items_to_process = response.data
    total_count = len(items_to_process)
    print(f"처리 대상: {total_count}개")
    
    # Selenium 드라이버 설정
    print("\n2. 브라우저 초기화...")
    driver = setup_driver()
    
    try:
        processed_count = 0
        success_count = 0
        
        for idx, item in enumerate(items_to_process, 1):
            pblanc_id = item.get('pblanc_id', '')
            
            print(f"\n[{idx}/{total_count}] 처리 중: {pblanc_id}")
            
            # 상세페이지 크롤링
            detail_content = extract_detail_content(driver, pblanc_id)
            
            if detail_content:
                # 요약 생성
                summary = generate_summary(item, detail_content)
                
                # 업데이트 데이터 구성
                update_data = {
                    'bsns_sumry': summary
                }
                
                # 첨부파일 정보가 있으면 추가
                if detail_content.get('attachments'):
                    update_data['attachment_urls'] = detail_content['attachments']
                
                # DB 업데이트
                try:
                    supabase.table('bizinfo_complete').update(update_data).eq('id', item['id']).execute()
                    success_count += 1
                    print(f"  ✅ 업데이트 완료")
                except Exception as e:
                    print(f"  ❌ DB 업데이트 실패: {e}")
            else:
                print(f"  ⚠️ 크롤링 실패")
            
            processed_count += 1
            
            # 과부하 방지
            time.sleep(1)
            
    finally:
        driver.quit()
    
    # 최종 통계
    print("\n" + "="*60)
    print("   처리 완료")
    print("="*60)
    print(f"✅ 총 처리: {processed_count}개")
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패: {processed_count - success_count}개")

if __name__ == "__main__":
    main()
