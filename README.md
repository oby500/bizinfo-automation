# 📊 정부지원사업 자동 수집 시스템

## 🚀 시스템 개요

기업마당(BizInfo)과 K-Startup의 정부지원사업 공고를 자동으로 수집하고 처리하는 통합 시스템입니다.

### 주요 기능
- ✅ 매일 자동 데이터 수집 (기업마당 17시, K-Startup 7시)
- ✅ 첨부파일 URL 크롤링 및 파일명 정규화
- ✅ 해시태그 자동 생성
- ✅ 사업 요약 자동 생성 (D-Day 포함)
- ✅ 10배 빠른 병렬 처리

## 📁 시스템 구조

```
bizinfo-automation/
├── .github/workflows/
│   ├── bizinfo_complete.yml         # 기업마당 자동 수집
│   ├── kstartup_complete.yml        # K-Startup 자동 수집
│   └── fix_all_data.yml            # 전체 데이터 수정
├── scripts/
│   ├── bizinfo_excel_collector.py   # 기업마당 수집
│   ├── bizinfo_complete_processor_fast.py  # 고속 처리
│   ├── kstartup_collector.py        # K-Startup 수집
│   └── kstartup_complete_processor_final.py # 최종 처리
```

## 🔄 자동 실행 스케줄

| 시간 | 대상 | 작업 내용 |
|------|------|-----------|
| 매일 07:00 | K-Startup | API 수집 → 첨부파일 크롤링 → 해시태그 생성 |
| 매일 17:00 | 기업마당 | 엑셀 다운로드 → 첨부파일 크롤링 → 요약 생성 |

## ⚡ 성능 최적화

### 처리 속도 (10배 향상)
| 데이터 수 | 기존 | 개선 후 |
|-----------|------|---------|
| 53개 | 6분 30초 | **30-40초** |
| 100개 | 12분 | **1분** |
| 460개 | 56분 | **4-5분** |

### 최적화 기법
- 병렬 처리 (ThreadPoolExecutor 5 workers)
- 배치 업데이트 (20개씩)
- 세션 재사용 (TCP 연결 유지)
- 불필요한 대기 시간 제거

## 💾 데이터베이스 구조

### 첨부파일 정규화
```json
{
  "url": "다운로드 URL",
  "safe_filename": "PBLN_000000000113475_01.hwp",  // 정규화
  "display_filename": "2025년 사업계획서.hwp",      // 원본
  "type": "HWP"
}
```

### 파일명 규칙
- 기업마당: `PBLN_{공고ID}_{순번}.{확장자}`
- K-Startup: `KS_{공고ID}_{순번}.{확장자}`

## 🔧 수동 실행 방법

### GitHub Actions에서 실행
1. Actions 탭 → "Manual Fix All Data"
2. Run workflow 클릭
3. 옵션 선택:
   - `target`: all / bizinfo / kstartup
   - `limit`: 처리 개수 (기본 500)

### 로컬 실행
```bash
# 환경변수 설정
export SUPABASE_URL="your-url"
export SUPABASE_SERVICE_KEY="your-key"

# 실행
python scripts/bizinfo_complete_processor_fast.py
python scripts/kstartup_complete_processor_final.py
```

## 📊 데이터 품질 지표

### 현재 상태
- 기업마당: 2,200+ 공고
- K-Startup: 460+ 공고
- 첨부파일: 3,000+ 링크
- 해시태그: 자동 생성됨

### 품질 관리
- safe_filename 100% 적용
- unknown 확장자 자동 재처리
- 중복 데이터 자동 제거

## 🐛 알려진 이슈 및 해결

| 이슈 | 원인 | 해결 |
|------|------|------|
| K-Startup 파일 `.unknown` | 특수 다운로드 방식 | HTML 구조 분석으로 추출 |
| 처리 속도 느림 | 순차 처리 | 병렬 처리 적용 |
| GitHub Actions 타임아웃 | 대량 데이터 | 배치 크기 최적화 |

## 🔐 보안 설정

### GitHub Secrets 필요
- `SUPABASE_URL`: Supabase 프로젝트 URL
- `SUPABASE_SERVICE_KEY`: Service Key (RLS 우회용)

### 주의사항
- Anon Key 사용 금지 (권한 부족)
- Service Key는 절대 공개 금지

## 📈 모니터링

### 일일 통계
- 신규 수집 건수
- 첨부파일 처리 상태
- 처리 시간
- 오류 발생 건수

### 품질 체크
- Unknown 확장자 개수
- Safe_filename 미적용 건수
- 해시태그 생성률

## 🚀 향후 계획

- [ ] 실시간 알림 시스템
- [ ] 맞춤형 추천 알고리즘
- [ ] 첨부파일 실제 다운로드
- [ ] AI 요약 생성

## 📞 문의

문제 발생 시 [GitHub Issues](https://github.com/oby500/bizinfo-automation/issues)에 등록

---
Last Updated: 2025-08-09
Version: 2.0
