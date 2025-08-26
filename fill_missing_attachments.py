#!/usr/bin/env python3
"""
첨부파일이 없는 K-Startup 공고들의 첨부파일 수집
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
from bs4 import BeautifulSoup
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import re
import time

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
})

def fetch_attachments_from_detail_page(detail_url):
    """상세페이지에서 첨부파일 추출 (구글시트 방식 추가)"""
    try:
        response = session.get(detail_url, timeout=10)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        attachments = []
        
        # 1. 구글시트 방식: download 속성이 있는 모든 링크
        download_attr_links = soup.find_all('a', attrs={'download': True})
        for link in download_attr_links:
            href = link.get('href', '')
            text = link.get_text(strip=True) or '첨부파일'
            
            if href and href not in ['#', 'javascript:void(0)']:
                if href.startswith('/'):
                    href = f"https://www.k-startup.go.kr{href}"
                
                if href not in [a.get('url') for a in attachments]:
                    attachments.append({
                        'url': href,
                        'filename': text,
                        'type': 'FILE'
                    })
        
        # 2. 기존 방식: 특정 URL 패턴
        download_links = soup.find_all('a', href=re.compile(r'(/cmm/fms/FileDown\.do|/afile/fileDownload/|download\.do)'))
        
        for link in download_links:
            href = link.get('href', '')
            text = link.get_text(strip=True) or '첨부파일'
            
            if href.startswith('/'):
                href = f"https://www.k-startup.go.kr{href}"
            
            if href not in [a.get('url') for a in attachments]:
                attachments.append({
                    'url': href,
                    'filename': text,
                    'type': 'FILE'
                })
        
        # onclick 형태
        onclick_links = soup.find_all('a', onclick=re.compile(r'fileDown|download'))
        for link in onclick_links:
            onclick = link.get('onclick', '')
            text = link.get_text(strip=True) or '첨부파일'
            
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
        return []

print("="*60)
print("K-Startup 첨부파일 보충 수집")
print("="*60)

# 첨부파일이 없는 공고 조회 (최근 것 위주)
result = supabase.table('kstartup_complete')\
    .select('announcement_id, detl_pg_url, biz_pbanc_nm')\
    .eq('attachment_count', 0)\
    .order('created_at', desc=True)\
    .limit(100)\
    .execute()

if not result.data:
    print("첨부파일이 없는 공고가 없습니다.")
else:
    print(f"첨부파일 수집 대상: {len(result.data)}개\n")
    
    success = 0
    found = 0
    
    for item in result.data[:30]:  # 우선 30개만
        ann_id = item['announcement_id']
        url = item['detl_pg_url']
        title = item['biz_pbanc_nm'][:40] if item['biz_pbanc_nm'] else ''
        
        if not url:
            continue
        
        print(f"처리: {ann_id} - {title}...")
        
        attachments = fetch_attachments_from_detail_page(url)
        
        if attachments:
            # 업데이트
            update_result = supabase.table('kstartup_complete')\
                .update({
                    'attachment_urls': attachments,
                    'attachment_count': len(attachments)
                })\
                .eq('announcement_id', ann_id)\
                .execute()
            
            if update_result.data:
                success += 1
                found += len(attachments)
                print(f"  [OK] {len(attachments)}개 첨부파일 발견")
            else:
                print(f"  [ERROR] 업데이트 실패")
        else:
            print(f"  [INFO] 첨부파일 없음")
        
        time.sleep(0.5)  # 서버 부하 방지
    
    print("\n" + "="*60)
    print(f"완료: {success}개 공고 업데이트")
    print(f"총 {found}개 첨부파일 수집")
    print("="*60)