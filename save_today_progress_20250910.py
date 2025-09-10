#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025-09-10 작업 내용 Supabase 저장
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from supabase import create_client
import os
from dotenv import load_dotenv
import json

load_dotenv()
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

# 로컬 시간 사용
local_date = '2025-09-10'
local_datetime = '2025-09-10 13:08:58'

content = """## 1. 완료한 작업

### 자동 파이프라인 설계 및 파일 저장 전략 수립
- 통합 매니저 기반 자동 파이프라인 설계 (URL 감지 → 다운로드 → 변환 → 추출 → 요약)
- Step별 결과 JSON 파일 저장 구조 설계 (`pipeline_results/` 폴더)
- 각 Step 완료 확인 후 다음 진행하는 안정적 실행 방식 확립

### 대용량 파일 분석 및 스마트 청킹 전략
- 5MB 이상 파일 101개 상세 분석 (총 1.5GB, 평균 15.25MB)
- 40MB PDF 파일 메타데이터 기반 9개 청크 분할 테스트
- 다양한 크기(6MB, 10MB, 20MB, 30MB) 파일별 최적 청크 수 산출

### 적응형 파일 저장 전략 확정
- 500KB 미만: 그대로 저장 (85.5%)
- 500KB-2MB: 3개 청크 분할 (11.4%)  
- 2-5MB: 5개 청크 분할 (2.1%)
- 5MB 이상: 최대 10개 청크 분할 (1.0%)

## 2. 발견한 문제와 해결책

### 문제 1: DB에서 JSONB 전체 로딩 문제
**문제**: JSONB에 여러 파일 저장 시 하나만 필요해도 전체 로딩
```sql
-- 문제: 40MB 전체 로딩
SELECT files FROM announcement_storage WHERE id = 'KS_123456';
```

**해결**: 파일별 개별 저장 + 메타데이터 기반 청킹
```sql
-- 해결: 필요한 청크만 로딩 (2-4MB)
SELECT chunk_data FROM pdf_chunks 
WHERE announcement_id = 'KS_123456' AND section_title LIKE '%자격%';
```

### 문제 2: 캐시 용량 한계
**문제**: PostgreSQL 캐시 256MB로 큰 JSONB 비효율
**해결**: 2MB 기준으로 분리 저장 전략

### 문제 3: 메타데이터 신뢰성
**문제**: 파일 분할 시 정확한 메타데이터 필요
**해결**: Step 3(구조 파악) + Step 4(AI 의미 분석) 이중 검증

## 3. 중요 결정사항

### 파일 저장 구조
- 공고당 1행 유지하되, 대용량 파일은 별도 테이블로 분리
- 메타데이터 중심 설계 (네비게이션 + AI 신청서 작성 가이드)
- 파일 데이터는 테이블 맨 오른쪽 컬럼 배치

### 자동화 전략
- 모든 Step 로컬 실행 (HWP 변환 필수 + Claude 구독 활용)
- 통합 매니저가 5분마다 새 URL 감지하여 자동 실행
- 각 Step 완료 확인 후 다음 진행 (안정성 우선)

### 청킹 전략
- 2MB를 기준점으로 설정
- 메타데이터 기반 책갈피식 분할
- 최대 10개 청크로 제한

## 4. 다음 작업

- [ ] Step 5 (스마트 청킹 저장) 구현
- [ ] 통합 매니저 스크립트 작성
- [ ] pipeline_results 폴더 구조 생성
- [ ] Windows 작업 스케줄러 설정
- [ ] 첫 번째 end-to-end 테스트

## 5. 주의사항

### 파일 크기별 처리
- 5MB 이상 파일은 반드시 청킹 처리
- 메타데이터 없을 경우 폴백 전략 (단순 페이지 분할)

### 캐시 관리
- 2MB 이상 파일은 캐시 부담 고려
- 자주 접근하는 청크만 우선 캐시

### Step 실행 순서
- 반드시 Step 3 → Step 4 → Step 5 순서 유지
- 메타데이터 생성 완료 후 분할 시작

## 6. 코드 변경사항

- **analyze_file_sizes_detailed.py**: 전체 파일 용량 분석 스크립트 생성
- **analyze_large_files.py**: 5MB 이상 대용량 파일 상세 분석
- **test_pdf_chunking.py**: 40MB PDF 청킹 시뮬레이션
- **test_multiple_pdf_chunking.py**: 다양한 크기 파일 청킹 테스트
- **save_today_progress_20250910.py**: 오늘 작업 내용 저장 (생성)

## 성과 요약

🎯 **파일 저장 전략 완성**
- 5,644개 파일 분석 완료
- 크기별 최적 청킹 전략 수립
- 90% 이상 메모리 절약 가능
- 10배 빠른 응답 속도 달성 가능"""

document_data = {
    'type': 'progress',
    'title': f'{local_date} 자동 파이프라인 및 스마트 청킹 전략 수립',
    'tags': ['claude-code', '스마트청킹', '파이프라인설계', '메타데이터'],
    'content': content
}

try:
    result = supabase.table('project_documents').insert(document_data).execute()
    
    if result.data:
        doc_id = result.data[0]['id']
        print(f'✅ Supabase 저장 완료!')
        print(f'📄 문서 ID: {doc_id}')
        print(f'📅 날짜: {local_date}')
        print(f'🏷️ 태그: {json.dumps(document_data["tags"], ensure_ascii=False)}')
        print(f'📊 주요 성과:')
        print(f'   - 5,644개 파일 분석 완료')
        print(f'   - 101개 대용량 파일 처리 전략 수립')
        print(f'   - 적응형 청킹 시스템 설계')
        print(f'   - 90% 메모리 절약, 10배 속도 향상 가능')
    else:
        print('❌ 저장 실패')
except Exception as e:
    print(f'오류: {e}')