#!/usr/bin/env python3
"""
K-Startup 공공데이터 API 수집기 (첨부파일 포함 버전)
data.go.kr API + 웹 스크래핑으로 첨부파일 수집
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import unquote
import time
import re

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 수집 모드
COLLECTION_MODE = os.environ.get('COLLECTION_MODE', 'daily')

# API 설정
API_URL = "http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
SERVICE_KEY = "rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=="

# 세션 설정 (웹 스크래핑용)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
})

def parse_xml_item(item):
    """XML item 파싱 (col name 형식)"""
    data = {}
    
    # col 태그들에서 데이터 추출
    cols = item.findall('col')
    for col in cols:
        name = col.get('name')
        value = col.text if col.text else ''
        data[name] = value.strip()
    
    return data

def fetch_attachments_from_detail_page(detail_url):
    """상세페이지에서 첨부파일 추출"""
    try:
        response = session.get(detail_url, timeout=10)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        attachments = []
        
        # 다양한 첨부파일 링크 패턴 찾기
        # 1. 직접 다운로드 링크
        download_links = soup.find_all('a', href=re.compile(r'(/cmm/fms/FileDown\.do|/afile/fileDownload/|download\.do)'))
        
        for link in download_links:
            href = link.get('href', '')
            text = link.get_text(strip=True) or '첨부파일'
            
            # 절대 URL로 변환
            if href.startswith('/'):
                href = f"https://www.k-startup.go.kr{href}"
            
            # 중복 제거
            if href not in [a.get('url') for a in attachments]:
                attachments.append({
                    'url': href,
                    'filename': text,
                    'type': 'FILE'
                })
        
        # 2. onclick 형태의 다운로드
        onclick_links = soup.find_all('a', onclick=re.compile(r'fileDown|download'))
        for link in onclick_links:
            onclick = link.get('onclick', '')
            text = link.get_text(strip=True) or '첨부파일'
            
            # onclick에서 파일 ID 추출
            match = re.search(r"['\"](\d+)['\"]", onclick)
            if match:
                file_id = match.group(1)
                url = f"https://www.k-startup.go.kr/cmm/fms/FileDown.do?fileNo={file_id}"
                
                if url not in [a.get('url') for a in attachments]:
                    attachments.append({
                        'url': url,
                        'filename': text,
                        'type': 'FILE'
                    })
        
        return attachments
        
    except Exception as e:
        print(f"    [첨부파일 추출 오류]: {str(e)[:50]}")
        return []

def fetch_page(page_no, num_of_rows=100):
    """API에서 페이지 데이터 가져오기"""
    try:
        params = {
            'serviceKey': unquote(SERVICE_KEY),
            'pageNo': page_no,
            'numOfRows': num_of_rows
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            return None, 0, 0
        
        # XML 파싱
        try:
            root = ET.fromstring(response.content)
            
            # 전체 개수 확인
            total_count_elem = root.find('totalCount')
            total = int(total_count_elem.text) if total_count_elem is not None else 0
            
            # 데이터 추출
            data_elem = root.find('data')
            if data_elem is None:
                return [], total, 0
            
            # 아이템 리스트
            items = data_elem.findall('item')
            
            announcements = []
            for item in items:
                raw_data = parse_xml_item(item)
                
                # 필드 매핑 (테이블 컬럼에 맞게)
                ann = {}
                
                # pbanc_sn (공고번호)
                pbanc_sn = raw_data.get('pbanc_sn', '')
                if not pbanc_sn:
                    continue
                    
                ann['announcement_id'] = f"KS_{pbanc_sn}"
                ann['pbanc_sn'] = pbanc_sn
                
                # 필수 필드
                ann['biz_pbanc_nm'] = raw_data.get('biz_pbanc_nm') or raw_data.get('intg_pbanc_biz_nm', '')
                ann['pbanc_ctnt'] = raw_data.get('pbanc_ctnt', '')  # 공고내용
                ann['supt_biz_clsfc'] = raw_data.get('supt_biz_clsfc', '')  # 지원사업분류
                ann['aply_trgt_ctnt'] = raw_data.get('aply_trgt_ctnt', '')  # 지원대상내용
                ann['supt_regin'] = raw_data.get('supt_regin', '')  # 지원지역
                ann['pbanc_rcpt_bgng_dt'] = raw_data.get('pbanc_rcpt_bgng_dt', '')  # 접수시작일
                ann['pbanc_rcpt_end_dt'] = raw_data.get('pbanc_rcpt_end_dt', '')  # 접수종료일
                ann['pbanc_ntrp_nm'] = raw_data.get('pbanc_ntrp_nm', '')  # 공고기관명
                ann['biz_gdnc_url'] = raw_data.get('biz_gdnc_url', '')  # 사업안내URL
                ann['detl_pg_url'] = raw_data.get('detl_pg_url', '')  # 상세페이지URL
                
                # bsns_sumry는 pbanc_ctnt 사용
                ann['bsns_sumry'] = ann['pbanc_ctnt'][:5000] if ann['pbanc_ctnt'] else ''
                
                # 상태
                if raw_data.get('rcrt_prgs_yn') == 'Y':
                    ann['status'] = '모집중'
                else:
                    ann['status'] = '마감'
                    
                # 타임스탬프
                ann['created_at'] = datetime.now().isoformat()
                
                announcements.append(ann)
            
            return announcements, total, len(announcements)
            
        except ET.ParseError:
            return None, 0, 0
            
    except Exception:
        return None, 0, 0

def main():
    """메인 실행"""
    print("="*60)
    print(f"🚀 K-Startup 공공데이터 API 수집 시작 ({COLLECTION_MODE} 모드)")
    print("📎 첨부파일 수집 포함")
    print("="*60)
    
    # 기존 데이터 조회
    existing = supabase.table('kstartup_complete').select('announcement_id').execute()
    existing_ids = {item['announcement_id'] for item in existing.data} if existing.data else set()
    print(f"✅ 기존 데이터: {len(existing_ids)}개\n")
    
    # 첫 페이지로 전체 개수 확인
    items, total_count, _ = fetch_page(1, 10)
    
    if items is None:
        print("[ERROR] API 접근 실패")
        return
    
    print(f"📊 전체 공고 수: {total_count}개")
    
    # 모드별 설정
    if COLLECTION_MODE == 'full':
        # Full 모드는 최대 20페이지까지만 (2000개)
        total_pages = min(20, (total_count // 100) + 1)
        print(f"📊 Full 모드: {total_pages}페이지 수집 (최대 2000개)")
    else:
        # Daily 모드는 최대 3페이지 (300개)
        total_pages = min(3, (total_count // 100) + 1)
        print(f"📊 Daily 모드: {total_pages}페이지 수집 (최대 300개)")
    
    all_new = 0
    all_updated = 0
    all_attachments = 0
    errors = 0
    
    # 페이지별 수집
    for page in range(1, total_pages + 1):
        print(f"\n페이지 {page}/{total_pages} 처리중...")
        items, _, count = fetch_page(page, 100)
        
        if items is None:
            errors += 1
            continue
        
        if not items:
            print("  데이터 없음")
            break
        
        new_count = 0
        update_count = 0
        attach_count = 0
        page_errors = 0
        
        for item in items:
            try:
                # 첨부파일 수집 (새로운 공고만)
                if item['announcement_id'] not in existing_ids and item.get('detl_pg_url'):
                    attachments = fetch_attachments_from_detail_page(item['detl_pg_url'])
                    item['attachment_urls'] = attachments
                    item['attachment_count'] = len(attachments)
                    if attachments:
                        attach_count += 1
                else:
                    item['attachment_urls'] = []
                    item['attachment_count'] = 0
                
                if item['announcement_id'] in existing_ids:
                    # 기존 데이터 업데이트
                    result = supabase.table('kstartup_complete').update(
                        item
                    ).eq('announcement_id', item['announcement_id']).execute()
                    
                    if result.data:
                        update_count += 1
                else:
                    # 신규 데이터 삽입
                    result = supabase.table('kstartup_complete').insert(item).execute()
                    
                    if result.data:
                        new_count += 1
                        existing_ids.add(item['announcement_id'])
                        
            except Exception as e:
                page_errors += 1
                if page_errors <= 2:  # 처음 2개만 에러 표시
                    print(f"    [ERROR] {item['announcement_id']}: {str(e)[:100]}")
        
        all_new += new_count
        all_updated += update_count
        all_attachments += attach_count
        errors += page_errors
        
        print(f"  결과: 신규 {new_count}개, 업데이트 {update_count}개")
        print(f"  첨부파일: {attach_count}개 공고에서 수집")
        if page_errors > 0:
            print(f"  오류: {page_errors}개")
        
        # Daily 모드에서 신규가 없으면 조기 종료
        if COLLECTION_MODE == 'daily' and new_count == 0 and page > 1:
            print("\n연속 중복 - 조기 종료")
            break
        
        time.sleep(0.5)  # API 부하 방지
    
    # 최종 보고
    print("\n" + "="*60)
    print("📊 K-Startup 공공데이터 API 수집 완료")
    print("="*60)
    print(f"✅ 신규: {all_new}개")
    print(f"📝 업데이트: {all_updated}개")
    print(f"📎 첨부파일 수집: {all_attachments}개 공고")
    print(f"❌ 오류: {errors}개")
    print(f"📊 전체: {all_new + all_updated}개 처리")
    print("="*60)

if __name__ == "__main__":
    main()