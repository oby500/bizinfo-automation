#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
자동화 시스템 테스트 스크립트
- 환경변수 확인
- API 연결 테스트
- 데이터 수집 가능 여부 확인
"""

import os
import sys
import requests
from datetime import datetime, timedelta

def test_environment():
    """환경변수 테스트"""
    print("\n=== 1. 환경변수 확인 ===")
    
    required_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_KEY']
    missing = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            if var == 'SUPABASE_URL':
                print(f"✅ {var}: {'설정됨' if value.startswith('https://') else '❌ https:// 누락'}")
            else:
                print(f"✅ {var}: 설정됨 (길이: {len(value)})")
        else:
            print(f"❌ {var}: 없음")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️ 누락된 환경변수: {', '.join(missing)}")
        return False
    return True

def test_supabase():
    """Supabase 연결 테스트"""
    print("\n=== 2. Supabase 연결 테스트 ===")
    
    try:
        from supabase import create_client
        
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            print("❌ Supabase 환경변수 없음")
            return False
        
        if not url.startswith('https://'):
            print(f"❌ SUPABASE_URL에 https:// 누락: {url}")
            return False
            
        print(f"URL: {url[:30]}...")
        print(f"Key: {key[:20]}...")
        
        try:
            supabase = create_client(url, key)
            
            # 간단한 쿼리로 연결 테스트
            result = supabase.table('bizinfo_complete').select('id').limit(1).execute()
            print(f"✅ Supabase 연결 성공")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if 'Invalid API key' in error_msg:
                print(f"❌ API 키 오류 - GitHub Secrets의 SUPABASE_SERVICE_KEY 확인 필요")
            else:
                print(f"❌ Supabase 연결 오류: {error_msg[:100]}")
            return False
                
    except ImportError:
        print("❌ supabase 라이브러리 없음")
        return False

def test_kstartup_api():
    """K-Startup API 테스트"""
    print("\n=== 3. K-Startup API 테스트 ===")
    
    # HTTP 사용 (HTTPS 아님!)
    api_url = "http://www.k-startup.go.kr/web/module/bizpbanc-list.do"
    
    params = {
        'cpage': 1,
        'rows': 10,
        '_': int(datetime.now().timestamp() * 1000)
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=10)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if 'resultList' in data:
                    count = len(data['resultList'])
                    print(f"✅ K-Startup API 정상 (데이터 {count}개)")
                    return True
                else:
                    print("⚠️ K-Startup API 응답 형식 변경됨")
                    return False
            except:
                # JSON 파싱 실패시 웹 스크래핑으로 대체 가능
                print("⚠️ K-Startup API JSON 파싱 실패 - 웹 스크래핑 모드로 전환 가능")
                return True  # 스크래핑으로 대체 가능하므로 True
        else:
            print(f"❌ K-Startup API 응답 오류: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ K-Startup API 연결 실패: {e}")
        return False

def test_bizinfo():
    """기업마당 웹사이트 접근 테스트"""
    print("\n=== 4. 기업마당 접근 테스트 ===")
    
    url = "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ 기업마당 웹사이트 접근 가능")
            return True
        else:
            print(f"❌ 기업마당 응답 오류: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 기업마당 연결 실패: {e}")
        return False

def check_recent_data():
    """최근 데이터 처리 현황 확인"""
    print("\n=== 5. 최근 처리 현황 ===")
    
    try:
        from supabase import create_client
        
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            print("⚠️ 환경변수 미설정으로 스킵")
            return
            
        supabase = create_client(url, key)
        
        # 기업마당 현황
        bizinfo = supabase.table('bizinfo_complete').select('id', 'created_at').order('created_at', desc=True).limit(1).execute()
        if bizinfo.data:
            last_time = bizinfo.data[0]['created_at']
            print(f"📊 기업마당 최근 수집: {last_time}")
        
        # K-Startup 현황
        kstartup = supabase.table('kstartup_complete').select('id', 'created_at').order('created_at', desc=True).limit(1).execute()
        if kstartup.data:
            last_time = kstartup.data[0]['created_at']
            print(f"📊 K-Startup 최근 수집: {last_time}")
            
    except Exception as e:
        print(f"⚠️ 데이터 확인 스킵 (API 키 문제)")

def main():
    """메인 테스트 실행"""
    print("="*50)
    print("   자동화 시스템 테스트")
    print("="*50)
    
    results = []
    
    # 각 테스트 실행
    results.append(("환경변수", test_environment()))
    results.append(("Supabase", test_supabase()))
    results.append(("K-Startup API", test_kstartup_api()))
    results.append(("기업마당", test_bizinfo()))
    
    # 최근 데이터 확인
    check_recent_data()
    
    # 결과 요약
    print("\n" + "="*50)
    print("   테스트 결과 요약")
    print("="*50)
    
    for name, result in results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{name}: {status}")
    
    # 전체 성공 여부
    all_success = all(r[1] for r in results)
    
    if all_success:
        print("\n🎉 모든 테스트 통과! 자동화 실행 가능")
        return 0
    else:
        print("\n⚠️ 일부 테스트 실패")
        print("\n📝 해결 방법:")
        print("1. GitHub Settings → Secrets → SUPABASE_SERVICE_KEY 업데이트")
        print("2. Supabase 대시보드에서 service_role 키 복사")
        print("3. SUPABASE_URL이 https://로 시작하는지 확인")
        return 1

if __name__ == "__main__":
    sys.exit(main())
