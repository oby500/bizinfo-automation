#!/usr/bin/env python3
"""
K-Startup 웹 스크래핑 수집기 (API 변경 대응)
웹페이지를 직접 파싱하여 데이터 수집
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
import re
import time

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 수집 모드
COLLECTION_MODE = os.environ.get('COLLECTION_MODE', 'daily')

# 세션 설정
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://www.k-startup.go.kr/'
})

def parse_list_page(page_num, status='ongoing'):
    """목록 페이지 파싱"""
    if status == 'ongoing':
        url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=list&page={page_num}'
    else:
        url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?schM=list&page={page_num}'
    
    try:
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            print(f"[ERROR] 페이지 {page_num} 로드 실패: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # JavaScript에서 데이터 추출
        announcements = []
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string and 'pbancSn' in script.string:
                # 정규식으로 공고 데이터 추출
                # pbancSn 패턴 찾기
                pbanc_pattern = r'pbancSn["\s]*:["\s]*"?(\d+)"?'
                title_pattern = r'bizPbancNm["\s]*:["\s]*"([^"]+)"'
                deadline_pattern = r'pbancDdlnDt["\s]*:["\s]*"([^"]+)"'
                
                pbanc_matches = re.findall(pbanc_pattern, script.string)
                title_matches = re.findall(title_pattern, script.string)
                deadline_matches = re.findall(deadline_pattern, script.string)
                
                # 매칭된 데이터 조합
                for i in range(len(pbanc_matches)):
                    if i < len(title_matches):
                        ann = {
                            'pbancSn': pbanc_matches[i],
                            'bizPbancNm': title_matches[i] if i < len(title_matches) else '',
                            'pbancDdlnDt': deadline_matches[i] if i < len(deadline_matches) else '',
                            'status': '모집중' if status == 'ongoing' else '마감'
                        }
                        announcements.append(ann)
        
        # HTML에서 직접 추출 시도 (대안)
        if not announcements:
            # 목록 아이템 찾기
            list_items = soup.select('.list-item, .board-list li, .notice-list li, .biz-list li')
            
            for item in list_items:
                # 링크에서 pbancSn 추출
                link = item.find('a', href=re.compile(r'pbancSn=(\d+)'))
                if link:
                    pbanc_sn = re.search(r'pbancSn=(\d+)', link.get('href', '')).group(1)
                    title_elem = item.select_one('.tit, .title, h3, h4')
                    deadline_elem = item.select_one('.date, .deadline, .period')
                    
                    ann = {
                        'pbancSn': pbanc_sn,
                        'bizPbancNm': title_elem.text.strip() if title_elem else '',
                        'pbancDdlnDt': deadline_elem.text.strip() if deadline_elem else '',
                        'status': '모집중' if status == 'ongoing' else '마감'
                    }
                    announcements.append(ann)
        
        return announcements
        
    except Exception as e:
        print(f"[ERROR] 페이지 파싱 오류: {e}")
        return []

def parse_detail_page(pbanc_sn, status='ongoing'):
    """상세 페이지 파싱"""
    if status == '모집중':
        url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}'
    else:
        url = f'https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?schM=view&pbancSn={pbanc_sn}'
    
    try:
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            return None, []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 사업 요약 추출
        content_elem = soup.select_one('.content-wrap, .detail-content, .board-view, .view-content')
        bsns_sumry = content_elem.get_text(strip=True)[:5000] if content_elem else ''
        
        # 첨부파일 추출
        attachments = []
        file_links = soup.find_all('a', href=re.compile(r'/afile/fileDownload/|download\.do'))
        
        for link in file_links:
            href = link.get('href', '')
            if href.startswith('/'):
                href = f'https://www.k-startup.go.kr{href}'
            
            text = link.get_text(strip=True) or '첨부파일'
            attachments.append({
                'url': href,
                'text': text,
                'type': 'FILE'
            })
        
        return bsns_sumry, attachments
        
    except Exception as e:
        print(f"[ERROR] 상세페이지 파싱 오류: {e}")
        return None, []

def main():
    """메인 실행"""
    print("="*60)
    print(f"🚀 K-Startup 웹 스크래핑 수집 시작 ({COLLECTION_MODE} 모드)")
    print("="*60)
    
    # 기존 데이터 조회
    existing = supabase.table('kstartup_complete').select('announcement_id').execute()
    existing_ids = {item['announcement_id'] for item in existing.data} if existing.data else set()
    print(f"✅ 기존 데이터: {len(existing_ids)}개\n")
    
    all_announcements = []
    
    # 모드별 페이지 설정
    if COLLECTION_MODE == 'full':
        max_pages = 50  # 전체 페이지
        statuses = ['ongoing', 'deadline']
    else:
        max_pages = 5  # daily는 최근 5페이지만
        statuses = ['ongoing']  # 진행중만
    
    # 각 상태별로 수집
    for status in statuses:
        print(f"\n📋 {status.upper()} 공고 수집")
        
        for page in range(1, max_pages + 1):
            print(f"  페이지 {page} 처리중...")
            
            announcements = parse_list_page(page, status)
            
            if not announcements:
                print(f"    데이터 없음 - 종료")
                break
            
            # 중복 체크
            new_items = []
            for ann in announcements:
                ann_id = f"KS_{ann['pbancSn']}"
                if ann_id not in existing_ids:
                    ann['announcement_id'] = ann_id
                    new_items.append(ann)
            
            if new_items:
                all_announcements.extend(new_items)
                print(f"    {len(new_items)}개 신규 발견")
            else:
                print(f"    모두 중복")
                if COLLECTION_MODE == 'daily':
                    break  # daily 모드에서는 중복 페이지 만나면 종료
            
            time.sleep(0.5)  # 서버 부하 방지
    
    if not all_announcements:
        print("\n✅ 새로운 데이터 없음")
        return
    
    print(f"\n📊 처리할 신규 데이터: {len(all_announcements)}개")
    print("🔄 상세 정보 수집 시작...\n")
    
    # 상세 정보 수집 및 저장
    success = 0
    errors = 0
    
    for i, ann in enumerate(all_announcements, 1):
        try:
            print(f"  [{i}/{len(all_announcements)}] {ann['announcement_id']} 처리중...")
            
            # 상세 페이지 파싱
            bsns_sumry, attachments = parse_detail_page(ann['pbancSn'], ann['status'])
            
            # 데이터 준비
            data = {
                'announcement_id': ann['announcement_id'],
                'pbanc_sn': ann['pbancSn'],
                'biz_pbanc_nm': ann['bizPbancNm'],
                'pbanc_ddln_dt': ann.get('pbancDdlnDt', ''),
                'status': ann['status'],
                'bsns_sumry': bsns_sumry or '',
                'attachment_urls': attachments,
                'attachment_count': len(attachments),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # 상세 URL 설정
            if ann['status'] == '모집중':
                data['detl_pg_url'] = f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={ann['pbancSn']}"
            else:
                data['detl_pg_url'] = f"https://www.k-startup.go.kr/web/contents/bizpbanc-deadline.do?schM=view&pbancSn={ann['pbancSn']}"
            
            # DB 저장
            result = supabase.table('kstartup_complete').upsert(
                data,
                on_conflict='announcement_id'
            ).execute()
            
            if result.data:
                success += 1
                print(f"    [OK] 저장 완료")
            else:
                errors += 1
                print(f"    [ERROR] 저장 실패")
            
            time.sleep(1)  # 서버 부하 방지
            
        except Exception as e:
            errors += 1
            print(f"    [ERROR] 처리 실패: {e}")
    
    # 최종 보고
    print("\n" + "="*60)
    print("📊 K-Startup 웹 스크래핑 수집 완료")
    print("="*60)
    print(f"✅ 성공: {success}개")
    print(f"❌ 실패: {errors}개")
    print(f"📊 전체: {success + errors}개")
    print("="*60)

if __name__ == "__main__":
    main()