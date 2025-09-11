#!/usr/bin/env python3
"""
상세 첨부파일 검증 및 자동화 스크립트 문서화
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import hashlib

# 환경변수 로드
load_dotenv()

class DetailedAttachmentVerifier:
    def __init__(self):
        self.project_root = Path("E:\\gov-support-automation")
        self.downloads_dir = self.project_root / "downloads"
        
        # Supabase 연결
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        self.supabase = create_client(url, key) if url and key else None
        
        # 통계 초기화
        self.results = {
            'kstartup': defaultdict(int),
            'bizinfo': defaultdict(int)
        }
        
        self.missing_downloads = {
            'kstartup': [],
            'bizinfo': []
        }
        
        self.local_files_map = {
            'kstartup': {},
            'bizinfo': {}
        }
    
    def get_server_attachments(self, table_name: str):
        """서버에서 첨부파일 정보 조회"""
        if not self.supabase:
            print("[ERROR] Supabase 연결 없음")
            return []
        
        print(f"\n[INFO] {table_name} 테이블 조회 중...")
        all_records = []
        
        try:
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
                    
                all_records.extend(result.data)
                
                if len(result.data) < limit:
                    break
                offset += limit
            
            print(f"  [OK] {len(all_records)}개 레코드 조회 완료")
            return all_records
            
        except Exception as e:
            print(f"  [ERROR] 조회 실패: {e}")
            return []
    
    def scan_local_files(self, source: str):
        """로컬 파일 스캔"""
        folder = self.downloads_dir / source
        if not folder.exists():
            print(f"  [ERROR] {folder} 폴더 없음")
            return {}
        
        files_map = {}
        for file_path in folder.glob("*"):
            if file_path.is_file():
                # 파일명에서 ID 추출
                filename = file_path.name
                if source == 'kstartup' and 'KS_' in filename:
                    # KS_174310_xxx.pdf 형식에서 174310 추출
                    parts = filename.split('_')
                    if len(parts) >= 2 and parts[1].isdigit():
                        record_id = int(parts[1])
                        if record_id not in files_map:
                            files_map[record_id] = []
                        files_map[record_id].append({
                            'filename': filename,
                            'path': str(file_path),
                            'size': file_path.stat().st_size
                        })
                elif source == 'bizinfo' and 'PBLN_' in filename:
                    # PBLN_123456_xxx.pdf 형식에서 123456 추출
                    parts = filename.split('_')
                    if len(parts) >= 2 and parts[1].isdigit():
                        record_id = int(parts[1])
                        if record_id not in files_map:
                            files_map[record_id] = []
                        files_map[record_id].append({
                            'filename': filename,
                            'path': str(file_path),
                            'size': file_path.stat().st_size
                        })
        
        return files_map
    
    def verify_source(self, source: str, table_name: str):
        """특정 소스 검증"""
        print(f"\n{'='*80}")
        print(f"[VERIFY] {source.upper()} 첨부파일 검증")
        print('='*80)
        
        # 서버 데이터 조회
        server_records = self.get_server_attachments(table_name)
        
        # 로컬 파일 스캔
        local_files = self.scan_local_files(source)
        self.local_files_map[source] = local_files
        
        # 통계 초기화
        total_server_urls = 0
        matched_urls = 0
        missing_urls = 0
        records_with_attachments = 0
        records_fully_downloaded = 0
        records_partially_downloaded = 0
        records_not_downloaded = 0
        
        # 각 레코드별 검증
        for record in server_records:
            record_id = record['id']
            attachment_urls = record.get('attachment_urls', [])
            
            if not attachment_urls:
                continue
            
            records_with_attachments += 1
            record_matched = 0
            record_total = 0
            
            # attachment_urls 처리
            if isinstance(attachment_urls, list):
                for url_item in attachment_urls:
                    if isinstance(url_item, dict):
                        # URL이 딕셔너리인 경우
                        url = url_item.get('url', '')
                        if url:
                            record_total += 1
                            total_server_urls += 1
                            
                            # 로컬 파일과 매칭 확인
                            if record_id in local_files:
                                # 해당 ID의 파일이 있는지 확인
                                record_matched += 1
                                matched_urls += 1
                            else:
                                missing_urls += 1
                                self.missing_downloads[source].append({
                                    'id': record_id,
                                    'url': url,
                                    'filename': url_item.get('original_filename', 'unknown')
                                })
                    elif isinstance(url_item, str):
                        # URL이 문자열인 경우
                        record_total += 1
                        total_server_urls += 1
                        
                        if record_id in local_files:
                            record_matched += 1
                            matched_urls += 1
                        else:
                            missing_urls += 1
                            self.missing_downloads[source].append({
                                'id': record_id,
                                'url': url_item,
                                'filename': 'unknown'
                            })
            
            # 레코드별 다운로드 상태 분류
            if record_total > 0:
                if record_matched == record_total:
                    records_fully_downloaded += 1
                elif record_matched > 0:
                    records_partially_downloaded += 1
                else:
                    records_not_downloaded += 1
        
        # 로컬에만 있는 파일 확인
        server_record_ids = {r['id'] for r in server_records}
        extra_local_ids = set(local_files.keys()) - server_record_ids
        
        # 통계 저장
        self.results[source] = {
            'total_server_records': len(server_records),
            'records_with_attachments': records_with_attachments,
            'total_server_urls': total_server_urls,
            'matched_urls': matched_urls,
            'missing_urls': missing_urls,
            'records_fully_downloaded': records_fully_downloaded,
            'records_partially_downloaded': records_partially_downloaded,
            'records_not_downloaded': records_not_downloaded,
            'total_local_files': sum(len(files) for files in local_files.values()),
            'local_record_ids': len(local_files),
            'extra_local_ids': len(extra_local_ids)
        }
        
        # 결과 출력
        print(f"\n[RESULT] 검증 결과:")
        print(f"  서버 레코드 (첨부파일 있음): {records_with_attachments:,}개")
        print(f"  서버 총 URL 수: {total_server_urls:,}개")
        print(f"  로컬 파일 수: {self.results[source]['total_local_files']:,}개")
        print(f"  로컬 레코드 ID 수: {self.results[source]['local_record_ids']:,}개")
        
        print(f"\n[STATUS] 다운로드 상태:")
        print(f"  [OK] 완전 다운로드: {records_fully_downloaded:,}개 레코드")
        print(f"  [WARN] 부분 다운로드: {records_partially_downloaded:,}개 레코드")
        print(f"  [FAIL] 미다운로드: {records_not_downloaded:,}개 레코드")
        
        if total_server_urls > 0:
            match_rate = (matched_urls / total_server_urls) * 100
            print(f"\n[MATCH] 매칭률: {match_rate:.1f}% ({matched_urls:,}/{total_server_urls:,})")
        
        # 문제 샘플 출력
        if self.missing_downloads[source]:
            print(f"\n[MISSING] 미다운로드 샘플 (최대 5개):")
            for item in self.missing_downloads[source][:5]:
                print(f"    ID: {item['id']}, 파일: {item['filename']}")
        
        if extra_local_ids:
            print(f"\n[EXTRA] 서버에 없는 로컬 파일 ID (최대 5개):")
            for local_id in list(extra_local_ids)[:5]:
                files = local_files[local_id]
                print(f"    ID: {local_id}, 파일 수: {len(files)}개")
    
    def generate_final_report(self):
        """최종 보고서 생성"""
        print("\n" + "="*80)
        print("[REPORT] 종합 검증 보고서")
        print("="*80)
        
        # 전체 통계
        total_server_urls = sum(r['total_server_urls'] for r in self.results.values())
        total_matched = sum(r['matched_urls'] for r in self.results.values())
        total_missing = sum(r['missing_urls'] for r in self.results.values())
        total_local_files = sum(r['total_local_files'] for r in self.results.values())
        
        print(f"\n[TOTAL] 전체 통계:")
        print(f"  서버 총 URL: {total_server_urls:,}개")
        print(f"  로컬 총 파일: {total_local_files:,}개")
        print(f"  매칭 성공: {total_matched:,}개")
        print(f"  미다운로드: {total_missing:,}개")
        
        if total_server_urls > 0:
            overall_match_rate = (total_matched / total_server_urls) * 100
            print(f"  전체 매칭률: {overall_match_rate:.1f}%")
        
        # 각 소스별 요약
        for source in ['kstartup', 'bizinfo']:
            if source in self.results:
                r = self.results[source]
                print(f"\n[{source.upper()}]:")
                print(f"  서버 URL: {r['total_server_urls']:,}개")
                print(f"  로컬 파일: {r['total_local_files']:,}개")
                print(f"  완전 다운로드: {r['records_fully_downloaded']:,}개 레코드")
                print(f"  부분 다운로드: {r['records_partially_downloaded']:,}개 레코드")
                print(f"  미다운로드: {r['records_not_downloaded']:,}개 레코드")
        
        # JSON 보고서 저장
        report_file = self.project_root / "attachment_verification_detailed.json"
        report_data = {
            'summary': {
                'total_server_urls': total_server_urls,
                'total_matched': total_matched,
                'total_missing': total_missing,
                'total_local_files': total_local_files,
                'overall_match_rate': overall_match_rate if total_server_urls > 0 else 0
            },
            'details': self.results,
            'missing_samples': {
                'kstartup': self.missing_downloads['kstartup'][:10],
                'bizinfo': self.missing_downloads['bizinfo'][:10]
            }
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[SAVE] 상세 보고서 저장: {report_file}")
        
        return report_data
    
    def document_automation_scripts(self):
        """GitHub Actions 자동화를 위한 스크립트 문서화"""
        print("\n" + "="*80)
        print("[DOC] 자동화 스크립트 문서화")
        print("="*80)
        
        automation_doc = """# 첨부파일 처리 자동화 스크립트 목록

