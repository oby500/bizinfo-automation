#!/usr/bin/env python3
"""
K-Startup 공공데이터 API 수집기
data.go.kr API를 사용한 수집
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import requests
import xml.etree.ElementTree as ET
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import time
from urllib.parse import quote, unquote

load_dotenv()

def get_kst_time():
    """한국 시간(KST) 반환"""
    utc_now = datetime.utcnow()
    kst_now = utc_now + timedelta(hours=9)
    return kst_now

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# 수집 모드
COLLECTION_MODE = os.environ.get('COLLECTION_MODE', 'daily')

# API 설정
API_URL = "http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
SERVICE_KEY = "rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=="

def fetch_page(page_no, num_of_rows=100):
    """API에서 페이지 데이터 가져오기"""
    try:
        params = {
            'serviceKey': unquote(SERVICE_KEY),  # 디코딩된 키 사용
            'pageNo': page_no,
            'numOfRows': num_of_rows,
            'returnType': 'XML'  # XML 형식으로 요청
        }
        
        print(f"  페이지 {page_no} 요청중...")
        response = requests.get(API_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"    [ERROR] HTTP {response.status_code}")
            return None, 0, 0
        
        # XML 파싱
        try:
            root = ET.fromstring(response.content)
            
            # 헤더 정보
            header = root.find('.//header')
            if header is not None:
                result_code = header.find('resultCode')
                if result_code is not None and result_code.text != '00':
                    result_msg = header.find('resultMsg')
                    print(f"    [ERROR] API 오류: {result_msg.text if result_msg is not None else 'Unknown'}")
                    return None, 0, 0
            
            # 바디 정보
            body = root.find('.//body')
            if body is None:
                print(f"    [ERROR] body 없음")
                return None, 0, 0
            
            # 전체 개수와 페이지 정보
            total_count = body.find('totalCount')
            total = int(total_count.text) if total_count is not None else 0
            
            # 아이템 추출
            items = body.find('items')
            if items is None:
                return [], total, 0
            
            item_list = items.findall('item')
            
            announcements = []
            for item in item_list:
                # 각 필드 추출
                ann = {}
                
                # 필드 매핑
                field_map = {
                    'pbancSn': 'pbanc_sn',  # 공고일련번호
                    'bizPbancNm': 'biz_pbanc_nm',  # 사업공고명
                    'pbancBgngDt': 'pbanc_bgng_dt',  # 공고시작일
                    'pbancEndDt': 'pbanc_ddln_dt',  # 공고종료일
                    'pbancDdlnDt': 'pbanc_ddln_dt',  # 공고마감일
                    'dtlPgUrl': 'detl_pg_url',  # 상세페이지URL
                    'sprtFldCn': 'spt_fld_cn',  # 지원분야내용
                    'sprtTrgtCn': 'spt_trgt_cn',  # 지원대상내용
                    'pbancSuptTrgtCn': 'spt_trgt_cn',  # 지원대상내용(대체)
                    'bizPbancDtlCn': 'bsns_sumry',  # 사업공고상세내용
                    'pbancSttsCd': 'status_cd',  # 공고상태코드
                }
                
                for xml_field, db_field in field_map.items():
                    elem = item.find(xml_field)
                    if elem is not None and elem.text:
                        ann[db_field] = elem.text.strip()
                
                # announcement_id 생성
                if 'pbanc_sn' in ann:
                    ann['announcement_id'] = f"KS_{ann['pbanc_sn']}"
                    
                    # 상태 설정
                    status_cd = ann.get('status_cd', '')
                    if status_cd == 'PBC030':
                        ann['status'] = '마감'
                    else:
                        ann['status'] = '모집중'
                    
                    announcements.append(ann)
            
            return announcements, total, len(announcements)
            
        except ET.ParseError as e:
            print(f"    [ERROR] XML 파싱 오류: {e}")
            # JSON 시도
            try:
                data = response.json()
                if 'response' in data:
                    body = data['response'].get('body', {})
                    total = body.get('totalCount', 0)
                    items = body.get('items', {}).get('item', [])
                    
                    announcements = []
                    for item in items:
                        ann = {
                            'announcement_id': f"KS_{item.get('pbancSn', '')}",
                            'pbanc_sn': item.get('pbancSn'),
                            'biz_pbanc_nm': item.get('bizPbancNm'),
                            'pbanc_bgng_dt': item.get('pbancBgngDt'),
                            'pbanc_ddln_dt': item.get('pbancDdlnDt') or item.get('pbancEndDt'),
                            'detl_pg_url': item.get('dtlPgUrl'),
                            'spt_fld_cn': item.get('sprtFldCn'),
                            'spt_trgt_cn': item.get('sprtTrgtCn') or item.get('pbancSuptTrgtCn'),
                            'bsns_sumry': item.get('bizPbancDtlCn'),
                            'status': '마감' if item.get('pbancSttsCd') == 'PBC030' else '모집중'
                        }
                        announcements.append(ann)
                    
                    return announcements, total, len(announcements)
            except:
                print(f"    [ERROR] JSON 파싱도 실패")
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
        
        time.sleep(0.5)  # API 부하 방지
    
    # 최종 보고
    print("\n" + "="*60)
    print("📊 K-Startup 공공데이터 API 수집 완료")
    print("="*60)
    print(f"✅ 신규: {len(all_new)}개")
    print(f"📝 업데이트: {len(all_updated)}개")
    print(f"❌ 오류: {errors}개")
    print(f"📊 전체: {len(all_new) + len(all_updated)}개 처리")
    print("="*60)

if __name__ == "__main__":
    main()