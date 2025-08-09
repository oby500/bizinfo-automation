import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
import os
import xml.etree.ElementTree as ET
import time

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')
supabase = create_client(url, key)

print('🚀 K-Startup 전체 공고 수집 (배치 처리)')
print('='*60)

# API 설정
api_key = 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ=='
base_url = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'

# 현재 시간
now = datetime.now()
print(f'📅 실행 시간: {now.strftime("%Y-%m-%d %H:%M:%S")}')

# 기존 데이터 확인
print('\n📊 기존 데이터 확인...')
try:
    existing = supabase.table('kstartup_complete').select('announcement_id').execute()
    existing_ids = {item['announcement_id'] for item in existing.data}
    print(f'✅ 현재 저장된 공고: {len(existing_ids)}개')
except:
    existing_ids = set()
    print('⚠️ 기존 데이터 없음 (첫 수집)')

# 수집 통계
total_collected = 0
total_saved = 0
skipped_expired = 0
skipped_duplicate = 0
failed_count = 0

print('\n🔍 전체 공고 수집 시작...')

def parse_date(date_str):
    """날짜 문자열을 DATE 형식으로 변환"""
    if not date_str:
        return None
    try:
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
    except:
        return None

def get_element_text(item, tag_name, default=""):
    """XML 요소에서 안전하게 텍스트 추출"""
    element = item.find(tag_name)
    if element is not None and element.text:
        return element.text.strip()
    return default

# 첫 페이지로 전체 개수 확인
params = {
    'serviceKey': api_key,
    'pageNo': '1',
    'numOfRows': '1',
    'resultType': 'xml'
}

response = requests.get(base_url, params=params, timeout=30)
root = ET.fromstring(response.content)
total_count_elem = root.find('.//totalCount')
total_count = int(total_count_elem.text) if total_count_elem is not None else 0
print(f'📊 전체 공고 수: {total_count}개')

# 페이지 계산
items_per_page = 100
total_pages = (total_count + items_per_page - 1) // items_per_page
print(f'📄 총 {total_pages}페이지 처리 예정')

# 배치 처리 설정
BATCH_SIZE = 100  # 한 번에 저장할 레코드 수
batch_records = []  # 배치 저장용 리스트

def save_batch(records):
    """배치 데이터 저장"""
    if not records:
        return 0
    
    try:
        # 배치 insert
        result = supabase.table('kstartup_complete').insert(records).execute()
        print(f'   ✅ 배치 저장 완료: {len(records)}개')
        return len(records)
    except Exception as e:
        print(f'   ❌ 배치 저장 실패: {str(e)[:100]}')
        # 배치 실패 시 개별 저장 시도
        saved = 0
        for record in records:
            try:
                supabase.table('kstartup_complete').insert(record).execute()
                saved += 1
            except:
                pass
        if saved > 0:
            print(f'   ⚠️ 개별 저장으로 {saved}개 복구')
        return saved

