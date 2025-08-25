#!/usr/bin/env python3
"""
K-Startup 일일 수집기 (워크플로우 호환 버전)
- daily/full 모드 지원
- 병렬 처리로 고속 수집
- 중복 체크 및 증분 업데이트
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
import json
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 수집 모드
COLLECTION_MODE = os.environ.get('COLLECTION_MODE', 'daily')

# 전역 변수
lock = threading.Lock()
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
})

progress = {
    'total': 0,
    'new': 0,
    'updated': 0,
    'skipped': 0,
    'errors': 0
}

def fetch_page(page):
    """페이지 데이터 가져오기"""
    url = "https://www.k-startup.go.kr/apigateway/ksus/bsns/anm/list"
    params = {
        'schClsfCd': 'PBC010',
        'sortType': 'recent',
        'currentPage': page,
        'perPage': 200,
        'searchStatus': '',
        'schStr': '',
        'schEdate': '',
        'returnType': 'JSON'
    }
    
    try:
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data and 'dataList' in data:
            return data['dataList']
    except Exception as e:
        print(f"   ❌ 페이지 {page} 오류: {e}")
    
    return []

def parse_detail_page(url, announcement_id):
    """상세페이지 파싱"""
    try:
        response = session.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # bsns_sumry 추출
        content_sections = []
        for selector in ['.content_wrap', '.detail_content', '.board_view']:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 100:
                    content_sections.append(text)
        
        bsns_sumry = ' '.join(content_sections[:3])[:5000] if content_sections else None
        
        # 첨부파일 추출
        attachments = []
        download_links = soup.find_all('a', href=lambda x: x and '/afile/fileDownload/' in x)
        
        for link in download_links:
            href = link.get('href', '')
            text = link.get_text(strip=True) or '첨부파일'
            
            if href.startswith('/'):
                href = f"https://www.k-startup.go.kr{href}"
            
            attachments.append({
                'url': href,
                'text': text,
                'type': 'FILE'
            })
        
        return bsns_sumry, attachments
        
    except Exception as e:
        print(f"   ❌ 상세페이지 파싱 오류: {e}")
        return None, []

def process_announcement(item):
    """공고 처리"""
    try:
        # 데이터 매핑
        announcement_id = f"KS_{item.get('pbancSn', '')}"
        
        # 상세페이지 URL 결정
        status = item.get('pbancSttsCd', '')
        pbanc_sn = item.get('pbancSn', '')
        
        if status == 'PBC030':  # 마감
            detail_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?schM=view&pbancSn={pbanc_sn}'
        else:  # 진행중
            detail_url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}'
        
        # 상세페이지 파싱
        bsns_sumry, attachments = parse_detail_page(detail_url, announcement_id)
        
        # 데이터 준비
        data = {
            'announcement_id': announcement_id,
            'pbanc_sn': item.get('pbancSn'),
            'biz_pbanc_nm': item.get('bizPbancNm', ''),
            'detl_pg_url': detail_url,
            'spt_fld_cn': item.get('sprtFldCn', ''),
            'spt_trgt_cn': item.get('pbancSuptTrgtCn', ''),
            'pbanc_bgng_dt': item.get('pbancBgngDt', ''),
            'pbanc_ddln_dt': item.get('pbancDdlnDt', ''),
            'bsns_sumry': bsns_sumry or item.get('bizPbancDtlCn', ''),
            'attachment_urls': attachments if attachments else [],
            'attachment_count': len(attachments),
            'status': '모집중' if status != 'PBC030' else '마감',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # DB 업서트
        result = supabase.table('kstartup_complete').upsert(
            data,
            on_conflict='announcement_id'
        ).execute()
        
        if result.data:
            with lock:
                if attachments:
                    progress['updated'] += 1
                else:
                    progress['new'] += 1
            return True
            
    except Exception as e:
        with lock:
            progress['errors'] += 1
        return False

def main():
    """메인 실행"""
    print("="*60)
    print(f"🚀 K-Startup 수집 시작 ({COLLECTION_MODE} 모드)")
    print("="*60)
    
    # 모드별 페이지 설정
    if COLLECTION_MODE == 'full':
        max_pages = 259  # 전체
        print("📊 Full 모드: 전체 데이터 수집")
    else:
        max_pages = 3  # daily는 최근 3페이지만
        print("📊 Daily 모드: 최근 600개만 확인")
    
    # 기존 데이터 ID 수집
    existing = supabase.table('kstartup_complete').select('announcement_id').execute()
    existing_ids = {item['announcement_id'] for item in existing.data} if existing.data else set()
    print(f"✅ 기존 데이터: {len(existing_ids)}개\n")
    
    all_items = []
    consecutive_duplicates = 0
    
    # 페이지별 수집
    for page in range(1, max_pages + 1):
        items = fetch_page(page)
        
        if not items:
            print(f"   페이지 {page}: 데이터 없음")
            break
        
        # 중복 체크
        new_items = []
        page_duplicates = 0
        
        for item in items:
            ann_id = f"KS_{item.get('pbancSn', '')}"
            if ann_id not in existing_ids:
                new_items.append(item)
            else:
                page_duplicates += 1
        
        all_items.extend(new_items)
        
        if new_items:
            print(f"   페이지 {page}: {len(new_items)}개 신규 (중복 {page_duplicates}개)")
            consecutive_duplicates = 0
        else:
            print(f"   페이지 {page}: 모두 중복 ({page_duplicates}개)")
            consecutive_duplicates += 1
        
        # 연속 중복 시 종료
        if consecutive_duplicates >= 3 and COLLECTION_MODE == 'daily':
            print(f"\n⚡ 연속 3페이지 중복 - 조기 종료")
            break
    
    progress['total'] = len(all_items)
    
    if not all_items:
        print("\n✅ 새로운 데이터 없음")
        return
    
    print(f"\n📊 처리할 신규 데이터: {len(all_items)}개")
    print("🔄 병렬 처리 시작...\n")
    
    # 병렬 처리
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_announcement, item) for item in all_items]
        
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                if i % 50 == 0:
                    print(f"   진행: {i}/{len(all_items)} ({i*100//len(all_items)}%)")
            except:
                pass
    
    # 최종 보고
    print("\n" + "="*60)
    print("📊 K-Startup 수집 완료")
    print("="*60)
    print(f"✅ 신규 추가: {progress['new']}개")
    print(f"📝 업데이트: {progress['updated']}개")
    print(f"⏭️  건너뜀: {progress['skipped']}개")
    print(f"❌ 오류: {progress['errors']}개")
    print("="*60)

if __name__ == "__main__":
    main()