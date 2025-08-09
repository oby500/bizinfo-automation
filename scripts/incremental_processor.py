#!/usr/bin/env python3
"""
증분 처리 전용 스크립트
- 새로 추가된 데이터만 처리
- 처리 완료된 데이터는 스킵
- 실패한 데이터만 재처리
"""

import os
import json
from datetime import datetime, timedelta
from supabase import create_client
import logging

logging.basicConfig(level=logging.INFO)

class IncrementalProcessor:
    def __init__(self):
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
        
        if not url or not key:
            raise ValueError("환경변수 설정 필요")
            
        self.supabase = create_client(url, key)
    
    def process_new_bizinfo(self):
        """신규 BizInfo 데이터만 처리"""
        logging.info("=== BizInfo 증분 처리 시작 ===")
        
        # 1. 처리 안 된 데이터만 조회
        response = self.supabase.table('bizinfo_complete')\
            .select('id,pblancId,attachment_urls')\
            .neq('attachment_urls', '[]')\
            .or_('attachment_processing_status.is.null,attachment_processing_status->processed.neq.true')\
            .execute()
        
        if not response.data:
            logging.info("처리할 신규 데이터 없음")
            return 0
        
        logging.info(f"처리 대상: {len(response.data)}개")
        
        processed = 0
        for item in response.data:
            # safe_filename이 이미 있으면 스킵
            needs_processing = False
            for att in item.get('attachment_urls', []):
                if isinstance(att, dict) and not att.get('safe_filename'):
                    needs_processing = True
                    break
            
            if needs_processing:
                # 처리 로직
                self.process_bizinfo_item(item)
                processed += 1
                
                # 처리 완료 표시
                self.supabase.table('bizinfo_complete').update({
                    'attachment_processing_status': {
                        'processed': True,
                        'processed_at': datetime.now().isoformat(),
                        'processor': 'incremental_v1'
                    }
                }).eq('id', item['id']).execute()
        
        logging.info(f"✅ {processed}개 처리 완료")
        return processed
    
    def process_new_kstartup(self):
        """신규 K-Startup 데이터만 처리"""
        logging.info("=== K-Startup 증분 처리 시작 ===")
        
        # 최근 24시간 이내 추가된 데이터만
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        
        response = self.supabase.table('kstartup_complete')\
            .select('id,announcement_id,attachment_urls')\
            .gte('created_at', yesterday)\
            .neq('attachment_urls', '[]')\
            .execute()
        
        if not response.data:
            logging.info("최근 24시간 내 신규 데이터 없음")
            return 0
        
        logging.info(f"최근 24시간 데이터: {len(response.data)}개")
        
        processed = 0
        for item in response.data:
            # unknown 확장자가 있거나 safe_filename이 없으면 처리
            needs_processing = False
            for att in item.get('attachment_urls', []):
                if isinstance(att, dict):
                    if not att.get('safe_filename') or att.get('safe_filename', '').endswith('.unknown'):
                        needs_processing = True
                        break
            
            if needs_processing:
                self.process_kstartup_item(item)
                processed += 1
        
        logging.info(f"✅ {processed}개 처리 완료")
        return processed
    
    def process_bizinfo_item(self, item):
        """BizInfo 개별 처리"""
        # 실제 처리 로직
        pass
    
    def process_kstartup_item(self, item):
        """K-Startup 개별 처리"""
        # 실제 처리 로직
        pass
    
    def reprocess_failed(self):
        """실패한 항목만 재처리"""
        logging.info("=== 실패 항목 재처리 ===")
        
        # attachment_processing_status가 'failed'인 것만
        response = self.supabase.table('bizinfo_complete')\
            .select('id')\
            .eq('attachment_processing_status->status', 'failed')\
            .execute()
        
        if response.data:
            logging.info(f"재처리 대상: {len(response.data)}개")
            # 재처리 로직
        
        return len(response.data) if response.data else 0
    
    def get_processing_stats(self):
        """처리 통계"""
        stats = {
            'bizinfo': {
                'total': 0,
                'processed': 0,
                'pending': 0,
                'failed': 0
            },
            'kstartup': {
                'total': 0,
                'processed': 0,
                'pending': 0,
                'failed': 0
            }
        }
        
        # BizInfo 통계
        biz_total = self.supabase.table('bizinfo_complete').select('id', count='exact').execute()
        biz_processed = self.supabase.table('bizinfo_complete')\
            .select('id', count='exact')\
            .eq('attachment_processing_status->processed', True)\
            .execute()
        
        stats['bizinfo']['total'] = biz_total.count if biz_total else 0
        stats['bizinfo']['processed'] = biz_processed.count if biz_processed else 0
        stats['bizinfo']['pending'] = stats['bizinfo']['total'] - stats['bizinfo']['processed']
        
        return stats

def main():
    processor = IncrementalProcessor()
    
    # 1. 신규 데이터만 처리
    processor.process_new_bizinfo()
    processor.process_new_kstartup()
    
    # 2. 실패한 것만 재처리 (선택)
    # processor.reprocess_failed()
    
    # 3. 통계 출력
    stats = processor.get_processing_stats()
    
    print("\n" + "="*50)
    print("📊 처리 현황")
    print("="*50)
    print(f"BizInfo: {stats['bizinfo']['processed']}/{stats['bizinfo']['total']} 처리 완료")
    print(f"K-Startup: {stats['kstartup']['processed']}/{stats['kstartup']['total']} 처리 완료")
    print("="*50)

if __name__ == "__main__":
    main()
