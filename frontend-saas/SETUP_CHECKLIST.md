# 🎯 전체 설정 체크리스트

프로젝트를 실제로 운영하기 위해 **반드시 신청/설정해야 하는 항목** 정리

---

## 1️⃣ 소셜 로그인 설정 (필수)

### ✅ 카카오 로그인 - 설정 완료 가능
- **상태**: ✅ Client ID 이미 설정됨
- **가이드**: `SOCIAL_LOGIN_SETUP_GUIDE.md` 참고
- **설정 항목**: 없음 (이미 완료)

### ⚠️ 네이버 로그인 - **신청 필요**
- **상태**: ❌ Client ID/Secret 미설정
- **신청 페이지**: https://developers.naver.com/main/
- **가이드**: `NAVER_LOGIN_SETUP.md` (방금 생성됨)
- **소요 시간**: 즉시 발급
- **필요 작업**:
  1. 네이버 개발자 센터 접속
  2. 애플리케이션 등록
  3. Client ID, Client Secret 발급
  4. `.env` 파일 업데이트
  5. 서버 재시작

### ⚠️ 구글 로그인 - **신청 필요**
- **상태**: ❌ Client ID/Secret 미설정
- **신청 페이지**: https://console.cloud.google.com/
- **가이드**: `GOOGLE_LOGIN_SETUP.md` (방금 생성됨)
- **소요 시간**: 즉시 발급
- **필요 작업**:
  1. Google Cloud Console 접속
  2. 프로젝트 생성
  3. OAuth 동의 화면 구성
  4. OAuth 2.0 Client ID 생성
  5. Client ID, Client Secret 발급
  6. `.env` 파일 업데이트
  7. 테스트 사용자 추가
  8. 서버 재시작

---

## 2️⃣ 결제 시스템 설정 (필수)

### ⚠️ PortOne (구 아임포트) - **신청 및 심사 필요**
- **상태**: ❌ Store ID/API Secret 미설정
- **신청 페이지**: https://portone.io/
- **가이드**: `PORTONE_SETUP_GUIDE.md` 참고
- **소요 시간**:
  - 계정 생성: 즉시
  - PG사 연동: 1-3일 (사업자 서류 필요)
- **필요 작업**:
  1. PortOne 계정 생성
  2. 상점 생성
  3. **사업자 등록증** 제출 (필수!)
  4. PG사 선택 및 연동 신청
     - 토스페이먼츠 (추천)
     - KG이니시스
     - NHN KCP 등
  5. Store ID, API Secret 발급
  6. `.env` 파일 업데이트
  7. Webhook URL 등록

**⚠️ 중요**: PG사 연동은 **사업자 등록증**이 필수입니다!
- 개인사업자 또는 법인사업자 등록 필요
- 테스트 환경은 사업자 없이 가능
- 실제 결제는 사업자 인증 후 가능

---

## 3️⃣ 데이터베이스 설정 (이미 완료)

### ✅ Supabase - 설정 완료
- **상태**: ✅ 이미 연결됨
- **DB URL**: 설정 완료
- **Service Key**: 설정 완료

### ⚠️ 스키마 마이그레이션 - **실행 필요**
```bash
cd frontend-saas
pnpm db:migrate
```

소셜 로그인을 위한 스키마 변경사항:
- `users.passwordHash` 컬럼을 optional로 변경
- 이미 코드에는 반영됨
- DB 마이그레이션만 실행하면 됨

---

## 4️⃣ 환경 변수 설정 현황

### 📋 `.env` 파일 체크리스트

```env
# ✅ 완료된 항목
POSTGRES_URL=설정완료
BASE_URL=http://localhost:3000
AUTH_SECRET=설정완료
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=설정완료
SUPABASE_SERVICE_KEY=설정완료
NEXT_PUBLIC_KAKAO_CLIENT_ID=03553539b6b533e1f946ee56f052da3b

# ❌ 설정 필요 (네이버)
NEXT_PUBLIC_NAVER_CLIENT_ID=your_naver_client_id_here
NAVER_CLIENT_SECRET=your_naver_client_secret_here

# ❌ 설정 필요 (구글)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# ❌ 설정 필요 (결제)
NEXT_PUBLIC_PORTONE_STORE_ID=your_store_id_here
PORTONE_API_SECRET=your_api_secret_here

# 🗑️ 제거 예정 (Stripe - 사용 안 함)
STRIPE_SECRET_KEY=sk_test_placeholder
STRIPE_WEBHOOK_SECRET=whsec_placeholder
```

