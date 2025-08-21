import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json

def analyze_complete_kstartup_api():
    print("=== K-Startup API 완전 필드 분석 ===")
    print("=" * 60)
    
    base_url = "https://www.k-startup.go.kr/api/apisvc/xml/GetPblancListSvc"
    
    # 여러 조건으로 테스트
    test_cases = [
        {
            'name': '등록일 기준 최신 5개',
            'params': {
                'perPage': '5',
                'page': '1',
                'sortColumn': 'REG_YMD',
                'sortDirection': 'DESC'
            }
        },
        {
            'name': '공고일 기준 최신 5개',
            'params': {
                'perPage': '5', 
                'page': '1',
                'sortColumn': 'PBLANC_YMD',
                'sortDirection': 'DESC'
            }
        },
        {
            'name': '접수마감일 기준 최신 5개',
            'params': {
                'perPage': '5',
                'page': '1', 
                'sortColumn': 'REQST_END_YMD',
                'sortDirection': 'DESC'
            }
        }
    ]
    
    all_fields = set()  # 모든 필드를 수집
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📡 {i}. {test_case['name']}")
        print("-" * 50)
        print(f"파라미터: {test_case['params']}")
        
        try:
            response = requests.get(base_url, params=test_case['params'], timeout=30)
            print(f"응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                print(f"응답 크기: {len(response.content)} bytes")
                
                # XML 파싱
                root = ET.fromstring(response.text)
                print(f"XML 루트: {root.tag}")
                
                # 구조 분석
                def analyze_structure(element, path="", level=0):
                    current_path = f"{path}/{element.tag}" if path else element.tag
                    
                    if level < 4:  # 4레벨까지만 출력
                        indent = "  " * level
                        if element.text and element.text.strip():
                            value = element.text.strip()
                            if len(value) > 50:
                                value = value[:50] + "..."
                            print(f"{indent}{element.tag}: {value}")
                        else:
                            print(f"{indent}{element.tag}")
                    
                    # 모든 태그 수집
                    if 'item' in element.tag.lower() or level > 0:
                        all_fields.add(element.tag)
                    
                    for child in element:
                        analyze_structure(child, current_path, level + 1)
                
                # 아이템 찾기
                items = []
                for elem in root.iter():
                    if 'item' in elem.tag.lower():
                        items.append(elem)
                
                print(f"발견된 아이템: {len(items)}개")
                
                if items:
                    print("\n🔍 첫 번째 아이템 상세 분석:")
                    print("-" * 30)
                    analyze_structure(items[0])
                    
                    # 첫 번째 아이템의 모든 자식 태그 수집
                    if len(items) > 0:
                        for child in items[0]:
                            all_fields.add(child.tag)
                else:
                    print("⚠️ 아이템을 찾을 수 없습니다. 전체 구조:")
                    analyze_structure(root)
                
            else:
                print(f"❌ API 호출 실패: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 오류: {e}")
        
        print("\n" + "="*60)
    
    # 모든 필드 요약
    print(f"\n📋 발견된 모든 XML 태그/필드: {len(all_fields)}개")
    print("-" * 60)
    
    sorted_fields = sorted(all_fields)
    for i, field in enumerate(sorted_fields, 1):
        print(f"{i:2d}. {field}")
    
    # JSON으로도 저장
    field_info = {
        'total_fields': len(all_fields),
        'fields': sorted_fields,
        'analyzed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'api_endpoint': base_url
    }
    
    with open('kstartup_api_fields.json', 'w', encoding='utf-8') as f:
        json.dump(field_info, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 분석 결과가 'kstartup_api_fields.json' 파일에 저장되었습니다.")
    
    return sorted_fields

if __name__ == "__main__":
    print(f"⏰ 분석 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    fields = analyze_complete_kstartup_api()
    print(f"\n🎉 분석 완료! 총 {len(fields)}개 필드 발견")