## 🎯 핵심 자동화 스크립트

### 1. 메인 자동화 스크립트
- **`scripts/complete_automation.py`** - 전체 프로세스 자동화
- **`scripts/perfect_automation.py`** - 완벽한 다운로드 자동화
- **`scripts/all_in_one_automation.py`** - 올인원 자동화

### 2. 다운로드 스크립트
- **`scripts/download_100_percent.py`** - 100% 다운로드 보장
- **`perfect_attachment_downloader.py`** - 완벽한 첨부파일 다운로더
- **`complete_attachment_manager.py`** - 첨부파일 관리자

### 3. 파일명 처리 스크립트
- **`fix_broken_filenames_final.py`** - 깨진 파일명 수정
- **`complete_filename_fix.py`** - 파일명 완전 수정
- **`fix_html_entities.py`** - HTML 엔티티 디코딩

### 4. 검증 스크립트
- **`scripts/verify_attachments_complete.py`** - 첨부파일 완전성 검증
- **`scripts/detailed_attachment_verification.py`** - 상세 검증
- **`scripts/compare_server_local_attachments.py`** - 서버/로컬 비교

## 🔄 GitHub Actions 워크플로우 구성

```yaml
name: Attachment Processing Automation

on:
  schedule:
    - cron: '0 2 * * *'  # 매일 오전 2시 실행
  workflow_dispatch:  # 수동 실행 가능

jobs:
  process-attachments:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Download attachments
      run: |
        python scripts/download_100_percent.py
    
    - name: Fix filenames
      run: |
        python complete_filename_fix.py
    
    - name: Verify downloads
      run: |
        python scripts/verify_attachments_complete.py
    
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: attachment-reports
        path: |
          *.json
          downloads/
```

