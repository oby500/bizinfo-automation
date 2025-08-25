#!/usr/bin/env python3
"""
K-Startup 스마트 일일 수집
- 최근 200개(2페이지)만 확인
- announcement_id로 중복 체크
- 신규 공고만 저장
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
import os
import xml.etree.ElementTree as ET
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

# Supabase 설정
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

# API 설정
API_KEY = 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=='
BASE_URL = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'

# 설정
CHECK_PAGES = 2  # 최근 200개 확인 (100개씩 2페이지)
ITEMS_PER_PAGE = 100
MAX_WORKERS = 10

# 전역 통계
lock = threading.Lock()
stats = {
    'checked': 0,
    'new': 0,
    'duplicate': 0,
    'expired': 0
}

def parse_date(date_str):
    """날짜 변환"""
    if not date_str or len(date_str) != 8:
        return None
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

def get_element_text(item, tag_name, default=""):
    """XML 요소 추출 - 새로운 API 형식 지원"""
    # 먼저 표준 XML 형식 시도
    element = item.find(tag_name)
    if element is not None and element.text:
        return element.text.strip()
    
    # <col name=""> 형식 시도
    for col in item.findall('col'):
        name = col.get('name')
        if name == tag_name and col.text:
            return col.text.strip()
    
    return default

def process_page(page_no, existing_ids, now):
    """단일 페이지 처리"""
    local_new = []
    
    try:
        # API 호출
        params = {
            'serviceKey': API_KEY,
            'pageNo': str(page_no),
            'numOfRows': str(ITEMS_PER_PAGE),
            'resultType': 'xml'
        }
        
        response = requests.get(BASE_URL, params=params, timeout=10)
        if response.status_code != 200:
            print(f"   ❌ 페이지 {page_no} API 오류: {response.status_code}")
            return []
        
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        
        page_new = 0
        page_dup = 0
        page_exp = 0
        
        for item in items:
            # 필수 정보 추출 (새 API는 snake_case, 이전 API는 CamelCase)
            pbanc_sn = get_element_text(item, 'pbanc_sn')
            if not pbanc_sn:
                pbanc_sn = get_element_text(item, 'pbancSn')  # 이전 형식 호환성
            if not pbanc_sn:
                continue
            
            announcement_id = f'KS_{pbanc_sn}'
            
            # 중복 체크 (ID 기준)
            if announcement_id in existing_ids:
                page_dup += 1
                continue
            
            # 마감일 체크 (새 API는 snake_case)
            end_date_str = get_element_text(item, 'pbanc_rcpt_end_dt')
            if not end_date_str:
                end_date_str = get_element_text(item, 'pbancRcptEndDt')  # 이전 형식 호환성
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y%m%d')
                    if end_date < now:
                        page_exp += 1
                        continue  # 마감된 공고 스킵
                except:
                    pass
            
            # 신규 공고 - 전체 데이터 수집
            title = get_element_text(item, 'biz_pbanc_nm')  # 새 API (snake_case)
            if not title:
                title = get_element_text(item, 'bizPbancNm', '제목 없음')  # 이전 API (CamelCase)
            
            record = {
                'announcement_id': announcement_id,
                'biz_pbanc_nm': title,
                'pbanc_ctnt': get_element_text(item, 'pbanc_ctnt') or get_element_text(item, 'pbancCtnt'),
                'supt_biz_clsfc': get_element_text(item, 'supt_biz_clsfc') or get_element_text(item, 'suptBizClsfc'),
                'aply_trgt_ctnt': get_element_text(item, 'aply_trgt_ctnt') or get_element_text(item, 'aplyTrgtCtnt'),
                'supt_regin': get_element_text(item, 'supt_regin') or get_element_text(item, 'suptRegin'),
                'pbanc_rcpt_bgng_dt': parse_date(get_element_text(item, 'pbanc_rcpt_bgng_dt') or get_element_text(item, 'pbancRcptBgngDt')),
                'pbanc_rcpt_end_dt': parse_date(get_element_text(item, 'pbanc_rcpt_end_dt') or get_element_text(item, 'pbancRcptEndDt')),
                'pbanc_ntrp_nm': get_element_text(item, 'pbanc_ntrp_nm') or get_element_text(item, 'pbancNtrpNm'),
                'biz_gdnc_url': get_element_text(item, 'biz_gdnc_url') or get_element_text(item, 'bizGdncUrl'),
                'biz_aply_url': get_element_text(item, 'biz_aply_url') or get_element_text(item, 'bizAplyUrl'),
                'detl_pg_url': f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}',
                'bsns_title': title,
                'spnsr_organ_nm': get_element_text(item, 'spnsr_organ_nm') or get_element_text(item, 'spnsrOrganNm'),
                'exctv_organ_nm': get_element_text(item, 'exctv_organ_nm') or get_element_text(item, 'exctvOrganNm'),
                'recept_start_dt': parse_date(get_element_text(item, 'pbanc_rcpt_bgng_dt') or get_element_text(item, 'pbancRcptBgngDt')),
                'recept_end_dt': parse_date(get_element_text(item, 'pbanc_rcpt_end_dt') or get_element_text(item, 'pbancRcptEndDt')),
                'support_type': get_element_text(item, 'supt_biz_clsfc') or get_element_text(item, 'suptBizClsfc'),
                'region': get_element_text(item, 'supt_regin') or get_element_text(item, 'suptRegin'),
                'attachment_urls': [],
                'attachment_count': 0,
                'attachment_processing_status': {},
                'created_at': datetime.now().isoformat()
            }
            
            # bsns_sumry (새 API는 snake_case)
            content = get_element_text(item, 'pbanc_ctnt') or get_element_text(item, 'pbancCtnt', '')
            record['bsns_sumry'] = content if content else title
            
            # 상태 계산
            if record['pbanc_rcpt_end_dt']:
                try:
                    end_date = datetime.strptime(record['pbanc_rcpt_end_dt'].replace('-', ''), '%Y%m%d')
                    days_left = (end_date - now).days
                    if days_left < 0:
                        record['status'] = '마감'
                    elif days_left <= 7:
                        record['status'] = '마감임박'
                    else:
                        record['status'] = '모집중'
                except:
                    record['status'] = '상태미정'
            else:
                record['status'] = '상태미정'
            
            # 해시태그 (테이블에 hash_tag 컬럼이 없으므로 주석 처리)
            # hashtags = []
            # if record.get('supt_biz_clsfc'):
            #     hashtags.append(f"#{record['supt_biz_clsfc'].replace(' ', '_')}")
            # if record.get('supt_regin'):
            #     hashtags.append(f"#{record['supt_regin'].replace(' ', '_')}")
            # if record['status'] == '마감임박':
            #     hashtags.append("#마감임박")
            # record['hash_tag'] = " ".join(hashtags) if hashtags else None
            
            # 추가 필드
            additional_data = {}
            extra_fields = {
                'bizEnyy': 'biz_enyy',
                'aplyExclTrgtCtnt': 'aply_excl_trgt_ctnt',
                'bizTrgtAge': 'biz_trgt_age',
                'prchCnplNo': 'prch_cnpl_no',
                'sprvInst': 'sprv_inst',
                'aplyTrgt': 'aply_trgt',
                'intgPbancYn': 'intg_pbanc_yn',
                'bizPrchDprtNm': 'biz_prch_dprt_nm',
                'aplyMthdOnliRcptIstc': 'aply_mthd_onli_rcpt_istc',
                'rcrtPrgsYn': 'rcrt_prgs_yn'
            }
            
            for api_field, db_field in extra_fields.items():
                value = get_element_text(item, api_field)
                if value:
                    additional_data[db_field] = value
            
            if additional_data:
                record['col_additional'] = additional_data
            
            local_new.append(record)
            page_new += 1
        
        # 통계 업데이트
        with lock:
            stats['checked'] += len(items)
            stats['new'] += page_new
            stats['duplicate'] += page_dup
            stats['expired'] += page_exp
        
        print(f"   📄 페이지 {page_no}: 확인 {len(items)}개 | 신규 {page_new}개 | 중복 {page_dup}개 | 마감 {page_exp}개")
        
        return local_new
        
    except Exception as e:
        print(f"   ❌ 페이지 {page_no} 오류: {str(e)[:100]}")
        return []

def main():
    """메인 실행"""
    print('🚀 K-Startup 스마트 일일 수집')
    print('='*60)
    
    now = datetime.now()
    print(f'📅 실행 시간: {now.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'🔍 확인 범위: 최근 {CHECK_PAGES * ITEMS_PER_PAGE}개 공고')
    
    # 1. 기존 ID 목록 가져오기
    print('\n📊 기존 데이터 확인...')
    existing_ids = set()
    try:
        # ID만 가져오기 (빠른 조회)
        result = supabase.table('kstartup_complete').select('announcement_id').execute()
        existing_ids = {item['announcement_id'] for item in result.data}
        print(f'✅ DB에 저장된 공고: {len(existing_ids)}개')
    except Exception as e:
        print(f'⚠️ DB 조회 실패: {e}')
        existing_ids = set()
    
    # 2. 최근 200개 병렬 확인
    print(f'\n🔍 최근 {CHECK_PAGES}페이지 확인 중...')
    start_time = time.time()
    
    all_new_records = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 모든 페이지 동시 처리
        futures = {executor.submit(process_page, page, existing_ids, now): page 
                  for page in range(1, CHECK_PAGES + 1)}
        
        for future in as_completed(futures):
            try:
                records = future.result()
                if records:
                    all_new_records.extend(records)
            except Exception as e:
                print(f"❌ 작업 실패: {e}")
    
    # 3. 신규 데이터만 저장
    if all_new_records:
        print(f'\n💾 신규 공고 {len(all_new_records)}개 저장 중...')
        
        try:
            # 배치 저장
            result = supabase.table('kstartup_complete').insert(all_new_records).execute()
            print(f'✅ {len(all_new_records)}개 저장 완료!')
            
            # 신규 공고 상세
            print('\n📋 신규 공고:')
            for rec in all_new_records[:5]:  # 처음 5개만 표시
                deadline = rec.get('recept_end_dt', '미정')
                print(f"   • [{rec['status']}] {rec['biz_pbanc_nm'][:40]}")
                print(f"     마감: {deadline} | 지역: {rec.get('region', '전국')}")
            
            if len(all_new_records) > 5:
                print(f"   ... 외 {len(all_new_records)-5}개")
                
        except Exception as e:
            print(f'❌ 저장 실패: {e}')
            # 개별 저장 시도
            saved = 0
            for record in all_new_records:
                try:
                    supabase.table('kstartup_complete').insert(record).execute()
                    saved += 1
                except:
                    pass
            if saved > 0:
                print(f'⚠️ 개별 저장으로 {saved}개 복구')
    else:
        print('\n✅ 신규 공고 없음 (모두 최신 상태)')
    
    # 4. 결과 요약
    elapsed = time.time() - start_time
    
    print('\n' + '='*60)
    print('📊 수집 완료!')
    print(f'⏱️ 소요 시간: {elapsed:.1f}초')
    print(f'🔍 확인한 공고: {stats["checked"]}개')
    print(f'✅ 신규 저장: {stats["new"]}개')
    print(f'🔄 중복 제외: {stats["duplicate"]}개')
    print(f'🚫 마감 제외: {stats["expired"]}개')
    
    # 최종 DB 상태
    try:
        final = supabase.table('kstartup_complete').select('announcement_id').execute()
        print(f'💾 DB 전체: {len(final.data)}개')
    except:
        pass
    
    print('='*60)
    
    # 신규 공고가 있으면 후속 처리 안내
    if all_new_records:
        print('\n💡 후속 처리 필요:')
        print('   1. python kstartup_ultra_fast_parser.py  # 상세 파싱')
        print('   2. python kstartup_attachment_fix.py     # 첨부파일')

if __name__ == "__main__":
    main()
