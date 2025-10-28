#!/usr/bin/env python3
"""
K-Startup 공공데이터 API 수집기 (첨부파일 포함 버전)
data.go.kr API + 웹 스크래핑으로 첨부파일 수집
"""
import sys

def get_kst_time():
    """한국 시간(KST) 반환"""
    from datetime import datetime, timedelta
    utc_now = datetime.utcnow()
    kst_now = utc_now + timedelta(hours=9)
    return kst_now

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
url = os.environ.get('SUPABASE_URL', 'https://csuziaogycciwgxxmahm.supabase.co')
key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')

# 키가 없으면 하드코딩된 값 사용
if not key:
    key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzdXppYW9neWNjaXdneHhtYWhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYxNTc4MCwiZXhwIjoyMDY5MTkxNzgwfQ.HnhM7zSLzi7lHVPd2IVQKIACDq_YA05mBMgZbSN1c9Q'

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

def fetch_attachments_and_dates_from_detail_page(detail_url):
    """
    상세페이지에서 첨부파일 및 날짜 정보 추출
    Returns: tuple (attachments: list, start_date: str, end_date: str)
    """
    try:
        response = session.get(detail_url, timeout=10)
        if response.status_code != 200:
            return [], None, None

        soup = BeautifulSoup(response.text, 'html.parser')
        attachments = []
        start_date = None
        end_date = None

        # === 첨부파일 수집 ===
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

        # === 날짜 정보 수집 ===
        all_text = soup.get_text()

        # 패턴 1: "접수기간 YYYY-MM-DD ~ YYYY-MM-DD" 형식
        date_range_pattern = r'(?:접수기간|신청기간|모집기간)\s*[:\s]*(\d{4}[-./]\d{1,2}[-./]\d{1,2})\s*~\s*(\d{4}[-./]\d{1,2}[-./]\d{1,2})'
        match = re.search(date_range_pattern, all_text)
        if match:
            start_date = match.group(1).replace('.', '-').replace('/', '-')
            end_date = match.group(2).replace('.', '-').replace('/', '-')

        # 패턴 2: 테이블에서 찾기 (패턴 1 실패 시)
        if not start_date or not end_date:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        header = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)

                        if any(kw in header for kw in ['접수기간', '신청기간', '모집기간']):
                            # 값에서 날짜 추출
                            dates = re.findall(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', value)
                            if len(dates) >= 2:
                                start_date = dates[0].replace('.', '-').replace('/', '-')
                                end_date = dates[1].replace('.', '-').replace('/', '-')
                                break
                if start_date and end_date:
                    break

        return attachments, start_date, end_date

    except Exception as e:
        print(f"    [상세페이지 추출 오류]: {str(e)[:50]}")
        return [], None, None

def fetch_page(page_no, num_of_rows=200):  # 구글시트처럼 200개씩 가져오기
    """API에서 페이지 데이터 가져오기"""
    try:
        params = {
            'serviceKey': unquote(SERVICE_KEY),
            'page': page_no,  # pageNo  page로 변경 (구글시트와 동일)
            'perPage': num_of_rows  # numOfRows  perPage로 변경
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
                # ann['pbanc_sn'] = pbanc_sn  # 우리 테이블에는 이 컬럼이 없음
                
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
                ann['created_at'] = get_kst_time().isoformat()
                
                announcements.append(ann)
            
            return announcements, total, len(announcements)
            
        except ET.ParseError:
            return None, 0, 0
            
    except Exception:
        return None, 0, 0

def main():
    """메인 실행"""
    print("="*60)
    print(f" K-Startup 공공데이터 API 수집 시작 ({COLLECTION_MODE} 모드)")
    print(" 첨부파일 수집 포함")
    print("="*60)
    
    # 기존 데이터 조회 (전체 가져오기 - Supabase는 기본 1000개 제한이 있음)
    # 여러 페이지로 나눠서 가져오기
    print(" 기존 데이터 로딩 중...")
    existing_ids = set()
    offset = 0
    limit = 1000
    page_count = 0
    while True:
        existing = supabase.table('kstartup_complete').select('announcement_id').range(offset, offset + limit - 1).execute()
        if not existing.data:
            break

        page_count += 1
        for item in existing.data:
            existing_ids.add(item['announcement_id'])

        print(f" - 페이지 {page_count}: {len(existing.data)}개 로드 (누적: {len(existing_ids)}개)")

        # 1000개 미만이면 마지막 페이지
        if len(existing.data) < limit:
            break

        offset += limit

    print(f" ✅ 기존 데이터: {len(existing_ids)}개 로드 완료\n")
    
    # 첫 페이지로 전체 개수 확인
    items, total_count, _ = fetch_page(1, 10)
    
    if items is None:
        print("[ERROR] API 접근 실패")
        return
    
    print(f" 전체 공고 수: {total_count}개")
    
    # 모드별 설정
    if COLLECTION_MODE == 'full':
        # Full 모드는 최대 20페이지까지만 (2000개)
        total_pages = min(20, (total_count // 100) + 1)
        print(f" Full 모드: {total_pages}페이지 수집 (최대 2000개)")
    else:
        # Daily 모드는 최대 3페이지 (300개)
        total_pages = min(3, (total_count // 100) + 1)
        print(f" Daily 모드: {total_pages}페이지 수집 (최대 300개)")
    
    all_new = 0
    all_updated = 0
    all_attachments = 0
    errors = 0
    
    # 연속 중복 카운터 (구글시트 방식)
    consecutive_duplicates = 0
    
    # 페이지별 수집
    for page in range(1, total_pages + 1):
        print(f"\n페이지 {page}/{total_pages} 처리중...")
        items, _, count = fetch_page(page, 200)  # 200개씩 가져오기
        
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
        page_duplicates = 0  # 페이지별 중복 수
        
        for item in items:
            try:
                # 첨부파일 및 날짜 정보 수집
                needs_scraping = (
                    item['announcement_id'] not in existing_ids and item.get('detl_pg_url')
                ) or (
                    # 날짜 정보가 없는 경우에도 스크래핑 시도
                    not item.get('pbanc_rcpt_bgng_dt') or not item.get('pbanc_rcpt_end_dt')
                )

                if needs_scraping and item.get('detl_pg_url'):
                    attachments, start_date, end_date = fetch_attachments_and_dates_from_detail_page(item['detl_pg_url'])
                    item['attachment_urls'] = attachments

                    # API에서 날짜가 없으면 스크래핑한 날짜 사용
                    if not item.get('pbanc_rcpt_bgng_dt') and start_date:
                        item['pbanc_rcpt_bgng_dt'] = start_date
                        print(f"    [날짜 스크래핑] {item['announcement_id']}: {start_date} ~ {end_date}")

                    if not item.get('pbanc_rcpt_end_dt') and end_date:
                        item['pbanc_rcpt_end_dt'] = end_date

                    if attachments:
                        attach_count += 1
                else:
                    item['attachment_urls'] = []
                
                if item['announcement_id'] in existing_ids:
                    # 기존 데이터 - 중복 카운트
                    page_duplicates += 1
                    consecutive_duplicates += 1
                    
                    # 연속 50개 중복 시 종료 (구글시트는 10개지만 우리는 좀 더 여유있게)
                    if consecutive_duplicates >= 50:
                        print(f"\n 연속 {consecutive_duplicates}개 중복  수집 종료")
                        all_new += new_count
                        all_updated += update_count
                        all_attachments += attach_count
                        # 최종 보고서로 이동
                        break
                    
                    # 기존 데이터 업데이트 (첨부파일이 없던 경우에만)
                    if len(item.get('attachment_urls', [])) > 0:
                        existing_attach = supabase.table('kstartup_complete').select('attachment_urls').eq('announcement_id', item['announcement_id']).execute()
                        if existing_attach.data and len(existing_attach.data[0].get('attachment_urls', [])) == 0:
                            # 기존에 첨부파일이 없었으면 업데이트
                            result = supabase.table('kstartup_complete').update({
                                'attachment_urls': item['attachment_urls']
                            }).eq('announcement_id', item['announcement_id']).execute()
                            
                            if result.data:
                                update_count += 1
                else:
                    # 신규 데이터 삽입
                    consecutive_duplicates = 0  # 신규 데이터면 중복 카운터 리셋
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
        
        print(f"  결과: 신규 {new_count}개, 업데이트 {update_count}개, 중복 {page_duplicates}개")
        print(f"  첨부파일: {attach_count}개 공고에서 수집")
        if page_errors > 0:
            print(f"  오류: {page_errors}개")
        
        # 연속 중복으로 종료된 경우
        if consecutive_duplicates >= 50:
            break
        
        time.sleep(0.5)  # API 부하 방지
    
    # 최종 보고
    print("\n" + "="*60)
    print(" K-Startup 공공데이터 API 수집 완료")
    print("="*60)
    print(f" 신규: {all_new}개")
    print(f" 업데이트: {all_updated}개")
    print(f" 첨부파일 수집: {all_attachments}개 공고")
    print(f" 오류: {errors}개")
    print(f" 전체: {all_new + all_updated}개 처리")
    print("="*60)

if __name__ == "__main__":
    main()