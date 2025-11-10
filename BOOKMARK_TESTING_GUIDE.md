# 북마크 기능 테스트 가이드

작성일: 2025-11-10
작성자: Claude (AI Assistant)

---

## 📋 목차

1. [사전 준비](#사전-준비)
2. [데이터베이스 테스트](#데이터베이스-테스트)
3. [Backend API 테스트](#backend-api-테스트)
4. [Frontend UI 테스트](#frontend-ui-테스트)
5. [통합 테스트](#통합-테스트)
6. [문제 해결](#문제-해결)

---

## 사전 준비

### 1. Supabase SQL 실행

북마크 테이블 생성:

```bash
# Supabase Dashboard 접속
# SQL Editor 열기
# 다음 파일 실행
cat E:\gov-support-automation\sql\create_bookmarks_table.sql
```

**검증**:
```sql
-- 테이블 생성 확인
SELECT * FROM bookmarks LIMIT 5;

-- RLS 정책 확인
SELECT tablename, policyname FROM pg_policies WHERE tablename = 'bookmarks';

-- 인덱스 확인
SELECT indexname FROM pg_indexes WHERE tablename = 'bookmarks';
```

**예상 결과**:
- 3개 RLS 정책: `Users can view own bookmarks`, `Users can insert own bookmarks`, `Users can delete own bookmarks`
- 4개 인덱스: `idx_bookmarks_user_id`, `idx_bookmarks_announcement`, `idx_bookmarks_created_at`, `idx_bookmarks_user_created`

---

## 데이터베이스 테스트

### Test 1: 북마크 추가

```sql
-- 테스트 데이터 추가 (임시 user_id 사용)
INSERT INTO bookmarks (user_id, announcement_id, announcement_source)
VALUES
  ('123e4567-e89b-12d3-a456-426614174000', 'KS_175399', 'kstartup'),
  ('123e4567-e89b-12d3-a456-426614174000', 'PBLN_000000000116027', 'bizinfo');

-- 확인
SELECT * FROM bookmarks ORDER BY created_at DESC;
```

**예상 결과**: 2개 레코드 추가됨

### Test 2: 중복 방지

```sql
-- 중복 추가 시도 (에러 발생 예상)
INSERT INTO bookmarks (user_id, announcement_id, announcement_source)
VALUES ('123e4567-e89b-12d3-a456-426614174000', 'KS_175399', 'kstartup');
```

**예상 결과**: `ERROR: duplicate key value violates unique constraint`

### Test 3: RLS 정책 테스트

```sql
-- 다른 사용자 데이터 추가
INSERT INTO bookmarks (user_id, announcement_id, announcement_source)
VALUES ('999e4567-e89b-12d3-a456-426614174999', 'KS_175400', 'kstartup');

-- 전체 조회 (Service Key로만 가능)
SELECT * FROM bookmarks;
```

**예상 결과**: Service Key로는 모든 데이터 조회 가능

---

## Backend API 테스트

### 사전 준비: FastAPI 서버 실행

```bash
cd E:\gov-support-automation\frontend
python app.py
```

**확인**: http://localhost:8000/docs 접속

### Test 1: POST /api/bookmarks - 북마크 추가

```bash
curl -X POST "http://localhost:8000/api/bookmarks?announcement_id=KS_175399&announcement_source=kstartup" \
  -H "X-User-ID: temp-user-id"
```

**예상 응답** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "temp-user-id",
  "announcement_id": "KS_175399",
  "announcement_source": "kstartup",
  "created_at": "2025-11-10T12:00:00Z"
}
```

### Test 2: GET /api/bookmarks - 북마크 목록 조회

```bash
curl -X GET "http://localhost:8000/api/bookmarks?page=1&page_size=20" \
  -H "X-User-ID: temp-user-id"
```

**예상 응답** (200 OK):
```json
{
  "bookmarks": [...],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### Test 3: DELETE /api/bookmarks/{id} - 북마크 삭제

```bash
curl -X DELETE "http://localhost:8000/api/bookmarks/{bookmark_id}" \
  -H "X-User-ID: temp-user-id"
```

**예상 응답** (200 OK):
```json
{
  "message": "북마크가 삭제되었습니다",
  "deleted_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Test 4: GET /api/bookmarks/check/{announcement_id} - 북마크 여부 확인

```bash
curl -X GET "http://localhost:8000/api/bookmarks/check/KS_175399?announcement_source=kstartup" \
  -H "X-User-ID: temp-user-id"
```

**예상 응답** (200 OK):
```json
{
  "is_bookmarked": true,
  "bookmark_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-11-10T12:00:00Z"
}
```

### Test 5: 에러 케이스

**5.1 인증 없이 요청**:
```bash
curl -X POST "http://localhost:8000/api/bookmarks?announcement_id=KS_175399&announcement_source=kstartup"
```
**예상 응답**: 401 Unauthorized

**5.2 잘못된 source**:
```bash
curl -X POST "http://localhost:8000/api/bookmarks?announcement_id=KS_175399&announcement_source=invalid" \
  -H "X-User-ID: temp-user-id"
```
**예상 응답**: 400 Bad Request

**5.3 중복 북마크**:
```bash
# 같은 공고 2번 추가
curl -X POST "http://localhost:8000/api/bookmarks?announcement_id=KS_175399&announcement_source=kstartup" \
  -H "X-User-ID: temp-user-id"
```
**예상 응답**: 409 Conflict

---

## Frontend UI 테스트

### 사전 준비: Next.js 서버 실행

```bash
cd E:\gov-support-automation\frontend-saas
npm run dev
# 또는
pnpm dev
```

**확인**: http://localhost:3000 접속

### Test 1: 메인 페이지 - BookmarkButton

1. http://localhost:3000 접속
2. 공고 목록에서 하트 아이콘 확인
3. 하트 아이콘 클릭 → 빨간색으로 변경 확인
4. 다시 클릭 → 회색으로 변경 확인
5. 개발자 도구 Console에서 에러 없는지 확인

**예상 동작**:
- 클릭 시 API 호출 (Network 탭 확인)
- 하트 색상 토글 (회색 ↔ 빨간색)
- 로딩 중 pulse 애니메이션

### Test 2: 상세 페이지 - BookmarkButton

1. 공고 클릭 → 상세 페이지 이동
2. 오른쪽 상단 하트 아이콘 확인
3. 클릭하여 북마크 추가/삭제 테스트

**예상 동작**:
- 메인 페이지와 동일한 동작
- 북마크 상태 일관성 유지

### Test 3: 북마크 목록 페이지

1. http://localhost:3000/bookmarks 접속
2. 저장한 북마크 목록 확인
3. "상세보기" 버튼 클릭 → 공고 상세 페이지 이동
4. 하트 아이콘 클릭 → 북마크 해제 → 목록에서 제거 확인

**예상 동작**:
- 북마크 목록 표시
- 페이지네이션 동작 (20개씩)
- 북마크 해제 시 즉시 목록에서 제거

### Test 4: 페이지네이션

1. 북마크 21개 이상 추가 (API 또는 SQL로)
2. 북마크 목록 페이지 접속
3. 페이지네이션 버튼 확인
4. 다음 페이지 이동 확인

**예상 동작**:
- 1페이지: 20개 표시
- 2페이지: 나머지 표시
- 페이지 번호 정확히 표시

---

## 통합 테스트

### E2E 시나리오 1: 신규 사용자 북마크 플로우

1. 메인 페이지 접속
2. 공고 검색 (예: "창업")
3. 첫 번째 공고 북마크 추가
4. 두 번째 공고 클릭 → 상세 페이지에서 북마크 추가
5. 북마크 목록 페이지 이동 (/bookmarks)
6. 2개 북마크 확인
7. 첫 번째 북마크 해제
8. 1개만 남은 것 확인

**예상 결과**: 모든 단계 정상 작동

### E2E 시나리오 2: 북마크 상태 일관성

1. 메인 페이지에서 공고 A 북마크 추가
2. 공고 A 클릭 → 상세 페이지
3. 상세 페이지에서 북마크 상태 확인 (빨간 하트)
4. 뒤로 가기 → 메인 페이지
5. 메인 페이지에서도 북마크 상태 유지 확인

**예상 결과**: 모든 페이지에서 북마크 상태 일관성 유지

### E2E 시나리오 3: 다중 탭 동작

1. 탭 A: 메인 페이지 접속
2. 탭 B: 동일 브라우저에서 북마크 목록 페이지 접속
3. 탭 A에서 공고 북마크 추가
4. 탭 B 새로고침 → 새 북마크 확인

**예상 결과**: 탭 간 데이터 일관성 유지

---

## 문제 해결

### 문제 1: "Supabase not configured" 에러

**원인**: 환경변수 미설정

**해결**:
```bash
# .env 파일 확인
cat E:\gov-support-automation\.env

# 필수 환경변수
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=xxxxx
```

### 문제 2: "인증이 필요합니다" 에러

**원인**: X-User-ID 헤더 누락

**해결**:
```typescript
// BookmarkButton.tsx에서 확인
headers: {
  'X-User-ID': 'temp-user-id', // TODO: 실제 세션에서 가져오기
}
```

**TODO**: NextAuth.js 세션 통합 필요

### 문제 3: RLS 정책으로 데이터 조회 안됨

**원인**: Service Key 대신 Anon Key 사용

**확인**:
```python
# frontend/routers/bookmark.py
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # SERVICE_KEY 사용 확인
```

### 문제 4: 북마크 버튼 클릭 시 카드 전체 클릭 이벤트 발생

**원인**: 이벤트 버블링

**해결**: 이미 적용됨
```typescript
// page.tsx
<div onClick={(e) => e.stopPropagation()}>
  <BookmarkButton ... />
</div>
```

### 문제 5: CORS 에러

**원인**: CORS 설정 누락

**해결**:
```python
# frontend/app.py 확인
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
```

---

## 체크리스트

### 데이터베이스
- [ ] bookmarks 테이블 생성 완료
- [ ] RLS 정책 3개 활성화 확인
- [ ] 인덱스 4개 생성 확인
- [ ] 중복 방지 제약조건 작동 확인

### Backend API
- [ ] POST /api/bookmarks 정상 작동
- [ ] GET /api/bookmarks 정상 작동
- [ ] DELETE /api/bookmarks/{id} 정상 작동
- [ ] GET /api/bookmarks/check/{id} 정상 작동
- [ ] Rate Limiting (60/min) 확인
- [ ] 에러 처리 정상 작동

### Frontend UI
- [ ] BookmarkButton 컴포넌트 렌더링
- [ ] 메인 페이지 통합 완료
- [ ] 상세 페이지 통합 완료
- [ ] 북마크 목록 페이지 정상 작동
- [ ] 페이지네이션 정상 작동

### 통합
- [ ] E2E 시나리오 1 통과
- [ ] E2E 시나리오 2 통과
- [ ] E2E 시나리오 3 통과

---

## 다음 단계 (TODO)

1. **NextAuth.js 세션 통합**
   - X-User-ID 헤더 대신 JWT 토큰 사용
   - 로그인한 사용자만 북마크 가능하도록 제한

2. **북마크 개수 표시**
   - 메인 페이지 헤더에 총 북마크 개수 표시
   - 북마크 목록 페이지에 카운트 표시

3. **북마크 내보내기**
   - 북마크 목록 Excel/CSV 내보내기 기능

4. **북마크 정렬 옵션**
   - 날짜순, 이름순, 마감일순 정렬

5. **북마크 검색**
   - 북마크 목록 내 검색 기능

---

## 참고 문서

- [UNIFIED_PROJECT_GUIDE.md](E:\gov-support-automation\PROJECT_DOCS\UNIFIED_PROJECT_GUIDE.md)
- [INFRASTRUCTURE_GUIDE.md](E:\gov-support-automation\PROJECT_DOCS\INFRASTRUCTURE_GUIDE.md)
- [OPERATION_LOG_2025_11.md](E:\gov-support-automation\PROJECT_DOCS\OPERATION_LOG_2025_11.md)
