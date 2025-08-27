#!/usr/bin/env python3
"""
K-Startup 공공데이터 API 수집기 (새로운 형식 대응)
data.go.kr API의 변경된 XML 형식 처리
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
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import unquote
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

def fetch_page(page_no, num_of_rows=100):
    """API에서 페이지 데이터 가져오기"""
    try:
        params = {
            'serviceKey': unquote(SERVICE_KEY),
            'pageNo': page_no,
            'numOfRows': num_of_rows
        }
        
        print(f"  페이지 {page_no} 요청중...")
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"    [ERROR] HTTP {response.status_code}")
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
                print(f"    [ERROR] data 태그 없음")
                return [], total, 0
            
            # 아이템 리스트
            items = data_elem.findall('item')
            
            announcements = []
            for item in items:
                raw_data = parse_xml_item(item)
                
                # 필드 매핑
                ann = {}
                
                # pbanc_sn (공고번호)
                if 'pbanc_sn' in raw_data:
                    ann['announcement_id'] = f"KS_{raw_data['pbanc_sn']}"
                    ann['pbanc_sn'] = raw_data['pbanc_sn']
                elif 'pbancSn' in raw_data:
                    ann['announcement_id'] = f"KS_{raw_data['pbancSn']}"
                    ann['pbanc_sn'] = raw_data['pbancSn']
                else:
                    continue  # 공고번호 없으면 스킵
                
                # 공고명
                ann['biz_pbanc_nm'] = raw_data.get('biz_pbanc_nm') or raw_data.get('intg_pbanc_biz_nm', '')
                
                # 날짜
                ann['pbanc_bgng_dt'] = raw_data.get('pbanc_rcpt_bgng_dt', '')
                ann['pbanc_ddln_dt'] = raw_data.get('pbanc_rcpt_end_dt', '')
                
                # URL
                ann['detl_pg_url'] = raw_data.get('detl_pg_url', '')
                
                # 지원 정보
                ann['spt_fld_cn'] = raw_data.get('supt_regin', '')  # 지원지역
                ann['spt_trgt_cn'] = raw_data.get('aply_trgt', '')  # 지원대상
                
                # 사업 요약
                ann['bsns_sumry'] = raw_data.get('pbanc_ctnt', '')
                
                # 상태 (모집 진행 여부)
                if raw_data.get('rcrt_prgs_yn') == 'Y':
                    ann['status'] = '모집중'
                else:
                    ann['status'] = '마감'
                
                # 기관 정보
                ann['pblanc_ntce_instt_nm'] = raw_data.get('pbanc_ntrp_nm', '')  # 공고기관
                
                announcements.append(ann)
            
            return announcements, total, len(announcements)
            
        except ET.ParseError as e:
            print(f"    [ERROR] XML 파싱 오류: {e}")
            return None, 0, 0
            
    except requests.exceptions.Timeout:
        print(f"    [ERROR] 타임아웃")
        return None, 0, 0
    except Exception as e:
        print(f"    [ERROR] 예외: {e}")
        return None, 0, 0

def main():
    """메인 실행"""
    print("="*60)
    print(f"🚀 K-Startup 공공데이터 API 수집 시작 ({COLLECTION_MODE} 모드)")
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
    
    # 모드별 페이지 계산
    if COLLECTION_MODE == 'full':
        total_pages = (total_count // 100) + 1
        print(f"📊 Full 모드: 전체 {total_pages}페이지 수집")
    else:
        total_pages = min(5, (total_count // 100) + 1)  # 최대 5페이지 (500개)
        print(f"📊 Daily 모드: 최근 {total_pages}페이지만 수집")
    
    all_new = []
    all_updated = []
    errors = 0
    
    # 페이지별 수집
    for page in range(1, total_pages + 1):
        items, _, count = fetch_page(page, 100)
        
        if items is None:
            errors += 1
            continue
        
        if not items:
            print(f"  페이지 {page}: 데이터 없음")
            break
        
        new_items = []
        updated_items = []
        
        for item in items:
            if item['announcement_id'] not in existing_ids:
                new_items.append(item)
            else:
                # 기존 데이터도 업데이트 (상태 변경 등)
                updated_items.append(item)
        
        print(f"  페이지 {page}: {count}개 (신규 {len(new_items)}개, 업데이트 {len(updated_items)}개)")
        
        # DB 저장
        for ann in new_items + updated_items:
            try:
                # 타임스탬프 추가
                ann['created_at'] = get_kst_time().isoformat()
                ann['updated_at'] = get_kst_time().isoformat()
                
                # 첨부파일 관련 필드 (나중에 별도 처리)
                ann['attachment_urls'] = []
                ann['attachment_count'] = 0
                
                # upsert (있으면 업데이트, 없으면 삽입)
                result = supabase.table('kstartup_complete').upsert(
                    ann,
                    on_conflict='announcement_id'
                ).execute()
                
                if result.data:
                    if ann in new_items:
                        all_new.append(ann['announcement_id'])
                    else:
                        all_updated.append(ann['announcement_id'])
                        
            except Exception as e:
                errors += 1
                print(f"    [ERROR] {ann['announcement_id']} 저장 실패: {e}")
        
        # daily 모드에서 연속 중복시 조기 종료
        if COLLECTION_MODE == 'daily' and len(new_items) == 0 and page > 2:
            print("  연속 중복 - 조기 종료")
            break
    
    # 최종 보고
    print("\n" + "="*60)
    print("📊 K-Startup 공공데이터 API 수집 완료")
    print("="*60)
    print(f"✅ 신규: {len(all_new)}개")
    print(f"📝 업데이트: {len(all_updated)}개")
    print(f"❌ 오류: {errors}개")
    print(f"📊 전체: {len(all_new) + len(all_updated)}개 처리")
    
    # 최근 수집된 데이터 표시
    if all_new:
        print(f"\n📋 최근 추가된 공고 (최대 5개):")
        recent = supabase.table('kstartup_complete').select('announcement_id, biz_pbanc_nm, pbanc_ddln_dt').in_('announcement_id', all_new[:5]).execute()
        if recent.data:
            for item in recent.data:
                title = item.get('biz_pbanc_nm', '')[:50]
                deadline = item.get('pbanc_ddln_dt', '')
                print(f"  - [{item['announcement_id']}] {title}")
                print(f"    마감: {deadline}")
    
    print("="*60)

if __name__ == "__main__":
    main()