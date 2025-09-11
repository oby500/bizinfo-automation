#!/usr/bin/env python3
"""
첨부파일 완전성 검증 스크립트
서버 DB의 attachment_urls와 로컬 다운로드 파일을 비교 검증
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from typing import Dict, List, Tuple
import hashlib
from urllib.parse import urlparse, unquote
from collections import defaultdict

# 환경변수 로드
load_dotenv()

class AttachmentVerifier:
    def __init__(self):
        self.project_root = Path("E:\\gov-support-automation")
        self.downloads_dir = self.project_root / "downloads"
        self.kstartup_dir = self.downloads_dir / "kstartup"
        self.bizinfo_dir = self.downloads_dir / "bizinfo"
        
        # Supabase 연결
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        self.supabase = create_client(url, key) if url and key else None
        
        # 통계 초기화
        self.stats = {
            'kstartup': {
                'db_total': 0,
                'db_with_attachments': 0,
                'total_attachment_urls': 0,
                'local_files': 0,
                'matched': 0,
                'missing': 0,
                'extra': 0,
                'errors': []
            },
            'bizinfo': {
                'db_total': 0,
                'db_with_attachments': 0,
                'total_attachment_urls': 0,
                'local_files': 0,
                'matched': 0,
                'missing': 0,
                'extra': 0,
                'errors': []
            }
        }
        
    def get_server_attachments(self, table_name: str) -> Dict[str, List[str]]:
        """서버에서 첨부파일 URL 조회"""
        if not self.supabase:
            print("[ERROR] Supabase 연결 없음")
            return {}
        
        print(f"\n[조회] {table_name} 테이블에서 첨부파일 정보 가져오는 중...")
        
        attachments_by_id = {}
        try:
            # 전체 레코드 수 확인
            total_result = self.supabase.table(table_name).select('id', count='exact', head=True).execute()
            total_count = total_result.count
            print(f"  전체 레코드 수: {total_count}")
            
            # attachment_urls가 있는 레코드만 조회 (페이징 처리)
            offset = 0
            limit = 1000
            
            while True:
                result = self.supabase.table(table_name)\
                    .select('id, attachment_urls')\
                    .not_.is_('attachment_urls', 'null')\
                    .range(offset, offset + limit - 1)\
                    .execute()
                
                if not result.data:
                    break
                    
                for record in result.data:
                    if record.get('attachment_urls'):
                        # attachment_urls가 문자열인 경우 JSON 파싱
                        urls = record['attachment_urls']
                        if isinstance(urls, str):
                            try:
                                urls = json.loads(urls)
                            except:
                                urls = [urls] if urls else []
                        elif not isinstance(urls, list):
                            urls = []
                        
                        if urls:
                            attachments_by_id[record['id']] = urls
                
                if len(result.data) < limit:
                    break
                offset += limit
            
            print(f"  첨부파일이 있는 레코드: {len(attachments_by_id)}개")
            
            # 전체 URL 수 계산
            total_urls = sum(len(urls) for urls in attachments_by_id.values())
            print(f"  총 첨부파일 URL 수: {total_urls}개")
            
            return attachments_by_id
            
        except Exception as e:
            print(f"[ERROR] 서버 조회 실패: {e}")
            return {}
    
    def get_local_files(self, folder_path: Path) -> Dict[str, Dict]:
        """로컬 파일 목록 조회"""
        files_info = {}
        
        if not folder_path.exists():
            print(f"[WARNING] 폴더 없음: {folder_path}")
            return files_info
        
        for file_path in folder_path.glob("*"):
            if file_path.is_file():
                file_info = {
                    'path': str(file_path),
                    'size': file_path.stat().st_size,
                    'name': file_path.name
                }
                files_info[file_path.name] = file_info
        
        return files_info
    
    def extract_id_from_filename(self, filename: str, source: str) -> str:
        """파일명에서 ID 추출"""
        if source == 'kstartup':
            # KS_123456_... 형식
            if filename.startswith('KS_'):
                parts = filename.split('_')
                if len(parts) >= 2:
                    return f"KS_{parts[1]}"
        elif source == 'bizinfo':
            # PBLN_123456_... 형식
            if filename.startswith('PBLN_'):
                parts = filename.split('_')
                if len(parts) >= 2:
                    return f"PBLN_{parts[1]}"
        return None
    
    def extract_id_from_url(self, url: str, source: str) -> str:
        """URL에서 ID 추출"""
        if source == 'kstartup':
            # /fileDownload/xxxxx 형식에서 ID 추출
            if 'KS_' in url:
                import re
                match = re.search(r'KS_(\d+)', url)
                if match:
                    return f"KS_{match.group(1)}"
        elif source == 'bizinfo':
            # bizinfo URL에서 ID 추출
            if 'pbancNo=' in url:
                import re
                match = re.search(r'pbancNo=(\d+)', url)
                if match:
                    return f"PBLN_{match.group(1)}"
        return None
    
    def verify_kstartup(self):
        """K-Startup 첨부파일 검증"""
        print("\n" + "="*80)
        print("K-STARTUP 첨부파일 검증")
        print("="*80)
        
        # 서버 데이터 조회
        server_attachments = self.get_server_attachments('kstartup_complete')
        self.stats['kstartup']['db_total'] = len(server_attachments)
        self.stats['kstartup']['db_with_attachments'] = len(server_attachments)
        
        # 로컬 파일 조회
        local_files = self.get_local_files(self.kstartup_dir)
        self.stats['kstartup']['local_files'] = len(local_files)
        
        print(f"\n[비교] 서버 vs 로컬")
        print(f"  서버 레코드 (첨부파일 있음): {len(server_attachments)}개")
        print(f"  로컬 파일: {len(local_files)}개")
        
        # URL별 파일 매칭
        url_to_file = {}
        file_to_url = {}
        unmatched_files = set(local_files.keys())
        missing_urls = []
        
        # 각 레코드의 URL과 로컬 파일 매칭
        for record_id, urls in server_attachments.items():
            self.stats['kstartup']['total_attachment_urls'] += len(urls)
            
            for url in urls:
                # URL에서 파일명 추출 시도
                found = False
                
                # 파일명에서 해당 ID를 포함하는 파일 찾기
                id_part = str(record_id).replace('KS_', '')
                for filename in local_files.keys():
                    if id_part in filename:
                        url_to_file[url] = filename
                        file_to_url[filename] = url
                        if filename in unmatched_files:
                            unmatched_files.remove(filename)
                        found = True
                        self.stats['kstartup']['matched'] += 1
                        break
                
                if not found:
                    missing_urls.append((record_id, url))
                    self.stats['kstartup']['missing'] += 1
        
        self.stats['kstartup']['extra'] = len(unmatched_files)
        
        # 결과 출력
        print(f"\n[결과]")
        print(f"  총 URL 수: {self.stats['kstartup']['total_attachment_urls']}개")
        print(f"  매칭 성공: {self.stats['kstartup']['matched']}개")
        print(f"  서버에만 있음 (미다운로드): {self.stats['kstartup']['missing']}개")
        print(f"  로컬에만 있음 (추가 파일): {self.stats['kstartup']['extra']}개")
        
        # 문제 파일 샘플 출력
        if missing_urls:
            print(f"\n[미다운로드 샘플] (최대 10개)")
            for record_id, url in missing_urls[:10]:
                print(f"  {record_id}: {url}")
        
        if unmatched_files:
            print(f"\n[로컬에만 있는 파일 샘플] (최대 10개)")
            for filename in list(unmatched_files)[:10]:
                print(f"  {filename}")
        
        return self.stats['kstartup']
    
    def verify_bizinfo(self):
        """BizInfo 첨부파일 검증"""
        print("\n" + "="*80)
        print("BIZINFO 첨부파일 검증")
        print("="*80)
        
        # 서버 데이터 조회
        server_attachments = self.get_server_attachments('bizinfo_complete')
        self.stats['bizinfo']['db_total'] = len(server_attachments)
        self.stats['bizinfo']['db_with_attachments'] = len(server_attachments)
        
        # 로컬 파일 조회
        local_files = self.get_local_files(self.bizinfo_dir)
        self.stats['bizinfo']['local_files'] = len(local_files)
        
        print(f"\n[비교] 서버 vs 로컬")
        print(f"  서버 레코드 (첨부파일 있음): {len(server_attachments)}개")
        print(f"  로컬 파일: {len(local_files)}개")
        
        # URL별 파일 매칭
        url_to_file = {}
        file_to_url = {}
        unmatched_files = set(local_files.keys())
        missing_urls = []
        
        # 각 레코드의 URL과 로컬 파일 매칭
        for record_id, urls in server_attachments.items():
            self.stats['bizinfo']['total_attachment_urls'] += len(urls)
            
            for url in urls:
                # URL에서 파일명 추출 시도
                found = False
                
                # 파일명에서 해당 ID를 포함하는 파일 찾기
                id_part = str(record_id).replace('PBLN_', '')
                for filename in local_files.keys():
                    if id_part in filename:
                        url_to_file[url] = filename
                        file_to_url[filename] = url
                        if filename in unmatched_files:
                            unmatched_files.remove(filename)
                        found = True
                        self.stats['bizinfo']['matched'] += 1
                        break
                
                if not found:
                    missing_urls.append((record_id, url))
                    self.stats['bizinfo']['missing'] += 1
        
        self.stats['bizinfo']['extra'] = len(unmatched_files)
        
        # 결과 출력
        print(f"\n[결과]")
        print(f"  총 URL 수: {self.stats['bizinfo']['total_attachment_urls']}개")
        print(f"  매칭 성공: {self.stats['bizinfo']['matched']}개")
        print(f"  서버에만 있음 (미다운로드): {self.stats['bizinfo']['missing']}개")
        print(f"  로컬에만 있음 (추가 파일): {self.stats['bizinfo']['extra']}개")
        
        # 문제 파일 샘플 출력
        if missing_urls:
            print(f"\n[미다운로드 샘플] (최대 10개)")
            for record_id, url in missing_urls[:10]:
                print(f"  {record_id}: {url}")
        
        if unmatched_files:
            print(f"\n[로컬에만 있는 파일 샘플] (최대 10개)")
            for filename in list(unmatched_files)[:10]:
                print(f"  {filename}")
        
        return self.stats['bizinfo']
    
    def generate_report(self):
        """종합 보고서 생성"""
        print("\n" + "="*80)
        print("종합 검증 보고서")
        print("="*80)
        
        # 전체 통계
        total_db_urls = self.stats['kstartup']['total_attachment_urls'] + \
                       self.stats['bizinfo']['total_attachment_urls']
        total_local_files = self.stats['kstartup']['local_files'] + \
                           self.stats['bizinfo']['local_files']
        total_matched = self.stats['kstartup']['matched'] + \
                       self.stats['bizinfo']['matched']
        total_missing = self.stats['kstartup']['missing'] + \
                       self.stats['bizinfo']['missing']
        total_extra = self.stats['kstartup']['extra'] + \
                     self.stats['bizinfo']['extra']
        
        print(f"\n[전체 통계]")
        print(f"  서버 총 URL 수: {total_db_urls:,}개")
        print(f"  로컬 총 파일 수: {total_local_files:,}개")
        print(f"  매칭 성공: {total_matched:,}개 ({total_matched/total_db_urls*100:.1f}%)")
        print(f"  미다운로드: {total_missing:,}개 ({total_missing/total_db_urls*100:.1f}%)")
        print(f"  추가 파일: {total_extra:,}개")
        
        print(f"\n[K-Startup]")
        if self.stats['kstartup']['total_attachment_urls'] > 0:
            match_rate = self.stats['kstartup']['matched'] / self.stats['kstartup']['total_attachment_urls'] * 100
            print(f"  매칭률: {match_rate:.1f}%")
        print(f"  서버 URL: {self.stats['kstartup']['total_attachment_urls']:,}개")
        print(f"  로컬 파일: {self.stats['kstartup']['local_files']:,}개")
        print(f"  매칭: {self.stats['kstartup']['matched']:,}개")
        
        print(f"\n[BizInfo]")
        if self.stats['bizinfo']['total_attachment_urls'] > 0:
            match_rate = self.stats['bizinfo']['matched'] / self.stats['bizinfo']['total_attachment_urls'] * 100
            print(f"  매칭률: {match_rate:.1f}%")
        print(f"  서버 URL: {self.stats['bizinfo']['total_attachment_urls']:,}개")
        print(f"  로컬 파일: {self.stats['bizinfo']['local_files']:,}개")
        print(f"  매칭: {self.stats['bizinfo']['matched']:,}개")
        
        # JSON 보고서 저장
        report_file = self.project_root / "attachment_verification_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        print(f"\n[저장] 상세 보고서: {report_file}")
        
        return self.stats


def main():
    """메인 실행 함수"""
    verifier = AttachmentVerifier()
    
    # K-Startup 검증
    verifier.verify_kstartup()
    
    # BizInfo 검증
    verifier.verify_bizinfo()
    
    # 종합 보고서
    verifier.generate_report()


if __name__ == "__main__":
    main()