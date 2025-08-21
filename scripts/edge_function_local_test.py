#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Edge Function 로컬 테스트 (Python 버전)
K-Startup API 호출 및 XML 파싱 테스트
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import re

def fetch_kstartup_api():
    """K-Startup API 호출 (Edge Function에서 사용하는 URL)"""
    print("🚀 Edge Function API 테스트 시작")
    print("="*60)
    
    # GitHub Actions에서 성공한 API URL 사용
    api_url = 'http://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01'
    
    params = {
        'ServiceKey': 'rHwfm51FIrtIJjqRL2fJFJFvNsVEng7v7Ud0T44EKQpgKoMEJmN06LZ+KQ2wbTfW29XZSm8OzMuNCUQi+MTlsQ==',
        'pageNo': '1',
        'numOfRows': '100'
    }
    
    print(f"📡 API 호출: {api_url}")
    print(f"📋 파라미터: {params}")
    
    try:
        headers = {
            'User-Agent': 'Edge-Function-Test/1.0',
            'Accept': 'application/xml, text/xml, */*'
        }
        
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        
        print(f"📊 HTTP 상태: {response.status_code}")
        print(f"📄 응답 크기: {len(response.text)} bytes")
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"❌ API 오류: {response.status_code}")
            print(f"📄 응답 내용: {response.text[:500]}...")
            return None
            
    except Exception as e:
        print(f"❌ 요청 오류: {e}")
        return None

def parse_xml_content(xml_text):
    """XML 내용 파싱 및 분석"""
    print(f"\n📄 XML 파싱 시작...")
    
    try:
        # XML 구조 분석
        print("🔍 XML 구조 분석:")
        
        # Root 요소 찾기
        if '<rss' in xml_text:
            print("  - RSS 형식 감지")
        elif '<xml' in xml_text or '<?xml' in xml_text:
            print("  - XML 형식 감지")
        else:
            print("  - HTML 또는 기타 형식")
            
        # Item 요소 찾기
        item_matches = re.findall(r'<item[^>]*>(.*?)</item>', xml_text, re.DOTALL | re.IGNORECASE)
        print(f"  - Item 요소 수: {len(item_matches)}")
        
        if len(item_matches) == 0:
            # 다른 패턴 확인
            col_matches = re.findall(r'<col[^>]*>(.*?)</col>', xml_text, re.DOTALL | re.IGNORECASE)
            print(f"  - Col 요소 수: {len(col_matches)}")
            
            data_matches = re.findall(r'<data[^>]*>(.*?)</data>', xml_text, re.DOTALL | re.IGNORECASE)
            print(f"  - Data 요소 수: {len(data_matches)}")
        
        # XML을 ElementTree로 파싱 시도
        try:
            root = ET.fromstring(xml_text)
            print(f"✅ XML 파싱 성공: Root = {root.tag}")
            
            # 모든 하위 요소 탐색
            all_elements = list(root.iter())
            print(f"📊 총 요소 수: {len(all_elements)}")
            
            # 유니크한 태그명들 출력
            unique_tags = set(elem.tag for elem in all_elements)
            print(f"🏷️ 발견된 태그들: {list(unique_tags)[:10]}")
            
            # item 또는 유사한 요소 찾기
            items = []
            
            # 다양한 패턴으로 item 찾기
            for pattern in ['item', 'data/item', './/item', 'channel/item']:
                found_items = root.findall(pattern)
                if found_items:
                    print(f"✅ '{pattern}' 패턴으로 {len(found_items)}개 아이템 발견")
                    items = found_items
                    break
            
            if not items:
                # col 패턴 확인
                cols = root.findall('.//col')
                if cols:
                    print(f"📋 Col 요소 {len(cols)}개 발견")
                    
                    # col을 item으로 그룹화
                    current_item = {}
                    items_data = []
                    
                    for col in cols:
                        name = col.get('name', '')
                        value = col.text or ''
                        
                        if name and value:
                            current_item[name] = value
                            
                            # 새로운 아이템의 시작점 감지 (예: pbanc_sn)
                            if name == 'pbanc_sn' and len(current_item) > 1:
                                items_data.append(current_item.copy())
                                current_item = {name: value}
                    
                    if current_item:
                        items_data.append(current_item)
                    
                    print(f"📦 그룹화된 아이템: {len(items_data)}개")
                    
                    # 샘플 아이템 출력
                    if items_data:
                        print("\n📋 샘플 데이터:")
                        sample = items_data[0]
                        for key, value in list(sample.items())[:5]:
                            print(f"  - {key}: {value[:50]}...")
                    
                    return items_data
            else:
                # 일반 item 요소 처리 - col 구조 확인
                items_data = []
                for item in items[:5]:  # 처음 5개만
                    item_data = {}
                    
                    # col 요소들 확인
                    cols = item.findall('col')
                    if cols:
                        print(f"🔍 Item에서 {len(cols)}개 col 발견")
                        for col in cols:
                            name = col.get('name', '')
                            value = col.text or ''
                            if name and value:
                                item_data[name] = value
                                
                        print(f"📋 Col 데이터: {list(item_data.keys())[:10]}")
                    else:
                        # 일반 자식 요소들
                        for child in item:
                            if child.text and child.text.strip():
                                item_data[child.tag] = child.text.strip()
                    
                    if item_data:
                        items_data.append(item_data)
                
                print(f"📦 처리된 아이템: {len(items_data)}개")
                
                if items_data:
                    print("\n📋 샘플 데이터:")
                    sample = items_data[0]
                    for key, value in list(sample.items())[:10]:
                        print(f"  - {key}: {str(value)[:50]}...")
                
                return items_data
                
        except ET.ParseError as e:
            print(f"❌ XML 파싱 실패: {e}")
            print("📄 XML 시작 부분:")
            print(xml_text[:500])
            return None
            
    except Exception as e:
        print(f"❌ 파싱 중 오류: {e}")
        return None

