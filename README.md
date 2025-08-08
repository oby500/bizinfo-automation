# 기업마당 자동 수집 시스템

## 📋 개요
기업마당(bizinfo.go.kr)의 정부지원사업 공고를 자동으로 수집하고 처리하는 시스템입니다.

## 🚀 기능
1. **데이터 수집**: 매일 오후 5시(평일) 자동으로 엑셀 다운로드 및 DB 저장
2. **첨부파일 크롤링**: 상세 페이지에서 첨부파일 링크 추출
3. **해시태그 생성**: 공고 내용 기반 자동 태그 생성
4. **요약 생성**: D-Day 계산 포함한 핵심 정보 요약

## ⚙️ 설정 방법

### 1. GitHub Secrets 설정
Repository Settings > Secrets and variables > Actions에서 다음 설정:
- `SUPABASE_URL`: Supabase 프로젝트 URL
- `SUPABASE_SERVICE_KEY`: Supabase Service Key (anon key 아님)

### 2. 수동 실행
Actions 탭에서 "Bizinfo Complete Processing" 워크플로우 선택 후 "Run workflow" 클릭

### 3. 자동 실행
평일 오후 5시(한국시간)에 자동 실행됩니다.

## 🔄 처리 프로세스
1. **17:00** - 기업마당 엑셀 다운로드 (최신 공고)
2. **즉시** - DB에 신규 데이터 저장 (중복 체크)
3. **연속** - 첨부파일 URL 크롤링
4. **동시** - 해시태그 및 요약 생성
5. **완료** - 처리 통계 출력
