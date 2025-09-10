#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 파이프라인 매니저 테스트
- 하나의 공고로 테스트
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from pathlib import Path

# 환경 변수 설정
os.environ['COLLECTION_MODE'] = 'TEST'

# 매니저 임포트
from scripts.integrated_pipeline_manager import PipelineManager

def test_single_announcement():
    """단일 공고 테스트"""
    
    # 테스트용 공고 데이터
    test_announcement = {
        'source': 'kstartup',
        'id': 'KS_TEST_001',
        'title': '테스트 공고',
        'urls': [
            # 실제 테스트할 URL 추가 필요
        ]
    }
    
    print("="*70)
    print("통합 파이프라인 테스트")
    print("="*70)
    
    # 매니저 생성
    manager = PipelineManager()
    
    # 단일 공고 처리
    manager.process_announcement(test_announcement)
    
    print("\n테스트 완료!")
    print(f"결과 확인: pipeline_results/KS_TEST_001_*.json")

def test_with_real_data():
    """실제 데이터로 테스트 (DB에서 가져오기)"""
    from supabase import create_client
    from dotenv import load_dotenv
    
    load_dotenv()
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    # 테스트할 공고 가져오기 (attachment_urls는 있지만 files가 없는 것)
    response = supabase.table('kstartup_announcements').select(
        'id, pbln_pblancnm, attachment_urls'
    ).not_.is_('attachment_urls', 'null').is_('files', 'null').limit(1).execute()
    
    if response.data and len(response.data) > 0:
        item = response.data[0]
        
        test_announcement = {
            'source': 'kstartup',
            'id': item['id'],
            'title': item['pbln_pblancnm'],
            'urls': item['attachment_urls']
        }
        
        print(f"테스트 공고: {test_announcement['title']}")
        print(f"ID: {test_announcement['id']}")
        print(f"URL 개수: {len(test_announcement['urls'])}")
        
        # 매니저 생성 및 처리
        manager = PipelineManager()
        manager.process_announcement(test_announcement)
        
        print(f"\n결과 파일: pipeline_results/{item['id']}_*.json")
    else:
        print("테스트할 공고를 찾을 수 없습니다.")
        print("attachment_urls는 있지만 files가 없는 공고가 없습니다.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--real':
        print("실제 데이터로 테스트")
        test_with_real_data()
    else:
        print("테스트 데이터로 실행")
        print("실제 데이터로 테스트하려면: python test_pipeline_manager.py --real")
        test_single_announcement()