def test_data_conversion(items_data):
    """데이터 변환 테스트"""
    if not items_data:
        return
        
    print(f"\n🔧 데이터 변환 테스트...")
    
    batch_id = f"edge_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    converted_records = []
    
    for item in items_data[:3]:  # 처음 3개만 테스트
        # Edge Function 형식으로 변환 (실제 필드명 사용)
        record = {
            'collection_batch_id': batch_id,
            'source': 'k-startup-edge',
            'data_status': 'raw',
            
            # 공고 기본 정보 (실제 API 필드명)
            'pblanc_nm': item.get('biz_pbanc_nm', 'Unknown'),
            'pblanc_id': item.get('pbanc_sn', 'Unknown'),
            'pblanc_url': item.get('detl_pg_url', ''),
            
            # 기관 정보
            'organ_nm': item.get('pbanc_ntrp_nm', ''),
            'exctv_organ_nm': item.get('biz_prch_dprt_nm', ''),
            'sprv_inst': item.get('sprv_inst', ''),
            
            # 지원 대상 및 내용
            'aply_trgt_ctnt': item.get('aply_trgt_ctnt', ''),
            'bsns_sumry': item.get('pbanc_ctnt', ''),
            'supt_biz_clsfc': item.get('supt_biz_clsfc', ''),
            
            # 일정
            'pbanc_rcpt_bgng_dt': item.get('pbanc_rcpt_bgng_dt', ''),
            'pbanc_rcpt_end_dt': item.get('pbanc_rcpt_end_dt', ''),
            
            # 원본 데이터
            'raw_xml_data': item
        }
        
        converted_records.append(record)
        
        print(f"✅ 변환 완료: {record['pblanc_nm']}")
    
    print(f"\n📊 변환 결과:")
    print(f"  - 총 레코드 수: {len(converted_records)}")
    print(f"  - 배치 ID: {batch_id}")
    
    # 샘플 레코드 출력
    if converted_records:
        print(f"\n📋 샘플 레코드:")
        sample = converted_records[0]
        for key, value in sample.items():
            if key != 'raw_xml_data':
                print(f"  - {key}: {str(value)[:60]}...")

def main():
    """메인 실행 함수"""
    
    # 1. API 호출
    xml_content = fetch_kstartup_api()
    
    if not xml_content:
        print("❌ API 호출 실패")
        return
    
    # 2. XML 파싱
    items_data = parse_xml_content(xml_content)
    
    if not items_data:
        print("❌ 데이터 파싱 실패")
        return
    
    # 3. 데이터 변환 테스트
    test_data_conversion(items_data)
    
    print("\n" + "="*60)
    print("🎉 Edge Function 로컬 테스트 완료!")
    print("="*60)

if __name__ == "__main__":
    main()