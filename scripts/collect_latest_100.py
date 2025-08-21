import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, date
import time
import os
import sys
from dotenv import load_dotenv

# Windows 콘솔 유니코드 지원
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# 환경변수 로드
load_dotenv()

def parse_date_string(date_str):
    """다양한 날짜 형식을 파싱"""
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip()
    
    # 일반적인 형식들 시도
    formats = [
        '%Y-%m-%d',
        '%Y%m%d', 
        '%Y.%m.%d',
        '%Y/%m/%d',
        '%Y년 %m월 %d일',
        '%Y-%m-%d %H:%M:%S'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    
    print(f"⚠️ 날짜 파싱 실패: {date_str}")
    return None

def parse_kstartup_item(item):
    """K-Startup XML 아이템을 딕셔너리로 변환"""
    data = {}
    
    for child in item:
        if child.text and child.text.strip():
            value = child.text.strip()
            
            # 날짜 필드들은 파싱
            if child.tag.lower().endswith('ymd'):
                parsed_date = parse_date_string(value)
                data[child.tag.lower()] = parsed_date
            else:
                data[child.tag.lower()] = value
    
    return data

def collect_latest_100_valid():
    """등록일 기준 최신 100개 중 유효한 공고만 수집"""
    print("🚀 K-Startup 최신 100개 유효 공고 수집")
    print("=" * 60)
    
    base_url = "https://www.k-startup.go.kr/api/apisvc/xml/GetPblancListSvc"
    today = date.today()
    
    print(f"📅 오늘 날짜: {today}")
    print(f"📋 수집 조건: 등록일 최신순 100개 중 마감일이 지나지 않은 것")
    print()
    
    # API 파라미터 - 등록일 기준 최신순
    params = {
        'perPage': '100',           # 100개만
        'page': '1',                # 첫 페이지만
        'sortColumn': 'REG_YMD',    # 등록일 기준
        'sortDirection': 'DESC'     # 내림차순 (최신순)
    }
    
    print(f"📡 API 호출 중...")
    print(f"URL: {base_url}")
    print(f"파라미터: {params}")
    print()
    
    try:
        # API 호출
        response = requests.get(base_url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API 호출 실패: {response.status_code}")
            return []
        
        print(f"✅ API 호출 성공! 응답 크기: {len(response.content)} bytes")
        
        # XML 파싱
        root = ET.fromstring(response.text)
        print(f"📄 XML 루트: {root.tag}")
        
        # 아이템 찾기
        items = []
        for elem in root.iter():
            if elem.tag.lower().endswith('item'):
                items.append(elem)
        
        print(f"📋 발견된 총 아이템: {len(items)}개")
        print()
        
        if not items:
            print("❌ 아이템을 찾을 수 없습니다.")
            return []
        
        # 각 아이템 처리
        valid_items = []
        expired_items = []
        no_date_items = []
        
        print("🔍 아이템별 상세 분석:")
        print("-" * 60)
        
        for i, item in enumerate(items, 1):
            data = parse_kstartup_item(item)
            
            if not data:
                continue
            
            # 기본 정보 추출
            title = data.get('pblancnm', '제목없음')
            reg_date = data.get('regymd')
            end_date = data.get('reqstendymd')
            org = data.get('organnm', '기관정보없음')
            
            print(f"📄 {i:2d}. {title[:40]}{'...' if len(title) > 40 else ''}")
            print(f"     등록일: {reg_date}")
            print(f"     마감일: {end_date}")
            print(f"     기관: {org}")
            
            # 유효성 검사
            if end_date and isinstance(end_date, date):
                if end_date >= today:
                    valid_items.append(data)
                    status = "✅ 유효"
                else:
                    expired_items.append(data)
                    status = "❌ 만료"
            else:
                no_date_items.append(data)
                status = "⚠️ 마감일 정보 없음"
            
            print(f"     상태: {status}")
            print()
        
        print("=" * 60)
        print(f"📊 분석 결과:")
        print(f"  ✅ 유효한 공고: {len(valid_items)}개")
        print(f"  ❌ 만료된 공고: {len(expired_items)}개") 
        print(f"  ⚠️ 마감일 정보 없음: {len(no_date_items)}개")
        print(f"  📋 총 처리: {len(items)}개")
        
        # 유효한 공고 + 마감일 정보 없는 공고 (일단 포함)
        final_items = valid_items + no_date_items
        
        print()
        print(f"🎯 최종 수집 대상: {len(final_items)}개")
        
        # 결과를 JSON 파일로 저장
        result = {
            'collection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_requested': 100,
            'total_found': len(items),
            'valid_count': len(valid_items),
            'expired_count': len(expired_items),
            'no_date_count': len(no_date_items),
            'final_count': len(final_items),
            'data': final_items
        }
        
        filename = f"kstartup_latest_100_valid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"💾 결과가 '{filename}' 파일에 저장되었습니다.")
        
        # 샘플 데이터 출력
        if final_items:
            print()
            print("📋 수집된 유효 공고 샘플 (처음 3개):")
            print("-" * 60)
            
            for i, item in enumerate(final_items[:3], 1):
                print(f"🔸 {i}번째 공고:")
                print(f"   제목: {item.get('pblancnm', 'N/A')}")
                print(f"   등록일: {item.get('regymd', 'N/A')}")
                print(f"   마감일: {item.get('reqstendymd', 'N/A')}")
                print(f"   기관: {item.get('organnm', 'N/A')}")
                print(f"   URL: {item.get('pblancurl', 'N/A')}")
                print()
        
        return final_items
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    items = collect_latest_100_valid()
    
    print()
    print("=" * 60)
    if items:
        print(f"🎉 수집 완료! 총 {len(items)}개의 유효한 공고를 가져왔습니다.")
        print("📁 JSON 파일을 확인하여 상세 데이터를 볼 수 있습니다.")
    else:
        print("❌ 수집 실패 또는 유효한 데이터가 없습니다.")
    
    print()
    print(f"⏰ 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