# 모든 페이지 처리
for page_no in range(1, total_pages + 1):
    try:
        print(f'\n📄 페이지 {page_no}/{total_pages} 처리 중...')
        
        params = {
            'serviceKey': api_key,
            'pageNo': str(page_no),
            'numOfRows': str(items_per_page),
            'resultType': 'xml'
        }
        
        response = requests.get(base_url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f'❌ API 오류: {response.status_code}')
            continue
        
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        
        if not items:
            print(f'   데이터 없음')
            continue
        
        page_expired = 0
        page_duplicate = 0
        page_records = []  # 이 페이지의 레코드
        
        for item in items:
            total_collected += 1
            
            # 필수 필드 추출
            pbanc_sn = get_element_text(item, 'pbancSn')
            if not pbanc_sn:
                continue
            
            announcement_id = f'KS_{pbanc_sn}'
            
            # 중복 체크
            if announcement_id in existing_ids:
                skipped_duplicate += 1
                page_duplicate += 1
                continue
            
            # 마감일 확인
            end_date_str = get_element_text(item, 'pbancRcptEndDt')
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y%m%d')
                    if end_date < now:
                        skipped_expired += 1
                        page_expired += 1
                        continue  # 마감일 지난 공고 건너뛰기
                except:
                    pass
            
            # 데이터 수집
            title = get_element_text(item, 'bizPbancNm', '제목 없음')
            
            # 레코드 생성
            record = {
                'announcement_id': announcement_id,
                'pbanc_sn': pbanc_sn,
                'biz_pbanc_nm': title,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # 필드 매핑
            field_mapping = {
                'pbancCtnt': 'pbanc_ctnt',
                'suptBizClsfc': 'supt_biz_clsfc',
                'aplyTrgtCtnt': 'aply_trgt_ctnt',
                'suptRegin': 'supt_regin',
                'pbancRcptBgngDt': 'pbanc_rcpt_bgng_dt',
                'pbancRcptEndDt': 'pbanc_rcpt_end_dt',
                'pbancNtrpNm': 'pbanc_ntrp_nm',
                'bizGdncUrl': 'biz_gdnc_url',
                'bizAplyUrl': 'biz_aply_url'
            }
            
            for api_field, db_field in field_mapping.items():
                value = get_element_text(item, api_field)
                if value:
                    # 날짜 필드 변환
                    if 'Dt' in api_field and len(value) == 8:
                        value = parse_date(value)
                    record[db_field] = value
            
            # URL 생성
            record['detl_pg_url'] = f'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}'
            
            # bsns_sumry - 전체 내용 저장
            content = get_element_text(item, 'pbancCtnt', '')
            record['bsns_sumry'] = content if content else title
            
            # 추가 필드
            record['bsns_title'] = title
            record['spnsr_organ_nm'] = get_element_text(item, 'spnsrOrganNm')
            record['exctv_organ_nm'] = get_element_text(item, 'exctvOrganNm')
            record['recept_start_dt'] = record.get('pbanc_rcpt_bgng_dt')
            record['recept_end_dt'] = record.get('pbanc_rcpt_end_dt')
            record['support_type'] = record.get('supt_biz_clsfc')
            record['region'] = record.get('supt_regin')
            
            # 상태 계산
            if record.get('pbanc_rcpt_end_dt'):
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
            
            # 해시태그
            hashtags = []
            if record.get('supt_biz_clsfc'):
                hashtags.append(f"#{record['supt_biz_clsfc'].replace(' ', '_')}")
            if record.get('supt_regin'):
                hashtags.append(f"#{record['supt_regin'].replace(' ', '_')}")
            if record.get('status') == '마감임박':
                hashtags.append("#마감임박")
            record['hash_tag'] = " ".join(hashtags) if hashtags else None
            
            # 필수 필드
            record['attachment_urls'] = []
            record['attachment_count'] = 0
            record['attachment_processing_status'] = {}
            
            # 추가 데이터
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
            
            # 배치 리스트에 추가
            page_records.append(record)
            batch_records.append(record)
            existing_ids.add(announcement_id)  # 중복 방지용
            
            # 배치가 가득 차면 저장
            if len(batch_records) >= BATCH_SIZE:
                saved = save_batch(batch_records)
                total_saved += saved
                batch_records = []  # 배치 초기화
        
        # 페이지 결과
        print(f'   📊 페이지 {page_no}: 수집 {len(page_records)}개, 마감 {page_expired}개, 중복 {page_duplicate}개')
        
        # API 부하 방지
        time.sleep(0.3)
        
        # 진행률 표시 (10페이지마다)
        if page_no % 10 == 0:
            progress = (page_no / total_pages) * 100
            print(f'\n🔄 진행률: {progress:.1f}% ({page_no}/{total_pages})')
            print(f'   현재까지 저장: {total_saved}개')
            
            # 남은 배치 저장
            if batch_records:
                saved = save_batch(batch_records)
                total_saved += saved
                batch_records = []
        
    except Exception as e:
        print(f'❌ 페이지 {page_no} 오류: {e}')
        import traceback
        traceback.print_exc()
        continue

# 마지막 남은 배치 저장
if batch_records:
    print('\n📦 마지막 배치 저장 중...')
    saved = save_batch(batch_records)
    total_saved += saved

# 최종 결과
print('\n' + '='*60)
print('📊 전체 공고 수집 완료!')
print(f'  - 실행 시간: {now.strftime("%Y-%m-%d %H:%M:%S")}')
print(f'  - 처리한 페이지: {total_pages}페이지')
print(f'  - 전체 조회: {total_collected}개')
print(f'  - 신규 저장: {total_saved}개')
print(f'  - 마감 지난 공고: {skipped_expired}개')
print(f'  - 중복 제외: {skipped_duplicate}개')
print(f'  - 저장 실패: {failed_count}개')

# DB 최종 확인
try:
    final_result = supabase.table('kstartup_complete').select('announcement_id').execute()
    db_count = len(final_result.data) if final_result.data else 0
    print(f'  - DB 전체 저장된 공고: {db_count}개')
except:
    pass

print('\n✅ K-Startup 전체 데이터 수집 완료!')
print('💡 배치 처리로 빠르게 수집했습니다.')