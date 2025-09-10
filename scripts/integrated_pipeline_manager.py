#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 파이프라인 매니저
- Supabase에서 새 URL 감지
- Step 1~5 자동 실행
- 각 단계 완료 확인 후 다음 진행
"""
import sys
import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import traceback

# 환경 설정
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from dotenv import load_dotenv

# Step 모듈 임포트
from kstartup_attachment_enhanced_fixed import main as step1_kstartup
from bizinfo_attachment_enhanced_fixed import main as step1_bizinfo
from step2_convert_hwp_v3 import process_hwp_files as step2_convert
from step3_extract_pdf_v7 import process_pdfs as step3_extract
from step4_summarize_v2 import process_texts as step4_summarize
# Step 5는 나중에 추가

# 환경 변수 로드
load_dotenv()
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline_manager.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 파이프라인 결과 저장 경로
PIPELINE_RESULTS_DIR = Path('pipeline_results')
PIPELINE_RESULTS_DIR.mkdir(exist_ok=True)

class PipelineManager:
    """통합 파이프라인 매니저"""
    
    def __init__(self):
        self.check_interval = 300  # 5분 (초 단위)
        self.last_check_time = None
        self.running = False
        
    def get_new_urls(self) -> List[Dict[str, Any]]:
        """Supabase에서 새로운 URL 가져오기"""
        try:
            # 아직 처리되지 않은 URL 조회
            # attachment_urls가 있지만 files가 없는 레코드
            response = supabase.table('kstartup_announcements').select(
                'id, pbln_pblancnm, attachment_urls'
            ).not_.is_('attachment_urls', 'null').is_('files', 'null').limit(10).execute()
            
            kstartup_urls = response.data if response.data else []
            
            # BizInfo도 확인
            response = supabase.table('bizinfo_announcements').select(
                'id, pbln_sj, attachment_urls'
            ).not_.is_('attachment_urls', 'null').is_('files', 'null').limit(10).execute()
            
            bizinfo_urls = response.data if response.data else []
            
            # 결합하여 반환
            all_urls = []
            
            for item in kstartup_urls:
                all_urls.append({
                    'source': 'kstartup',
                    'id': item['id'],
                    'title': item['pbln_pblancnm'],
                    'urls': item['attachment_urls']
                })
                
            for item in bizinfo_urls:
                all_urls.append({
                    'source': 'bizinfo',
                    'id': item['id'],
                    'title': item['pbln_sj'],
                    'urls': item['attachment_urls']
                })
                
            logger.info(f"새로운 URL {len(all_urls)}개 발견")
            return all_urls
            
        except Exception as e:
            logger.error(f"URL 조회 실패: {e}")
            return []
    
    def run_step1(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """Step 1: 첨부파일 다운로드"""
        logger.info(f"[Step 1] {announcement['title']} 다운로드 시작")
        
        result = {
            'step': 1,
            'announcement_id': announcement['id'],
            'source': announcement['source'],
            'status': 'pending',
            'files': []
        }
        
        # Supabase 상태 업데이트 - 처리 시작
        self.update_db_status(announcement['id'], announcement['source'], 'step1_processing')
        
        try:
            if announcement['source'] == 'kstartup':
                # K-Startup 다운로드 실행
                downloaded_files = step1_kstartup(
                    announcement_id=announcement['id'],
                    urls=announcement['urls']
                )
            else:
                # BizInfo 다운로드 실행
                downloaded_files = step1_bizinfo(
                    announcement_id=announcement['id'],
                    urls=announcement['urls']
                )
            
            result['status'] = 'completed'
            result['files'] = downloaded_files
            result['completed_at'] = datetime.now().isoformat()
            
            # Supabase 파일 목록 업데이트
            self.update_db_files(announcement['id'], announcement['source'], downloaded_files, step=1)
            
            logger.info(f"[Step 1] 완료: {len(downloaded_files)}개 파일 다운로드")
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"[Step 1] 실패: {e}")
            
            # Supabase 오류 상태 업데이트
            self.update_db_status(announcement['id'], announcement['source'], 'step1_failed', str(e))
        
        # 결과 저장
        self.save_step_result(announcement['id'], 1, result)
        return result
    
    def run_step2(self, announcement_id: str, source: str, step1_result: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2: HWP → PDF 변환"""
        logger.info(f"[Step 2] {announcement_id} HWP 변환 시작")
        
        result = {
            'step': 2,
            'announcement_id': announcement_id,
            'status': 'pending',
            'converted_files': []
        }
        
        # Supabase 상태 업데이트
        self.update_db_status(announcement_id, source, 'step2_processing')
        
        try:
            hwp_files = [f for f in step1_result['files'] if f.endswith('.hwp') or f.endswith('.hwpx')]
            
            if hwp_files:
                converted = step2_convert(hwp_files)
                result['converted_files'] = converted
                logger.info(f"[Step 2] {len(converted)}개 파일 변환 완료")
                
                # DB 파일 목록 업데이트
                self.update_db_files(announcement_id, source, converted, step=2)
            else:
                logger.info("[Step 2] 변환할 HWP 파일 없음")
            
            result['status'] = 'completed'
            result['completed_at'] = datetime.now().isoformat()
            
            # 상태 업데이트
            self.update_db_status(announcement_id, source, 'step2_completed')
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"[Step 2] 실패: {e}")
            self.update_db_status(announcement_id, source, 'step2_failed', str(e))
        
        self.save_step_result(announcement_id, 2, result)
        return result
    
    def run_step3(self, announcement_id: str, source: str, files: List[str]) -> Dict[str, Any]:
        """Step 3: PDF 구조 추출 및 텍스트 변환"""
        logger.info(f"[Step 3] {announcement_id} PDF 텍스트 추출 시작")
        
        result = {
            'step': 3,
            'announcement_id': announcement_id,
            'status': 'pending',
            'text_files': [],
            'metadata': {}
        }
        
        # 상태 업데이트
        self.update_db_status(announcement_id, source, 'step3_processing')
        
        try:
            pdf_files = [f for f in files if f.endswith('.pdf')]
            
            if pdf_files:
                text_files, metadata = step3_extract(pdf_files)
                result['text_files'] = text_files
                result['metadata'] = metadata
                logger.info(f"[Step 3] {len(text_files)}개 텍스트 파일 생성")
                
                # DB 업데이트
                self.update_db_files(announcement_id, source, text_files, step=3)
            else:
                logger.info("[Step 3] 처리할 PDF 파일 없음")
            
            result['status'] = 'completed'
            result['completed_at'] = datetime.now().isoformat()
            self.update_db_status(announcement_id, source, 'step3_completed')
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"[Step 3] 실패: {e}")
            self.update_db_status(announcement_id, source, 'step3_failed', str(e))
        
        self.save_step_result(announcement_id, 3, result)
        return result
    
    def run_step4(self, announcement_id: str, source: str, text_files: List[str], metadata: Dict) -> Dict[str, Any]:
        """Step 4: AI 요약 생성"""
        logger.info(f"[Step 4] {announcement_id} AI 요약 시작")
        
        result = {
            'step': 4,
            'announcement_id': announcement_id,
            'status': 'pending',
            'summary': None,
            'enhanced_metadata': {}
        }
        
        # 상태 업데이트
        self.update_db_status(announcement_id, source, 'step4_processing')
        
        try:
            if text_files:
                summary, enhanced_metadata = step4_summarize(text_files, metadata)
                result['summary'] = summary
                result['enhanced_metadata'] = enhanced_metadata
                logger.info("[Step 4] AI 요약 생성 완료")
                
                # DB 요약 정보 업데이트
                self.update_db_summary(announcement_id, source, summary, enhanced_metadata)
                self.update_db_files(announcement_id, source, [], step=4)
            else:
                logger.info("[Step 4] 요약할 텍스트 파일 없음")
            
            result['status'] = 'completed'
            result['completed_at'] = datetime.now().isoformat()
            self.update_db_status(announcement_id, source, 'step4_completed')
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"[Step 4] 실패: {e}")
            self.update_db_status(announcement_id, source, 'step4_failed', str(e))
        
        self.save_step_result(announcement_id, 4, result)
        return result
    
    def run_step5(self, announcement_id: str, source: str, files: List[str], metadata: Dict) -> Dict[str, Any]:
        """Step 5: 스마트 청킹 및 DB 저장"""
        logger.info(f"[Step 5] {announcement_id} 스마트 청킹 시작")
        
        result = {
            'step': 5,
            'announcement_id': announcement_id,
            'status': 'pending',
            'chunks_saved': 0
        }
        
        # 상태 업데이트
        self.update_db_status(announcement_id, source, 'step5_processing')
        
        try:
            # Step 5 구현 예정
            # - 파일 크기별 청킹 전략 적용
            # - 메타데이터 기반 분할
            # - DB 저장
            
            logger.info("[Step 5] 스마트 청킹 구현 예정")
            result['status'] = 'pending_implementation'
            result['completed_at'] = datetime.now().isoformat()
            
            # 일단 구현 대기 상태로 표시
            self.update_db_status(announcement_id, source, 'step5_pending')
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            logger.error(f"[Step 5] 실패: {e}")
            self.update_db_status(announcement_id, source, 'step5_failed', str(e))
        
        self.save_step_result(announcement_id, 5, result)
        return result
    
    def save_step_result(self, announcement_id: str, step: int, result: Dict[str, Any]):
        """각 단계 결과를 JSON 파일로 저장"""
        result_file = PIPELINE_RESULTS_DIR / f"{announcement_id}_step{step}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"결과 저장: {result_file}")
    
    def update_db_status(self, announcement_id: str, source: str, status: str, error: str = None):
        """DB 상태 업데이트"""
        try:
            table_name = f"{source}_announcements"
            update_data = {
                'processing_status': status,
                'last_updated': datetime.now().isoformat()
            }
            
            if error:
                update_data['processing_error'] = error
            
            response = supabase.table(table_name).update(update_data).eq('id', announcement_id).execute()
            
            if response.data:
                logger.info(f"DB 상태 업데이트: {announcement_id} → {status}")
            else:
                logger.error(f"DB 상태 업데이트 실패: {announcement_id}")
                
        except Exception as e:
            logger.error(f"DB 상태 업데이트 오류: {e}")
    
    def update_db_files(self, announcement_id: str, source: str, files: List[str], step: int):
        """DB 파일 목록 업데이트"""
        try:
            table_name = f"{source}_announcements"
            
            # 기존 파일 정보 가져오기
            response = supabase.table(table_name).select('files').eq('id', announcement_id).single().execute()
            existing_files = response.data.get('files', {}) if response.data else {}
            
            # Step별 파일 정보 업데이트
            if step == 1:
                existing_files['downloaded'] = files
            elif step == 2:
                existing_files['converted'] = files
            elif step == 3:
                existing_files['text_files'] = files
            elif step == 4:
                existing_files['summary_generated'] = True
            elif step == 5:
                existing_files['chunks_created'] = True
            
            # DB 업데이트
            update_data = {
                'files': existing_files,
                f'step{step}_completed': datetime.now().isoformat()
            }
            
            response = supabase.table(table_name).update(update_data).eq('id', announcement_id).execute()
            
            if response.data:
                logger.info(f"DB 파일 정보 업데이트: {announcement_id} Step {step}")
            else:
                logger.error(f"DB 파일 정보 업데이트 실패: {announcement_id}")
                
        except Exception as e:
            logger.error(f"DB 파일 정보 업데이트 오류: {e}")
    
    def update_db_summary(self, announcement_id: str, source: str, summary: str, metadata: Dict):
        """DB 요약 정보 업데이트"""
        try:
            table_name = f"{source}_announcements"
            
            update_data = {
                'ai_summary': summary,
                'metadata': metadata,
                'summary_created_at': datetime.now().isoformat()
            }
            
            response = supabase.table(table_name).update(update_data).eq('id', announcement_id).execute()
            
            if response.data:
                logger.info(f"DB 요약 정보 업데이트: {announcement_id}")
            else:
                logger.error(f"DB 요약 정보 업데이트 실패: {announcement_id}")
                
        except Exception as e:
            logger.error(f"DB 요약 정보 업데이트 오류: {e}")
    
    def process_announcement(self, announcement: Dict[str, Any]):
        """하나의 공고 전체 파이프라인 처리"""
        logger.info(f"===== 파이프라인 시작: {announcement['title']} =====")
        
        source = announcement['source']
        announcement_id = announcement['id']
        
        try:
            # Step 1: 다운로드
            step1_result = self.run_step1(announcement)
            if step1_result['status'] != 'completed':
                logger.error("Step 1 실패, 파이프라인 중단")
                self.update_db_status(announcement_id, source, 'pipeline_failed', 'Step 1 failed')
                return
            
            # Step 2: HWP 변환
            step2_result = self.run_step2(announcement_id, source, step1_result)
            
            # 모든 파일 목록 (원본 + 변환된 파일)
            all_files = step1_result['files'] + step2_result.get('converted_files', [])
            
            # Step 3: 텍스트 추출
            step3_result = self.run_step3(announcement_id, source, all_files)
            if step3_result['status'] != 'completed':
                logger.error("Step 3 실패, 파이프라인 중단")
                self.update_db_status(announcement_id, source, 'pipeline_failed', 'Step 3 failed')
                return
            
            # Step 4: AI 요약
            step4_result = self.run_step4(
                announcement_id,
                source,
                step3_result['text_files'],
                step3_result['metadata']
            )
            
            # Step 5: 스마트 청킹 (구현 예정)
            step5_result = self.run_step5(
                announcement_id,
                source,
                all_files,
                step4_result.get('enhanced_metadata', {})
            )
            
            # 파이프라인 완료 상태 업데이트
            self.update_db_status(announcement_id, source, 'pipeline_completed')
            logger.info(f"===== 파이프라인 완료: {announcement['title']} =====")
            
        except Exception as e:
            logger.error(f"파이프라인 오류: {e}")
            logger.error(traceback.format_exc())
            self.update_db_status(announcement_id, source, 'pipeline_error', str(e))
    
    def run(self):
        """메인 실행 루프"""
        logger.info("통합 파이프라인 매니저 시작")
        self.running = True
        
        while self.running:
            try:
                # 새로운 URL 확인
                new_announcements = self.get_new_urls()
                
                if new_announcements:
                    logger.info(f"{len(new_announcements)}개 공고 처리 시작")
                    
                    for announcement in new_announcements:
                        self.process_announcement(announcement)
                        
                        # 다음 공고 처리 전 잠시 대기
                        time.sleep(5)
                else:
                    logger.info("새로운 URL 없음")
                
                # 다음 확인까지 대기
                logger.info(f"{self.check_interval}초 대기...")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("사용자 중단")
                self.running = False
                break
            except Exception as e:
                logger.error(f"메인 루프 오류: {e}")
                logger.error(traceback.format_exc())
                time.sleep(60)  # 오류 발생 시 1분 대기
    
    def stop(self):
        """매니저 중지"""
        self.running = False
        logger.info("통합 파이프라인 매니저 중지")

def main():
    """메인 함수"""
    # 로그 폴더 생성
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # 매니저 실행
    manager = PipelineManager()
    
    try:
        manager.run()
    except KeyboardInterrupt:
        logger.info("프로그램 종료")
    except Exception as e:
        logger.error(f"치명적 오류: {e}")
        logger.error(traceback.format_exc())
    finally:
        manager.stop()

if __name__ == "__main__":
    main()