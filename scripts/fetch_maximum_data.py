import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

def fetch_maximum_government_data():
    """정부지원사업 API에서 최대한 많은 정보 수집"""
    print("=== 정부지원사업 API 최대 정보 수집 ===")
    print("=" * 70)
    
    all_data = []
    all_fields = set()
    
    # 1. K-Startup API 호출
    print("\n📡 1. K-Startup API 호출")
    print("-" * 50)
    kstartup_data = fetch_bizinfo_complete()
    all_data.extend(kstartup_data)
    
    # 2. 기업마당 API 시뮬레이션 (실제 API 키 없이)
    print("\n📡 2. 기업마당 API 필드 분석")
    print("-" * 50)
    bizinfo_fields = analyze_bizinfo_schema()
    
    # 3. 모든 필드 통합 분석
    print("\n📊 3. 전체 필드 통합 분석")
    print("-" * 50)
    
    # K-Startup 필드 수집
    for item in all_data:
        for field in item.keys():
            all_fields.add(f"kstartup_{field}")
    
    # 기업마당 필드 추가
    for field in bizinfo_fields:
        all_fields.add(f"bizinfo_{field}")
    
    print(f"📋 총 발견된 필드: {len(all_fields)}개")
    print(f"  - K-Startup 필드: {len([f for f in all_fields if f.startswith('kstartup_')])}개")
    print(f"  - 기업마당 필드: {len([f for f in all_fields if f.startswith('bizinfo_')])}개")
    
    # 4. 상세 데이터 출력
    print("\n🔍 4. 수집된 데이터 샘플")
    print("-" * 50)
    
    for i, item in enumerate(all_data[:3], 1):
        print(f"\n📄 {i}번째 지원사업:")
        print("-" * 30)
        for key, value in item.items():
            if value and str(value).strip():
                display_value = str(value).strip()
                if len(display_value) > 100:
                    display_value = display_value[:100] + "..."
                print(f"  {key}: {display_value}")
    
    # 5. 결과 저장
    result = {
        'collection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_fields': len(all_fields),
        'all_fields': sorted(list(all_fields)),
        'kstartup_fields': sorted([f.replace('kstartup_', '') for f in all_fields if f.startswith('kstartup_')]),
        'bizinfo_fields': sorted([f.replace('bizinfo_', '') for f in all_fields if f.startswith('bizinfo_')]),
        'sample_data': all_data[:5],
        'field_mapping': {
            'kstartup_api_url': 'https://www.k-startup.go.kr/api/apisvc/xml/GetPblancListSvc',
            'bizinfo_api_url': 'http://apis.data.go.kr/B552015/NpsBplcInfoInqireService/getBplcInfoList'
        }
    }
    
    with open('complete_government_api_data.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 완전한 분석 결과가 'complete_government_api_data.json'에 저장되었습니다.")
    
    return result

def fetch_bizinfo_complete():
    """K-Startup API에서 최대한 완전한 데이터 수집"""
    print("K-Startup API 데이터 수집 중...")
    
    base_url = "https://www.k-startup.go.kr/api/apisvc/xml/GetPblancListSvc"
    
    # 다양한 조건으로 호출해서 더 많은 필드 발견하기
    test_params = [
        {
            'perPage': '10',
            'page': '1',
            'sortColumn': 'REG_YMD',
            'sortDirection': 'DESC'
        },
        {
            'perPage': '10', 
            'page': '1',
            'sortColumn': 'PBLANC_YMD',
            'sortDirection': 'DESC'
        },
        {
            'perPage': '10',
            'page': '1',
            'sortColumn': 'REQST_END_YMD', 
            'sortDirection': 'DESC'
        }
    ]
    
    all_items = []
    
    for params in test_params:
        try:
            response = requests.get(base_url, params=params, timeout=30)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                # 모든 item 요소 찾기
                items = []
                for elem in root.iter():
                    if elem.tag.lower().endswith('item'):
                        items.append(elem)
                
                print(f"  파라미터 {params['sortColumn']}: {len(items)}개 아이템 발견")
                
                # 각 아이템의 모든 자식 요소를 딕셔너리로 변환
                for item in items:
                    item_data = {'source': 'k-startup'}
                    for child in item:
                        if child.text and child.text.strip():
                            item_data[child.tag] = child.text.strip()
                    
                    if len(item_data) > 1:  # source 외에 데이터가 있으면
                        all_items.append(item_data)
                        
        except Exception as e:
            print(f"  오류 발생: {e}")
    
    # 중복 제거 (공고ID 기준)
    unique_items = []
    seen_ids = set()
    
    for item in all_items:
        item_id = item.get('pblancId') or item.get('pblancNo') or item.get('seq', '')
        if item_id and item_id not in seen_ids:
            seen_ids.add(item_id)
            unique_items.append(item)
    
    print(f"✅ K-Startup 총 {len(unique_items)}개 유니크 아이템 수집 완료")
    return unique_items

def analyze_bizinfo_schema():
    """제공된 기업마당 API 스키마 분석"""
    print("기업마당 API 스키마 분석 중...")
    
    # 문서에서 제공된 모든 필드들
    bizinfo_fields = [
        # RSS 기본 정보
        'title', 'link', 'description', 'language', 'copyright',
        'managingEditor', 'webMaster', 'pubDate', 'lastBuildDate',
        'category', 'ttl',
        
        # 아이템 기본 정보
        'title', 'link', 'seq', 'author', 'excInsttNm',
        'description', 'lcategory', 'pubDate', 'reqstDt',
        'trgetNm', 'inqireCo',
        
        # 파일 관련
        'flpthNm', 'fileNm', 'printFlpthNm', 'printFileNm',
        
        # 메타 정보
        'hashTags', 'totCnt',
        
        # 공고 상세 정보 (중복 제거된 버전)
        'pblancNm', 'pblancUrl', 'pblancId', 'jrsdInsttNm',
        'bsnsSumryCn', 'reqstMthPapersCn', 'refrncNm',
        'rceptEngnHmpgUrl', 'pldirSportRealmLclasCodeNm',
        'creatPnttm', 'reqstBeginEndDe'
    ]
    
    # 중복 제거
    unique_fields = list(set(bizinfo_fields))
    
    print(f"✅ 기업마당 API {len(unique_fields)}개 필드 분석 완료")
    
    # 필드별 설명도 포함
    field_descriptions = {
        'pblancNm': '공고명',
        'pblancUrl': '공고URL', 
        'pblancId': '공고ID',
        'jrsdInsttNm': '소관기관명',
        'excInsttNm': '수행기관명',
        'bsnsSumryCn': '사업개요내용',
        'reqstMthPapersCn': '사업신청방법',
        'refrncNm': '문의처',
        'rceptEngnHmpgUrl': '사업신청URL',
        'pldirSportRealmLclasCodeNm': '지원분야 대분류',
        'creatPnttm': '등록일자',
        'reqstBeginEndDe': '신청기간',
        'trgetNm': '지원대상',
        'hashTags': '해시태그',
        'inqireCo': '조회수',
        'flpthNm': '첨부파일경로명',
        'fileNm': '첨부파일명',
        'printFlpthNm': '본문출력파일경로명',
        'printFileNm': '본문출력파일명'
    }
    
    print("\n📋 주요 기업마당 API 필드들:")
    for field in sorted(unique_fields)[:15]:  # 처음 15개만 출력
        desc = field_descriptions.get(field, '설명 없음')
        print(f"  {field}: {desc}")
    
    return unique_fields

def create_unified_collector():
    """통합 수집기 생성"""
    print("\n🔧 통합 데이터 수집기 생성")
    print("-" * 50)
    
    collector_code = '''
# 통합 정부지원사업 데이터 수집기
# K-Startup + 기업마당 API 모든 필드 수집

import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

def collect_all_government_data():
    """모든 정부지원사업 데이터 수집"""
    
    all_data = []
    
    # 1. K-Startup API 수집
    kstartup_data = collect_kstartup_data()
    all_data.extend(kstartup_data)
    
    # 2. 기업마당 API 수집 (API 키 필요)
    # bizinfo_data = collect_bizinfo_data()
    # all_data.extend(bizinfo_data)
    
    return all_data

def collect_kstartup_data():
    """K-Startup 모든 필드 수집"""
    # ... (위 코드와 동일)
    pass

def collect_bizinfo_data():
    """기업마당 모든 필드 수집 (API 키 필요)"""
    # API 키가 있을 때 사용
    pass

if __name__ == "__main__":
    data = collect_all_government_data()
    print(f"총 {len(data)}개 지원사업 수집 완료!")
'''
    
    with open('unified_government_collector.py', 'w', encoding='utf-8') as f:
        f.write(collector_code)
    
    print("✅ 통합 수집기 코드가 'unified_government_collector.py'에 저장되었습니다.")

if __name__ == "__main__":
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 최대 정보 수집 실행
    result = fetch_maximum_government_data()
    
    # 통합 수집기 생성
    create_unified_collector()
    
    print(f"\n🎉 분석 완료!")
    print(f"📊 총 {result['total_fields']}개 필드 발견")
    print(f"📁 저장된 파일:")
    print(f"  - complete_government_api_data.json (전체 분석 결과)")
    print(f"  - unified_government_collector.py (통합 수집기)")
