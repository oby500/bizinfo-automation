# 구글 로그인 설정 가이드

## 🔧 Google Cloud Console 설정

### 1. Google Cloud Console 접속
👉 https://console.cloud.google.com/

### 2. 프로젝트 생성

1. **새 프로젝트 만들기** 클릭
2. **프로젝트 이름**: 정부지원사업 검색 (또는 원하는 이름)
3. **조직**: 선택 사항
4. **만들기** 클릭

### 3. OAuth 동의 화면 구성

1. 좌측 메뉴 → **APIs & Services** → **OAuth consent screen**
2. **User Type** 선택:
   - **External** 선택 (일반 사용자용)
   - **CREATE** 클릭

#### 앱 정보 입력

**필수 항목**:
- **App name**: 정부지원사업 검색
- **User support email**: 본인 이메일
- **Developer contact information**: 본인 이메일

**선택 항목**:
- **App logo**: 서비스 로고 (선택)
- **App domain**: 나중에 프로덕션 도메인 추가
- **Authorized domains**: yourdomain.com (프로덕션 도메인)

3. **SAVE AND CONTINUE** 클릭

#### Scopes (범위) 설정

1. **ADD OR REMOVE SCOPES** 클릭
2. 필수 범위 선택:
   - ✅ `.../auth/userinfo.email`
   - ✅ `.../auth/userinfo.profile`
   - ✅ `openid`
3. **UPDATE** → **SAVE AND CONTINUE**

#### Test users (테스트 단계)

개발 중에는 테스트 사용자 추가 필요:
1. **ADD USERS** 클릭
2. 테스트할 구글 계정 이메일 입력
3. **ADD** → **SAVE AND CONTINUE**

### 4. OAuth 2.0 Client ID 생성

1. 좌측 메뉴 → **APIs & Services** → **Credentials**
2. **+ CREATE CREDENTIALS** → **OAuth client ID** 선택
3. **Application type**: **Web application**
4. **Name**: Web Client (또는 원하는 이름)

#### Authorized redirect URIs 설정

**개발 환경**:
```
http://localhost:3000/auth/callback/google
```

**프로덕션 환경** (나중에 추가):
```
https://yourdomain.com/auth/callback/google
```

5. **CREATE** 클릭

### 5. Client ID 및 Client Secret 확인

생성 완료 후 팝업에서:
- **Client ID** 복사
- **Client secret** 복사

또는 Credentials 페이지에서 생성한 OAuth 2.0 Client 클릭하여 확인 가능

### 6. .env 파일 업데이트

```env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_actual_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_actual_client_secret
```

**중요**:
- Client ID는 클라이언트 측에서 사용
- Client Secret은 서버 측에서만 사용 (절대 노출 금지!)

---

## ⚠️ 주의사항

### 1. OAuth 동의 화면 상태

개발 중에는 **Testing** 상태:
- 테스트 사용자만 로그인 가능
- 최대 100명까지 테스트 사용자 추가 가능

프로덕션 배포 시 **Publishing** 필요:
- 구글 검토 필요 (7-14일 소요)
- 모든 구글 사용자 로그인 가능

### 2. Redirect URI 정확히 입력
- 반드시 `/auth/callback/google` 경로로 끝나야 함
- 포트 번호까지 정확히 일치해야 함
- HTTPS 권장 (localhost는 HTTP 허용)

### 3. API 활성화
Google People API가 자동으로 활성화되지만, 필요시 수동 활성화:
1. **APIs & Services** → **Library**
2. "Google People API" 검색
3. **ENABLE** 클릭

---

## 🧪 테스트 방법

### 1. 서버 재시작
.env 파일 수정 후 Next.js 서버 재시작:
```bash
# 현재 서버 종료 (Ctrl+C)
pnpm dev
```

### 2. 로그인 테스트

#### 테스트 사용자로 로그인
1. http://localhost:3000/sign-in 접속
2. **"구글로 시작하기"** 버튼 클릭
3. 구글 로그인 페이지로 이동
4. **테스트 사용자 계정**으로 로그인
5. 권한 동의 화면에서 **허용** 클릭
6. 자동으로 서비스로 리다이렉트

#### 일반 사용자로 로그인 시도 (Testing 상태)
- "Access blocked" 에러 발생
- 테스트 사용자로만 로그인 가능

### 3. DB 확인
```sql
SELECT * FROM users WHERE email LIKE '%@gmail.com';
```

---

## 🔍 문제 해결

### Error: redirect_uri_mismatch
- **원인**: Redirect URI가 Google Cloud Console에 등록된 URI와 다름
- **해결**:
  1. Google Cloud Console → Credentials
  2. OAuth 2.0 Client 클릭
  3. Authorized redirect URIs 확인 및 수정
  4. 정확한 URI 형식: `http://localhost:3000/auth/callback/google`

### Error: invalid_client
- **원인**: Client ID 또는 Client Secret이 잘못됨
- **해결**:
  1. .env 파일의 값 확인
  2. 공백이나 개행 문자 제거
  3. Client ID는 `.apps.googleusercontent.com`으로 끝나야 함

### Error: Access blocked (Testing mode)
- **원인**: OAuth 동의 화면이 Testing 상태이고 테스트 사용자가 아님
- **해결**:
  1. Google Cloud Console → OAuth consent screen
  2. Test users에 사용자 추가
  3. 또는 Publishing 상태로 변경 (구글 검토 필요)

### Error: invalid_grant
- **원인**: Authorization code가 만료되었거나 이미 사용됨
- **해결**: 다시 로그인 시도

---

## 📊 OAuth 동의 화면 상태 비교

| 항목 | Testing | In production |
|------|---------|---------------|
| 사용자 제한 | 테스트 사용자만 (최대 100명) | 모든 구글 사용자 |
| 구글 검토 | 불필요 | 필수 (7-14일) |
| 사용 기한 | 무제한 | 무제한 |
| Refresh token | 7일마다 만료 | 만료 없음 |

---

## 🚀 프로덕션 배포 준비

### 1. OAuth 동의 화면 Publishing

1. **OAuth consent screen** → **PUBLISH APP** 클릭
2. 구글 검토 제출:
   - 앱 설명
   - 스크린샷
   - 개인정보 처리방침 URL
   - 서비스 약관 URL
3. 검토 승인 대기 (7-14일)

### 2. Redirect URI 추가

프로덕션 도메인 추가:
```
https://yourdomain.com/auth/callback/google
```

### 3. Authorized domains 추가

OAuth 동의 화면에서:
- **Authorized domains**에 실제 도메인 추가
- 예: `yourdomain.com`

---

## ✅ 체크리스트

설정 완료 후 확인:
- [ ] Google Cloud 프로젝트 생성
- [ ] OAuth 동의 화면 구성 (Testing)
- [ ] OAuth 2.0 Client ID 생성
- [ ] Client ID, Client Secret 발급
- [ ] .env 파일에 두 값 입력
- [ ] Redirect URI 정확히 설정
- [ ] 테스트 사용자 추가
- [ ] 서버 재시작
- [ ] 테스트 사용자로 로그인 성공
- [ ] DB에 사용자 정보 저장 확인

---

## 🎉 완료!

구글 간편 로그인 설정이 완료되었습니다!

**프로덕션 배포 전 필수**:
1. OAuth 동의 화면 Publishing 신청
2. 실제 도메인 Redirect URI 추가
3. 개인정보 처리방침 및 서비스 약관 페이지 작성
