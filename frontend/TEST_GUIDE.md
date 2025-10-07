# 🧪 테스트 가이드 - 상세 페이지 데이터 연동 확인

## ✅ 완료된 작업

### 1. 데이터 개수 확인 ✓
- **총 5,686개** 레코드 확인
- K-Startup: 1,527개
- BizInfo: 4,159개
- ✅ 목표 5,686개와 정확히 일치!

### 2. API 엔드포인트 확인 ✓
- `/api/stats` - 통계 API (정상)
- `/api/search` - 검색 API (정상)
- `/api/announcement/{id}` - 상세 조회 API (정상)
- 모든 API가 실제 Supabase 데이터 연동됨

### 3. 상세 페이지 데이터 바인딩 ✓
- **실제 API 호출로 변경**
- 로딩 상태 표시 추가
- 에러 처리 추가
- 첨부파일 다운로드 링크 연동
- AI 요약 (간단/상세) 표시
- 스크롤 가능한 상세 내용

### 4. D-day 색상 확인 ✓
- D-3 이하: 빨간색 (text-red-600)
- D-7 이하: 주황색 (text-orange-600)
- D-8 이상: 파란색 (text-blue-600)
- 마감: 회색 (text-gray-400)

---

## 🚀 테스트 방법

### Step 1: 서버 실행

#### 방법 1: 배치 파일 사용 (권장)
```batch
# E:\gov-support-automation\frontend\ 폴더에서
START_SAFE.bat
```

#### 방법 2: 직접 실행
```batch
cd E:\gov-support-automation\frontend
python app_safe.py
```

서버가 실행되면 다음과 같은 메시지가 표시됩니다:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

---

### Step 2: API 테스트 (선택)

새 터미널에서:
```batch
cd E:\gov-support-automation\frontend
python test_api_endpoint.py
```

**예상 결과:**
```
[1] Testing /api/stats
  Total: 5686
  Ongoing: 1983
  Deadline: 61
  [OK] Stats API working

[2] Testing /api/search
  Found: 5 results
  Sample: AI 기반 스타트업 지원사업...
  [OK] Search API working

[3] Testing /api/announcement/{id}
  Testing with ID: KS_174187
  Title: 2025년 AI 융합 창업지원사업...
  Organization: 중소벤처기업부
  Simple Summary: YES
  Detailed Summary: YES
  Attachments: 3
  [OK] Detail API working
```

---

### Step 3: 웹 브라우저 테스트

1. **브라우저 열기**
   - URL: http://localhost:8000
   - 크롬 권장 (F12로 개발자 도구 열기)

2. **기본 기능 확인**
   - ✅ 통계 카드 표시 (총 5,686개)
   - ✅ 검색창에 "AI" 입력 → 검색 결과 표시
   - ✅ 필터 선택 (K-Startup, BizInfo, 진행중, 마감임박)
   - ✅ 페이지네이션 동작

3. **D-day 색상 확인**
   - 목록에서 각 공고의 오른쪽 D-day 확인
   - D-3 이하: **빨간색**
   - D-7 이하: **주황색**
   - D-8 이상: **파란색**
   - 마감: **회색**

4. **상세 페이지 테스트** ⭐ 가장 중요!

   **a. 공고 클릭**
   - 목록에서 아무 공고나 클릭
   - 로딩 스피너 표시 확인 (회전하는 원)

   **b. 상세 정보 확인**
   - ✅ 제목 표시
   - ✅ 기관명 표시
   - ✅ 신청 기간 표시 (YYYY.MM.DD ~ YYYY.MM.DD)
   - ✅ 남은 기간 표시 (D-day 색상)

   **c. 요약 정보 확인**
   - ✅ "📋 간단 요약" 섹션에 4줄 요약
   - ✅ "📝 상세 내용" 섹션에 상세 요약 (스크롤 가능)

   **d. 첨부파일 확인**
   - ✅ "📎 첨부파일" 섹션에 파일 목록
   - ✅ 파일 클릭 시 다운로드/열기

   **e. 여러 공고 테스트**
   - K-Startup 공고 1개
   - BizInfo 공고 1개
   - 마감 임박 공고 1개

5. **개발자 도구 확인** (F12)

   **a. Network 탭**
   - 공고 클릭 시 `/api/announcement/{id}` 호출 확인
   - Status: 200 OK 확인
   - Response 탭에서 JSON 데이터 확인

   **b. Console 탭**
   - 에러 메시지 없는지 확인
   - 정상 동작 시 깨끗해야 함

---

## 🐛 문제 해결

### 문제 1: 서버가 시작되지 않음
```
해결: .env 파일 확인
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=eyJhbG...
```

### 문제 2: "Database not connected" 오류
```
해결: Supabase 환경변수 확인
python test_supabase_connection.py
```

### 문제 3: 상세 페이지가 로딩 중에서 멈춤
```
확인: 브라우저 Console (F12)에서 에러 확인
확인: 서버 터미널에서 에러 로그 확인
```

### 문제 4: 첨부파일이 표시되지 않음
```
확인: attachment_urls가 빈 배열인 경우 정상
일부 공고는 첨부파일이 없을 수 있음
```

### 문제 5: 한글이 깨짐
```
해결: chcp 65001 (UTF-8 설정)
또는 START_SAFE.bat 사용
```

---

## 📊 체크리스트

### 필수 확인 사항
- [ ] 서버 정상 실행 (http://localhost:8000)
- [ ] 5,686개 데이터 로드
- [ ] 검색 기능 동작
- [ ] 필터 기능 동작
- [ ] 페이지네이션 동작

### 상세 페이지 확인 (⭐ 가장 중요)
- [ ] 공고 클릭 시 로딩 표시
- [ ] 제목, 기관명 표시
- [ ] 신청 기간 표시
- [ ] D-day 색상 표시
- [ ] 간단 요약 표시
- [ ] 상세 내용 표시 (스크롤 가능)
- [ ] 첨부파일 목록 표시
- [ ] 첨부파일 클릭 시 다운로드
- [ ] K-Startup 공고 테스트
- [ ] BizInfo 공고 테스트

### D-day 색상 확인
- [ ] D-3 이하: 빨간색
- [ ] D-7 이하: 주황색
- [ ] D-8 이상: 파란색
- [ ] 마감: 회색

---

## 📸 스크린샷 촬영 가이드

테스트 완료 후 다음 스크린샷을 찍어주세요:

1. **메인 화면**: 전체 목록 (통계 카드 포함)
2. **검색 결과**: "AI" 검색 결과
3. **상세 모달**: K-Startup 공고 (전체)
4. **상세 모달**: BizInfo 공고 (전체)
5. **D-day 색상**: 서로 다른 색상의 공고들
6. **첨부파일**: 첨부파일이 있는 공고

---

## ✅ 성공 기준

1. ✅ **5,686개 데이터** 모두 로드
2. ✅ **상세 페이지** 실제 API 데이터 표시
3. ✅ **AI 요약** (간단/상세) 표시
4. ✅ **첨부파일** 다운로드 가능
5. ✅ **D-day 색상** 올바르게 표시
6. ✅ **로딩 속도** 2-3초 이내
7. ✅ **에러 없음** (Console 깨끗)

---

## 🎉 테스트 완료 후

모든 테스트가 성공하면:
1. 스크린샷 저장
2. 문제 발견 시 즉시 보고
3. 다음 작업 (벡터 검색) 준비

---

**작성일**: 2025-10-07
**버전**: 1.0
**작성자**: Claude Assistant
