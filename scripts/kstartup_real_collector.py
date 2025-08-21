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
        
        info = {
            'pbanc_rcpt_bgng_dt': None,
            'pbanc_rcpt_end_dt': None, 
            'sprt_cnts': None,
            'attachment_urls': []
        }
        
        # 기간 추출 (여러 패턴 시도)
        date_patterns = [
            r'접수기간.*?(\d{4}[-\.]\d{2}[-\.]\d{2}).*?(\d{4}[-\.]\d{2}[-\.]\d{2})',
            r'신청기간.*?(\d{4}[-\.]\d{2}[-\.]\d{2}).*?(\d{4}[-\.]\d{2}[-\.]\d{2})',
            r'(\d{4}[-\.]\d{2}[-\.]\d{2}).*?~.*?(\d{4}[-\.]\d{2}[-\.]\d{2})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                start_date = match.group(1).replace('.', '-')
                end_date = match.group(2).replace('.', '-')
                info['pbanc_rcpt_bgng_dt'] = start_date
                info['pbanc_rcpt_end_dt'] = end_date
                break
        
        # 지원내용 추출
        sprt_patterns = [
            r'지원내용[:\s]*([^<\n]{20,200})',
            r'지원규모[:\s]*([^<\n]{20,200})',
            r'지원금액[:\s]*([^<\n]{20,200})'
        ]
        
        for pattern in sprt_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                info['sprt_cnts'] = clean_text(match.group(1))
                break
        
        # 첨부파일 추출
        file_patterns = [
            r'href="([^"]*\.(pdf|hwp|doc|docx|xls|xlsx)[^"]*)"[^>]*>([^<]+)',
            r'onclick="[^"]*download[^"]*\([\'"]([^\'"]*)[\'"][^>]*>([^<]+)'
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    url = match[0] if match[0].startswith('http') else f"https://www.k-startup.go.kr{match[0]}"
                    filename = match[2] if len(match) > 2 else match[1]
                    file_ext = url.split('.')[-1].upper() if '.' in url else 'UNKNOWN'
                    
                    info['attachment_urls'].append({
                        'url': url,
                        'filename': clean_text(filename),
                        'type': file_ext
                    })
        
        return info
        
    except Exception as e:
        print(f"    ❌ 상세정보 추출 실패: {e}")
        return None

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚀 K-Startup 실제 데이터 수집 시작")
    print("=" * 60)
    
    # 환경변수 확인
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    COLLECTION_MODE = os.getenv('COLLECTION_MODE', 'daily').lower()
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ 환경변수 누락: SUPABASE_URL, SUPABASE_KEY")
        return
    
    print(f"📊 수집 모드: {COLLECTION_MODE}")
    print(f"🔗 Supabase URL: {SUPABASE_URL[:30]}...")
    
    # Supabase 연결
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase 연결 성공")
    except Exception as e:
        print(f"❌ Supabase 연결 실패: {e}")
        return
    
    # 기존 데이터 조회 (중복 체크용)
    try:
        existing_result = supabase.table('kstartup_complete').select('announcement_id').execute()
        # 뒤 6자리만 추출하여 집합으로 저장
        existing_ids = set()
        for row in existing_result.data:
            aid = str(row['announcement_id'])
            # 뒤 6자리 숫자만 추출 (KS_ 접두사 제거)
            if len(aid) >= 6:
                last_6 = aid[-6:] if aid[-6:].isdigit() else aid
                existing_ids.add(last_6)
        
        print(f"📋 기존 데이터: {len(existing_ids)}개 (뒤 6자리 기준)")
    except Exception as e:
        print(f"❌ 기존 데이터 조회 실패: {e}")
        existing_ids = set()
    
    # 수집 모드별 설정
    if COLLECTION_MODE == 'daily':
        print("📅 Daily 모드: 최신 데이터 확인")
        max_duplicate_count = 50  # 연속 중복 50개면 종료
        max_pages = 5  # 5페이지까지 확인 (1000개)
        min_check_count = 0  # 최소 검토 개수 제한 없음
    else:
        print("🔄 Full 모드: 전체 데이터 수집")
        max_duplicate_count = 200  # 연속 중복 200개면 종료
        max_pages = 50  # 50페이지까지 확인 (10000개)
        min_check_count = 100  # 최소 100개는 검토
    
    # 데이터 수집
    base_url = "https://www.k-startup.go.kr/api/apisvc/xml/GetPblancListSvc"
    new_items = []
    duplicate_count = 0
    total_checked = 0
    
    print(f"\n🔍 최대 {max_pages}페이지, 연속 중복 {max_duplicate_count}개까지 확인")
    
    for page in range(1, max_pages + 1):
        print(f"\n📄 페이지 {page} 처리 중...")
        
        try:
            params = {
                'page': page,
                'perPage': 200,  # 구글시트와 동일하게 200개
                'sortColumn': 'REG_YMD',
                'sortDirection': 'DESC'
            }
            
            response = requests.get(base_url, params=params, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"  ❌ HTTP 오류: {response.status_code}")
                continue
            
            # XML 파싱
            root = ET.fromstring(response.text)
            items = []
            
            # 아이템 찾기 (다양한 태그명 시도)
            for tag in ['item', 'items', 'pblanc']:
                found_items = root.findall(f".//{tag}")
                if found_items:
                    items = found_items
                    break
            
            if not items:
                print(f"  ⚠️ 페이지 {page}: 아이템 없음")
                continue
            
            print(f"  📊 페이지 {page}: {len(items)}개 아이템 발견")
            
            # 각 아이템 처리
            for item in items:
                total_checked += 1
                
                # ID 추출
                id_elem = item.find('pblancId') or item.find('pblanc_id') or item.find('id')
                if id_elem is None or not id_elem.text:
                    continue
                
                id_text = str(id_elem.text).strip()
                # 뒤 6자리만 추출
                id_trimmed = id_text.replace('KS_', '').replace('ks_', '')
                id_last_6 = id_trimmed[-6:] if len(id_trimmed) >= 6 and id_trimmed[-6:].isdigit() else id_trimmed
                
                if id_last_6 in existing_ids:
                    duplicate_count += 1
                    print(f"  ⚠️ 중복: {id_trimmed} → {id_last_6} ({duplicate_count}연속)")
                    
                    # 연속 중복이 max_duplicate_count에 도달하면 종료
                    if duplicate_count >= max_duplicate_count:
                        print(f"🔄 연속 중복 {max_duplicate_count}건 도달 - 수집 종료")
                        break
                    continue
                
                duplicate_count = 0  # 새 데이터 발견 시 리셋
                
                # 새 데이터 처리
                title_elem = item.find('pblancNm') or item.find('pblanc_nm') or item.find('title')
                title = title_elem.text if title_elem is not None else "제목 없음"
                
                print(f"  ✅ 새 데이터: {id_trimmed} - {title[:30]}...")
                
                # 상세 URL 생성
                detail_url = f"https://www.k-startup.go.kr/homepage/businessManage/businessManageDetail.do?bizPblancId={id_text}"
                
                # 상세정보 추출
                detail_info = fetch_detail_info(detail_url)
                
                # 기본 데이터 구성
                item_data = {
                    'announcement_id': id_text,
                    'biz_pbanc_nm': clean_text(title),
                    'detail_url': detail_url,
                    'collected_at': format_date_time(datetime.now())
                }
                
                # 상세정보 병합
                if detail_info:
                    item_data.update(detail_info)
                
                new_items.append(item_data)
                existing_ids.add(id_last_6)  # 중복 체크용 추가
                
                if len(new_items) >= 100:  # 한 번에 너무 많이 수집 방지
                    print(f"  🎯 100개 수집 완료 - 배치 저장")
                    break
            
            # 연속 중복으로 종료된 경우
            if duplicate_count >= max_duplicate_count:
                break
                
        except Exception as e:
            print(f"  ❌ 페이지 {page} 처리 실패: {e}")
            continue
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 수집 결과")
    print("=" * 60)
    print(f"🔍 총 검토: {total_checked}개")
    print(f"✅ 새 데이터: {len(new_items)}개")
    print(f"⚠️ 최종 중복: {duplicate_count}연속")
    
    # 데이터 저장
    if new_items:
        print(f"\n💾 Supabase에 {len(new_items)}개 저장 중...")
        try:
            # 배치로 저장 (100개씩)
            batch_size = 100
            saved_count = 0
            
            for i in range(0, len(new_items), batch_size):
                batch = new_items[i:i + batch_size]
                result = supabase.table('kstartup_complete').insert(batch).execute()
                saved_count += len(batch)
                print(f"  📦 배치 {i//batch_size + 1}: {len(batch)}개 저장")
            
            print(f"✅ 총 {saved_count}개 저장 완료!")
            
            # 최신 데이터 샘플 출력
            print(f"\n📋 저장된 데이터 샘플:")
            for i, item in enumerate(new_items[:3]):
                print(f"  {i+1}. {item['announcement_id']} - {item['biz_pbanc_nm'][:40]}...")
                if item.get('attachment_urls'):
                    print(f"     📎 첨부파일: {len(item['attachment_urls'])}개")
            
        except Exception as e:
            print(f"❌ 저장 실패: {e}")
    else:
        print("ℹ️ 저장할 새 데이터가 없습니다.")
    
    print("\n" + "=" * 60)
    print("🎉 수집 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()