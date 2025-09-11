#!/usr/bin/env python3
"""
첨부파일 모니터링 시스템
- 5분마다 서버 체크
- 새로운 첨부파일 URL 감지 시 파이프라인 실행
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
import json
from datetime import datetime, timedelta
import pytz
from supabase import create_client
from dotenv import load_dotenv
import subprocess
from pathlib import Path

load_dotenv()

# Supabase 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

class AttachmentMonitor:
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.state_file = Path("monitor_state.json")
        self.pipeline_script = Path("scripts/integrated_pipeline_manager.py")
        self.check_interval = 300  # 5분 (300초)
        self.kst = pytz.timezone('Asia/Seoul')
        
        # 상태 파일 로드
        self.load_state()
        
    def load_state(self):
        """이전 실행 상태 로드"""
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                self.state = json.load(f)
        else:
            self.state = {
                'last_check': None,
                'processed_ids': {
                    'kstartup': [],
                    'bizinfo': []
                }
            }
    
    def save_state(self):
        """현재 상태 저장"""
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
    
    def check_new_attachments(self):
        """새로운 첨부파일 체크"""
        new_items = {
            'kstartup': [],
            'bizinfo': []
        }
        
        now = datetime.now(self.kst)
        
        # K-Startup 체크
        try:
            # attachment_urls가 있고 처리 상태가 pending인 항목
            response = self.supabase.table('kstartup_complete')\
                .select('announcement_id, biz_pbanc_nm, attachment_urls, attachment_processing_status')\
                .not_.is_('attachment_urls', 'null')\
                .or_('attachment_processing_status.is.null,attachment_processing_status.eq.pending')\
                .execute()
            
            for item in response.data:
                announcement_id = item['announcement_id']
                if announcement_id not in self.state['processed_ids']['kstartup']:
                    # attachment_urls 확인
                    urls = item.get('attachment_urls', [])
                    if isinstance(urls, str):
                        try:
                            urls = json.loads(urls)
                        except:
                            continue
                    
                    if urls and len(urls) > 0:
                        new_items['kstartup'].append({
                            'id': announcement_id,
                            'title': item.get('biz_pbanc_nm', 'N/A'),
                            'url_count': len(urls)
                        })
        except Exception as e:
            print(f"K-Startup 체크 오류: {e}")
        
        # BizInfo 체크
        try:
            response = self.supabase.table('bizinfo_complete')\
                .select('pblanc_id, pblanc_nm, attachment_urls, attachment_processing_status')\
                .not_.is_('attachment_urls', 'null')\
                .or_('attachment_processing_status.is.null,attachment_processing_status.eq.pending')\
                .execute()
            
            for item in response.data:
                pblanc_id = item['pblanc_id']
                if pblanc_id not in self.state['processed_ids']['bizinfo']:
                    # attachment_urls 확인
                    urls = item.get('attachment_urls', [])
                    if isinstance(urls, str):
                        try:
                            urls = json.loads(urls)
                        except:
                            continue
                    
                    if urls and len(urls) > 0:
                        new_items['bizinfo'].append({
                            'id': pblanc_id,
                            'title': item.get('pblanc_nm', 'N/A'),
                            'url_count': len(urls)
                        })
        except Exception as e:
            print(f"BizInfo 체크 오류: {e}")
        
        return new_items
    
    def run_pipeline(self, source, announcement_id):
        """파이프라인 실행"""
        print(f"\n🚀 파이프라인 실행: {source} - {announcement_id}")
        
        try:
            # 파이프라인 매니저 실행
            cmd = [
                'python', 
                str(self.pipeline_script),
                '--source', source,
                '--id', announcement_id
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                print(f"✅ 파이프라인 완료: {announcement_id}")
                # 처리 완료 ID 저장
                self.state['processed_ids'][source].append(announcement_id)
                self.save_state()
                return True
            else:
                print(f"❌ 파이프라인 실패: {announcement_id}")
                print(f"에러: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"파이프라인 실행 오류: {e}")
            return False
    
    def monitor_loop(self):
        """메인 모니터링 루프"""
        print("="*70)
        print("📡 첨부파일 모니터링 시작")
        print(f"⏰ 체크 간격: {self.check_interval}초 (5분)")
        print("="*70)
        
        while True:
            try:
                now = datetime.now(self.kst)
                print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 체크 시작...")
                
                # 새로운 첨부파일 체크
                new_items = self.check_new_attachments()
                
                # 통계 출력
                total_new = len(new_items['kstartup']) + len(new_items['bizinfo'])
                
                if total_new > 0:
                    print(f"\n📊 발견된 새 항목:")
                    print(f"  - K-Startup: {len(new_items['kstartup'])}건")
                    print(f"  - BizInfo: {len(new_items['bizinfo'])}건")
                    
                    # K-Startup 처리
                    for item in new_items['kstartup']:
                        print(f"\n[K-Startup] {item['id']}: {item['title'][:50]}...")
                        print(f"  첨부파일: {item['url_count']}개")
                        self.run_pipeline('kstartup', item['id'])
                        time.sleep(2)  # 서버 부하 방지
                    
                    # BizInfo 처리
                    for item in new_items['bizinfo']:
                        print(f"\n[BizInfo] {item['id']}: {item['title'][:50]}...")
                        print(f"  첨부파일: {item['url_count']}개")
                        self.run_pipeline('bizinfo', item['id'])
                        time.sleep(2)  # 서버 부하 방지
                else:
                    print("새로운 첨부파일 없음")
                
                # 상태 업데이트
                self.state['last_check'] = now.isoformat()
                self.save_state()
                
                # 다음 체크까지 대기
                print(f"\n💤 다음 체크: {self.check_interval}초 후...")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n\n🛑 모니터링 중지")
                break
            except Exception as e:
                print(f"\n❌ 모니터링 오류: {e}")
                print(f"30초 후 재시도...")
                time.sleep(30)

def main():
    monitor = AttachmentMonitor()
    monitor.monitor_loop()

if __name__ == "__main__":
    main()