---

## 5️⃣ 우선순위별 작업 계획

### 🔥 높음 - 바로 실행 가능
1. **네이버 로그인 설정** (10분 소요)
   - 가이드: `NAVER_LOGIN_SETUP.md`
   - 즉시 발급 가능

2. **구글 로그인 설정** (15분 소요)
   - 가이드: `GOOGLE_LOGIN_SETUP.md`
   - 즉시 발급 가능
   - 테스트 사용자 추가 필요

3. **DB 마이그레이션** (1분 소요)
   ```bash
   cd frontend-saas
   pnpm db:migrate
   ```

### 🟡 중간 - 준비 후 신청
4. **PortOne 계정 생성** (즉시)
   - 가이드: `PORTONE_SETUP_GUIDE.md`
   - 테스트 결제는 바로 가능

### 🔴 낮음 - 사업자 등록 후
5. **PortOne PG사 연동** (1-3일 소요)
   - 사업자 등록증 필요
   - 실제 결제 기능 활성화

---

## 6️⃣ 테스트 환경 vs 프로덕션 환경

### 개발/테스트 (현재)
- ✅ 카카오 로그인: 바로 테스트 가능
- ⚠️ 네이버 로그인: Client ID 발급 후 테스트 가능
- ⚠️ 구글 로그인: Client ID 발급 + 테스트 사용자 추가 후 가능
- ⚠️ 결제: PortOne 계정만 있으면 테스트 결제 가능

### 프로덕션 (배포 시)
- 구글: OAuth 동의 화면 Publishing 필요 (구글 검토 7-14일)
- 결제: PG사 심사 완료 필요 (사업자 등록증, 1-3일)
- 도메인: 각 플랫폼에 실제 도메인 Redirect URI 추가 필요

---

## 7️⃣ 빠른 시작 가이드

### 지금 바로 할 수 있는 것:

1. **네이버 로그인 설정** (10분)
   ```bash
   # 1. NAVER_LOGIN_SETUP.md 열기
   # 2. 네이버 개발자 센터에서 앱 등록
   # 3. .env 파일 업데이트
   # 4. 서버 재시작
   ```

2. **구글 로그인 설정** (15분)
   ```bash
   # 1. GOOGLE_LOGIN_SETUP.md 열기
   # 2. Google Cloud Console에서 프로젝트 생성
   # 3. OAuth Client ID 발급
   # 4. .env 파일 업데이트
   # 5. 테스트 사용자 추가
   # 6. 서버 재시작
   ```

3. **PortOne 계정 생성** (5분)
   ```bash
   # 1. PORTONE_SETUP_GUIDE.md 열기
   # 2. PortOne 가입
   # 3. 상점 생성
   # 4. Store ID 확인
   # 5. .env 파일 업데이트
   # 6. 테스트 결제 시도 (사업자 없이 가능)
   ```

---

## ✅ 최종 체크리스트

### 즉시 실행 가능 (30분)
- [ ] 네이버 로그인 설정
- [ ] 구글 로그인 설정
- [ ] DB 마이그레이션 실행
- [ ] PortOne 계정 생성
- [ ] 모든 로그인 테스트

### 사업자 등록 후 (추가 1-3일)
- [ ] PortOne PG사 연동
- [ ] 실제 결제 테스트

### 프로덕션 배포 전 (추가 7-14일)
- [ ] 구글 OAuth 동의 화면 Publishing
- [ ] 실제 도메인 Redirect URI 추가
- [ ] 개인정보 처리방침 작성
- [ ] 서비스 약관 작성

---

## 📞 도움이 필요하면

각 가이드 문서를 참고하세요:
- 네이버: `NAVER_LOGIN_SETUP.md`
- 구글: `GOOGLE_LOGIN_SETUP.md`
- 결제: `PORTONE_SETUP_GUIDE.md`
- 전체 소셜 로그인: `SOCIAL_LOGIN_SETUP_GUIDE.md`
