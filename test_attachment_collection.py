#!/usr/bin/env python3
"""
첨부파일 URL 수집 테스트 스크립트
K-Startup과 BizInfo 모두 테스트
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
from datetime import datetime

# 환경변수 설정
os.environ['SUPABASE_URL'] = 'https://csuziaogycciwgxxmahm.supabase.co'
os.environ['SUPABASE_SERVICE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzdXppYW9neWNjaXdneHhtYWhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzYxNTc4MCwiZXhwIjoyMDY5MTkxNzgwfQ.HnhM7zSLzi7lHVPd2IVQKIACDq_YA05mBMgZbSN1c9Q'
os.environ['PROCESSING_LIMIT'] = '5'  # 테스트용으로 5개만

def test_kstartup_attachment():
    """K-Startup 첨부파일 수집 테스트"""
    print("\n" + "="*60)
    print("K-Startup 첨부파일 URL 수집 테스트")
    print("="*60)
    
    try:
        # K-Startup 첨부파일 수집 스크립트 실행
        from scripts.kstartup_attachment_enhanced_fixed import main as kstartup_main
        print("\n📎 K-Startup 첨부파일 수집 시작...")
        kstartup_main()
        print("✅ K-Startup 첨부파일 수집 완료!")
        return True
    except Exception as e:
        print(f"❌ K-Startup 첨부파일 수집 실패: {e}")
        return False

def test_bizinfo_attachment():
    """BizInfo 첨부파일 수집 테스트"""
    print("\n" + "="*60)
    print("BizInfo 첨부파일 URL 수집 테스트")
    print("="*60)
    
    try:
        # BizInfo 첨부파일 수집 스크립트 실행
        from scripts.bizinfo_attachment_enhanced_fixed import main as bizinfo_main
        print("\n📎 BizInfo 첨부파일 수집 시작...")
        bizinfo_main()
        print("✅ BizInfo 첨부파일 수집 완료!")
        return True
    except Exception as e:
        print(f"❌ BizInfo 첨부파일 수집 실패: {e}")
        return False

def verify_results():
    """수집 결과 검증"""
    print("\n" + "="*60)
    print("수집 결과 검증")
    print("="*60)
    
    try:
        from supabase import create_client
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_KEY')
        supabase = create_client(url, key)
        
        # K-Startup 결과 확인
        kstartup_result = supabase.table('kstartup_complete')\
            .select('announcement_id, biz_pbanc_nm, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .limit(5)\
            .execute()
        
        print(f"\n📊 K-Startup 첨부파일 수집 결과:")
        print(f"  - 첨부파일이 있는 공고: {len(kstartup_result.data)}개")
        
        for item in kstartup_result.data[:3]:
            urls = item.get('attachment_urls', [])
            print(f"  - {item['announcement_id']}: {len(urls)}개 URL")
            if urls and len(urls) > 0:
                print(f"    첫 번째 URL: {urls[0].get('url', '')[:60]}...")
        
        # BizInfo 결과 확인
        bizinfo_result = supabase.table('bizinfo_complete')\
            .select('pblanc_id, pblanc_nm, attachment_urls')\
            .not_.is_('attachment_urls', 'null')\
            .limit(5)\
            .execute()
        
        print(f"\n📊 BizInfo 첨부파일 수집 결과:")
        print(f"  - 첨부파일이 있는 공고: {len(bizinfo_result.data)}개")
        
        for item in bizinfo_result.data[:3]:
            urls = item.get('attachment_urls', [])
            print(f"  - {item['pblanc_id']}: {len(urls)}개 URL")
            if urls and len(urls) > 0:
                print(f"    첫 번째 URL: {urls[0].get('url', '')[:60]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ 결과 검증 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print(f"\n🚀 첨부파일 URL 수집 테스트 시작")
    print(f"시작 시간: {datetime.now()}")
    
    results = []
    
    # K-Startup 테스트
    results.append(("K-Startup", test_kstartup_attachment()))
    time.sleep(2)
    
    # BizInfo 테스트
    results.append(("BizInfo", test_bizinfo_attachment()))
    time.sleep(2)
    
    # 결과 검증
    results.append(("검증", verify_results()))
    
    # 최종 결과
    print("\n" + "="*60)
    print("📊 최종 테스트 결과")
    print("="*60)
    
    for name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        print(f"{name}: {status}")
    
    all_success = all(r[1] for r in results)
    if all_success:
        print("\n🎉 모든 테스트 성공!")
    else:
        print("\n⚠️ 일부 테스트 실패 - 확인 필요")
    
    print(f"\n종료 시간: {datetime.now()}")

if __name__ == "__main__":
    main()