## 📋 실행 순서

1. **데이터 수집**: `collect_kstartup_batch.py` / `collect_bizinfo_batch.py`
2. **첨부파일 다운로드**: `download_100_percent.py`
3. **파일명 수정**: `complete_filename_fix.py`
4. **압축 해제**: (필요시 구현)
5. **텍스트 추출**: (다음 단계)
6. **검증**: `verify_attachments_complete.py`

## 🔧 환경 변수 설정

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
COLLECTION_MODE=full
```

## 📊 출력 파일

- `download_complete_record.json` - 다운로드 기록
- `attachment_verification_detailed.json` - 검증 보고서
- `downloads/kstartup/` - K-Startup 첨부파일
- `downloads/bizinfo/` - BizInfo 첨부파일
"""
        
        # 문서 저장
        doc_file = self.project_root / "AUTOMATION_SCRIPTS_GUIDE.md"
        with open(doc_file, 'w', encoding='utf-8') as f:
            f.write(automation_doc)
        
        print(f"[OK] 자동화 가이드 생성: {doc_file}")
        
        return doc_file


def main():
    """메인 실행"""
    verifier = DetailedAttachmentVerifier()
    
    # K-Startup 검증
    verifier.verify_source('kstartup', 'kstartup_complete')
    
    # BizInfo 검증
    verifier.verify_source('bizinfo', 'bizinfo_complete')
    
    # 최종 보고서
    verifier.generate_final_report()
    
    # 자동화 스크립트 문서화
    verifier.document_automation_scripts()


if __name__ == "__main__":
    main()