# 웹 서비스 프로덕션 배포 가이드

**배포 플랫폼**: Vercel (Frontend) + Railway (Backend)
**3단계 환경**: dev.roten.kr → staging.roten.kr → roten.kr
**예상 비용**: $150-200/월 (Vercel Pro $20 + Railway Starter $5 + AI APIs $125-175)

---

## 목차

1. [사전 준비](#1-사전-준비)
2. [Vercel 설정 (Frontend)](#2-vercel-설정-frontend)
3. [Railway 설정 (Backend)](#3-railway-설정-backend)
4. [DNS 및 도메인 설정](#4-dns-및-도메인-설정)
5. [환경별 배포 전략](#5-환경별-배포-전략)
6. [배포 체크리스트](#6-배포-체크리스트)
7. [롤백 절차](#7-롤백-절차)
8. [모니터링 및 로그](#8-모니터링-및-로그)
9. [문제 해결](#9-문제-해결)

---

## 1. 사전 준비

### 1.1 필수 계정 생성

**Vercel 계정** (Frontend 호스팅)
- URL: https://vercel.com/signup
- 플랜: Pro ($20/월) - 3개 환경 분리 필요
- GitHub 계정으로 가입 권장

**Railway 계정** (Backend 호스팅)
- URL: https://railway.app/
- 플랜: Starter ($5/월 + 사용량)
- GitHub 계정으로 가입 권장

**도메인 등록** (선택)
- roten.kr 도메인 보유 확인
- DNS 관리 권한 확인

### 1.2 GitHub 저장소 준비

```bash
# 최신 코드 커밋 확인
git status
git add .
git commit -m "feat: 프로덕션 배포 준비"
git push origin main
```

### 1.3 환경변수 준비

다음 파일 참고하여 실제 값 준비:
- `frontend-saas/.env.production.example` (27개 환경변수)
- `frontend/.env.example` (17개 환경변수)

---

## 2. Vercel 설정 (Frontend)

### 2.1 프로젝트 생성

1. **Vercel Dashboard 접속**: https://vercel.com/dashboard
2. **"Add New Project"** 클릭
3. **Import Git Repository** 선택
4. GitHub 저장소 선택: `oby500/bizinfo-automation`
5. **Root Directory** 설정: `frontend-saas`
6. **Framework Preset**: Next.js (자동 감지)
7. **Build Command**: `pnpm build`
8. **Output Directory**: `.next`
9. **Install Command**: `pnpm install`

### 2.2 환경변수 설정

**Vercel Dashboard → Settings → Environment Variables**

다음 27개 환경변수를 **모든 환경(Production, Preview, Development)**에 추가:

#### 데이터베이스 (Supabase)
```
POSTGRES_URL=postgresql://postgres.[project-id]:[password]@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
```

#### 인증 (NextAuth.js)
```bash
# 32자 이상 랜덤 문자열 생성
openssl rand -base64 32

# 생성된 값을 AUTH_SECRET에 설정
AUTH_SECRET=<생성된_값>
BASE_URL=https://roten.kr  # 환경별로 다르게 설정
```

#### Supabase 클라이언트
```
NEXT_PUBLIC_SUPABASE_URL=https://csuziaogycciwgxxmahm.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 결제 시스템 (PortOne)
```
NEXT_PUBLIC_PORTONE_STORE_ID=store-98677ff8-f5b2-46ce-8761-2ac536238cb9
PORTONE_API_SECRET=4aCPBZedtU4RbmIWsCoogNTDI1zYDZclgAkaXIAWSMF3AEFh7zQ8yDzk3ttZXHLe3Zl3iiOeGBQh8XOF
```

#### OAuth (Google, Kakao, Naver)
```
NEXT_PUBLIC_GOOGLE_CLIENT_ID=...
NEXT_PUBLIC_GOOGLE_CLIENT_SECRET=...
NEXT_PUBLIC_KAKAO_CLIENT_ID=...
NEXT_PUBLIC_KAKAO_CLIENT_SECRET=...
NEXT_PUBLIC_NAVER_CLIENT_ID=...
NEXT_PUBLIC_NAVER_CLIENT_SECRET=...
```

#### 백엔드 API
```
# Railway 배포 후 생성된 URL 사용
NEXT_PUBLIC_API_URL=https://api.roten.kr
```

#### 기타
```
NEXT_TELEMETRY_DISABLED=1
NODE_ENV=production
```

### 2.3 환경별 설정

**Development 환경**
```
BASE_URL=https://dev.roten.kr
NEXT_PUBLIC_API_URL=https://api-dev.roten.kr
```

**Preview (Staging) 환경**
```
BASE_URL=https://staging.roten.kr
NEXT_PUBLIC_API_URL=https://api-staging.roten.kr
```

**Production 환경**
```
BASE_URL=https://roten.kr
NEXT_PUBLIC_API_URL=https://api.roten.kr
```

### 2.4 배포

**자동 배포** (GitHub 연동)
```bash
# main 브랜치에 push하면 자동 배포
git push origin main
```

**수동 배포**
- Vercel Dashboard → Deployments → "Redeploy" 클릭

---

## 3. Railway 설정 (Backend)

### 3.1 프로젝트 생성

1. **Railway Dashboard 접속**: https://railway.app/dashboard
2. **"New Project"** 클릭
3. **"Deploy from GitHub repo"** 선택
4. GitHub 저장소 선택: `oby500/bizinfo-automation`
5. **Root Directory**: `frontend` (FastAPI 백엔드)
6. **Builder**: Dockerfile (자동 감지)

### 3.2 환경변수 설정

**Railway Dashboard → Variables 탭**

다음 17개 환경변수 추가:

#### 데이터베이스 (Supabase)
```
SUPABASE_URL=https://csuziaogycciwgxxmahm.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...[service_role_key]
POSTGRES_URL=postgresql://postgres.[project-id]:[password]@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
```

#### AI APIs
```
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...
```

#### 파일 저장소
```
STORAGE_TYPE=supabase
SUPABASE_STORAGE_BUCKET=announcements
```

#### 데이터 수집
```
COLLECTION_MODE=auto
```

#### 서버 설정
```
HOST=0.0.0.0
PORT=8000
RELOAD=false
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
```

#### CORS 설정 (환경별)
```
# Development
CORS_ORIGINS=https://dev.roten.kr

# Staging
CORS_ORIGINS=https://staging.roten.kr

# Production
CORS_ORIGINS=https://roten.kr,https://www.roten.kr
```

#### 환경 설정
```
ENV=production
DEBUG=false
```

### 3.3 Health Check 설정

**Railway Dashboard → Settings → Healthcheck**
```
Healthcheck Path: /health
Healthcheck Timeout: 100
Restart Policy: ON_FAILURE
Max Retries: 10
```

### 3.4 배포

**자동 배포** (GitHub 연동)
```bash
# main 브랜치에 push하면 자동 배포
git push origin main
```

**배포 확인**
```bash
# Railway 생성한 임시 URL로 확인
curl https://[railway-domain].railway.app/health

# 응답 예시
{"status": "healthy", "version": "1.0.0"}
```

---

## 4. DNS 및 도메인 설정

### 4.1 Vercel 도메인 설정

**Vercel Dashboard → Settings → Domains**

#### Development 환경
```
도메인: dev.roten.kr
타입: CNAME
값: cname.vercel-dns.com
```

#### Staging 환경
```
도메인: staging.roten.kr
타입: CNAME
값: cname.vercel-dns.com
```

#### Production 환경
```
도메인: roten.kr
타입: A
값: 76.76.21.21 (Vercel IP)

도메인: www.roten.kr
타입: CNAME
값: cname.vercel-dns.com
```

### 4.2 Railway 도메인 설정

**Railway Dashboard → Settings → Domains**

#### Development 환경
```
도메인: api-dev.roten.kr
```

#### Staging 환경
```
도메인: api-staging.roten.kr
```

#### Production 환경
```
도메인: api.roten.kr
```

### 4.3 DNS 레코드 추가 (도메인 등록 업체)

**가비아, 후이즈, AWS Route 53 등에서 설정**

```
# Frontend (Vercel)
dev.roten.kr        CNAME  cname.vercel-dns.com
staging.roten.kr    CNAME  cname.vercel-dns.com
roten.kr            A      76.76.21.21
www.roten.kr        CNAME  cname.vercel-dns.com

# Backend (Railway)
api-dev.roten.kr      CNAME  [railway-generated].railway.app
api-staging.roten.kr  CNAME  [railway-generated].railway.app
api.roten.kr          CNAME  [railway-generated].railway.app
```

### 4.4 SSL 인증서

**Vercel**: 자동 발급 (Let's Encrypt)
**Railway**: 자동 발급 (Let's Encrypt)

도메인 추가 후 5-10분 내 자동 활성화

---

## 5. 환경별 배포 전략

### 5.1 Development (dev.roten.kr)

**목적**: 개발/테스트 환경
**배포 트리거**: `develop` 브랜치 push
**데이터**: 테스트 데이터 사용
**결제**: PortOne 테스트 모드

```bash
# develop 브랜치에서 작업
git checkout develop
git add .
git commit -m "feat: 새 기능 추가"
git push origin develop

# Vercel/Railway 자동 배포
```

### 5.2 Staging (staging.roten.kr)

**목적**: 프로덕션 배포 전 최종 검증
**배포 트리거**: `staging` 브랜치 push
**데이터**: 프로덕션 복제 데이터
**결제**: PortOne 테스트 모드

```bash
# develop → staging 머지
git checkout staging
git merge develop
git push origin staging

# QA 테스트 진행
# 문제 없으면 → Production 배포
```

### 5.3 Production (roten.kr)

**목적**: 실제 서비스 환경
**배포 트리거**: `main` 브랜치 push
**데이터**: 실제 사용자 데이터
**결제**: PortOne 실제 결제 (PG 승인 후)

```bash
# staging → main 머지
git checkout main
git merge staging
git push origin main

# 배포 후 모니터링
# 문제 발생 시 → 즉시 롤백
```

---

## 6. 배포 체크리스트

### 6.1 배포 전 체크리스트

- [ ] 모든 테스트 통과 확인
- [ ] 환경변수 27개 (Frontend) + 17개 (Backend) 설정 완료
- [ ] Supabase 테이블 생성 완료 (`sql/create_*.sql` 실행)
- [ ] PortOne PG 승인 완료 (실제 결제 사용 시)
- [ ] OAuth 콜백 URL 등록 (Google, Kakao, Naver)
- [ ] DNS 레코드 설정 완료 및 전파 확인 (24-48시간)
- [ ] SSL 인증서 자동 발급 확인
- [ ] 코드 리뷰 완료
- [ ] 배포 계획 팀원 공유

### 6.2 배포 후 체크리스트

- [ ] 프론트엔드 접속 확인 (https://roten.kr)
- [ ] 백엔드 Health Check 확인 (https://api.roten.kr/health)
- [ ] 로그인 기능 테스트 (Google, Kakao, Naver, Email)
- [ ] 공고 검색 기능 테스트
- [ ] 북마크 기능 테스트
- [ ] AI 신청서 작성 기능 테스트
- [ ] 결제 기능 테스트 (테스트 모드 → 실제 소액 결제)
- [ ] 모바일 반응형 확인 (iOS, Android)
- [ ] 브라우저 호환성 확인 (Chrome, Safari, Edge)
- [ ] 성능 측정 (Lighthouse 점수 80+ 목표)
- [ ] 에러 로그 확인 (Vercel, Railway)
- [ ] 모니터링 대시보드 확인

---

## 7. 롤백 절차

### 7.1 Vercel 롤백

**Vercel Dashboard → Deployments**

1. 이전 정상 배포 찾기
2. "..." 메뉴 → "Promote to Production" 클릭
3. 즉시 롤백 완료 (30초 이내)

**CLI 롤백**
```bash
# Vercel CLI 설치
npm i -g vercel

# 이전 배포로 롤백
vercel rollback [deployment-url]
```

### 7.2 Railway 롤백

**Railway Dashboard → Deployments**

1. 이전 정상 배포 찾기
2. "Rollback" 버튼 클릭
3. 즉시 롤백 완료 (1-2분)

**Git 기반 롤백**
```bash
# 이전 커밋으로 되돌리기
git revert HEAD
git push origin main

# Railway 자동 재배포
```

### 7.3 긴급 롤백 시나리오

**Critical Bug 발생 시**
```bash
# 1. 즉시 Vercel + Railway 롤백
# 2. 문제 원인 파악
# 3. Hotfix 브랜치 생성
git checkout -b hotfix/critical-bug main

# 4. 수정 후 즉시 배포
git add .
git commit -m "hotfix: Critical bug 수정"
git push origin hotfix/critical-bug

# 5. main 브랜치 머지
git checkout main
git merge hotfix/critical-bug
git push origin main
```

---

## 8. 모니터링 및 로그

### 8.1 Vercel 모니터링

**Vercel Dashboard → Analytics**
- Real-time Visitors
- Page Views
- Performance Metrics (Core Web Vitals)
- Error Rate

**로그 확인**
```bash
# Vercel CLI로 실시간 로그
vercel logs [deployment-url] --follow
```

### 8.2 Railway 모니터링

**Railway Dashboard → Metrics**
- CPU Usage
- Memory Usage
- Network Traffic
- Deployment Status

**로그 확인**
- Railway Dashboard → Logs 탭
- 실시간 스트리밍 로그 제공

### 8.3 Supabase 모니터링

**Supabase Dashboard → Database**
- Connection Pool Usage
- Query Performance
- Table Size
- Index Usage

**RLS Policy 확인**
```sql
-- 북마크 정책 확인
SELECT * FROM pg_policies WHERE tablename = 'bookmarks';

-- 신청서 정책 확인
SELECT * FROM pg_policies WHERE tablename = 'applications';
```

### 8.4 외부 모니터링 (선택)

**Sentry** (에러 추적)
```bash
npm install @sentry/nextjs
```

**Uptime Robot** (가동 시간 모니터링)
- URL: https://uptimerobot.com/
- 5분마다 ping 체크
- 장애 시 이메일/슬랙 알림

---

## 9. 문제 해결

### 9.1 빌드 실패

**증상**: Vercel 배포 실패, "Build Error"

**원인**:
- TypeScript 에러
- 환경변수 누락
- 의존성 문제

**해결**:
```bash
# 로컬에서 빌드 테스트
cd frontend-saas
pnpm install
pnpm build

# 에러 확인 후 수정
# TypeScript 에러: npm run type-check
# Lint 에러: npm run lint
```

### 9.2 환경변수 누락

**증상**: "NEXT_PUBLIC_SUPABASE_URL is not defined"

**해결**:
1. Vercel Dashboard → Settings → Environment Variables
2. 누락된 변수 추가
3. "Redeploy" 클릭

### 9.3 CORS 에러

**증상**: "CORS policy: No 'Access-Control-Allow-Origin' header"

**해결**:
```bash
# Railway 환경변수 확인
CORS_ORIGINS=https://roten.kr,https://www.roten.kr

# app.py CORS 설정 확인
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://roten.kr"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 9.4 데이터베이스 연결 실패

**증상**: "Connection refused" 또는 "Authentication failed"

**해결**:
```bash
# 1. Supabase 연결 정보 확인
POSTGRES_URL=postgresql://postgres.[project-id]:[password]@...

# 2. Supabase Dashboard → Database → Connection Pooling 활성화
# 3. Railway 환경변수 업데이트
# 4. Railway 재배포
```

### 9.5 PortOne 결제 실패

**증상**: "Payment failed" 또는 "Invalid Store ID"

**해결**:
```bash
# 1. PortOne Store ID 확인
NEXT_PUBLIC_PORTONE_STORE_ID=store-xxxxx

# 2. PortOne 콜백 URL 등록
https://roten.kr/api/portone/webhook

# 3. PG사 승인 확인
# PortOne Console → 상점 설정 → PG 설정
```

### 9.6 OAuth 로그인 실패

**증상**: "Redirect URI mismatch"

**해결**:

**Google**
```
Google Cloud Console → APIs & Services → Credentials
승인된 리디렉션 URI:
- https://roten.kr/api/auth/callback/google
- https://dev.roten.kr/api/auth/callback/google
```

**Kakao**
```
Kakao Developers → 내 애플리케이션 → Redirect URI
- https://roten.kr/api/auth/callback/kakao
- https://dev.roten.kr/api/auth/callback/kakao
```

**Naver**
```
Naver Developers → Application → 서비스 URL
- https://roten.kr
- Callback URL: https://roten.kr/api/auth/callback/naver
```

### 9.7 Health Check 실패

**증상**: Railway "Service Unhealthy"

**해결**:
```bash
# 1. Health check 엔드포인트 확인
curl https://api.roten.kr/health

# 2. app.py에 health check 추가
@app.get("/health")
async def health():
    return {"status": "healthy"}

# 3. Railway 설정 확인
Healthcheck Path: /health
Healthcheck Timeout: 100
```

### 9.8 SSL 인증서 문제

**증상**: "Your connection is not private" (ERR_CERT_COMMON_NAME_INVALID)

**해결**:
1. DNS 전파 확인 (24-48시간 대기)
2. Vercel/Railway에서 도메인 재등록
3. 브라우저 캐시 삭제 (Ctrl+Shift+Delete)
4. 5-10분 대기 후 재시도

---

## 참고 문서

- [Vercel 공식 문서](https://vercel.com/docs)
- [Railway 공식 문서](https://docs.railway.app/)
- [Next.js 배포 가이드](https://nextjs.org/docs/deployment)
- [FastAPI 배포 가이드](https://fastapi.tiangolo.com/deployment/)
- [Supabase 문서](https://supabase.com/docs)
- [PortOne 개발자 문서](https://developers.portone.io/)
- [프로젝트 배포 전략](./DEPLOYMENT_STRATEGY.md)
- [인프라 가이드](./PROJECT_DOCS/INFRASTRUCTURE_GUIDE.md)

---

## 지원

문제 발생 시:
1. 위 문제 해결 섹션 참고
2. Vercel/Railway 로그 확인
3. GitHub Issues 등록
4. 개발팀 슬랙 채널 문의

---

**작성일**: 2025-11-10
**버전**: 1.0.0
**작성자**: Claude Code SuperClaude
