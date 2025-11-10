# 소셜 로그인 설정 가이드

이 프로젝트는 카카오, 네이버, 구글 소셜 로그인을 지원합니다.

## 🎯 구현 완료 상태

✅ **카카오 로그인**: 완료 (DB 저장 로직 포함)
✅ **네이버 로그인**: 완료 (커스텀 OAuth 구현)
✅ **구글 로그인**: 완료 (OAuth 2.0 구현)

---

## 📋 설정 방법

### 1. 카카오 로그인 설정

1. **[Kakao Developers](https://developers.kakao.com/)** 접속
2. 애플리케이션 생성
3. **앱 키** → REST API 키 복사
4. **플랫폼 설정** → Web 플랫폼 추가
   - 사이트 도메인: `http://localhost:3000` (개발), `https://yourdomain.com` (프로덕션)
5. **Redirect URI 등록**:
   - `http://localhost:3000/auth/callback/kakao`
   - `https://yourdomain.com/auth/callback/kakao`
6. **동의 항목 설정**:
   - 닉네임: 필수
   - 프로필 이미지: 선택

**`.env` 파일에 추가**:
```env
NEXT_PUBLIC_KAKAO_CLIENT_ID=your_kakao_rest_api_key
```

---

### 2. 네이버 로그인 설정

1. **[네이버 개발자 센터](https://developers.naver.com/main/)** 접속
2. **애플리케이션 등록** → 애플리케이션 이름 입력
3. **사용 API**: 네이버 로그인 선택
4. **서비스 환경**:
   - PC 웹: `http://localhost:3000` (개발), `https://yourdomain.com` (프로덕션)
5. **Callback URL 등록**:
   - `http://localhost:3000/auth/callback/naver`
   - `https://yourdomain.com/auth/callback/naver`
6. **제공 정보 설정**:
   - 회원 이름
   - 이메일 주소
   - 별명 (선택)

**`.env` 파일에 추가**:
```env
NEXT_PUBLIC_NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
```

---

### 3. 구글 로그인 설정

1. **[Google Cloud Console](https://console.cloud.google.com/)** 접속
2. 프로젝트 생성 또는 선택
3. **APIs & Services** → **Credentials**
4. **Create Credentials** → **OAuth client ID**
5. **Application type**: Web application
6. **Authorized redirect URIs**:
   - `http://localhost:3000/auth/callback/google`
   - `https://yourdomain.com/auth/callback/google`
7. Client ID와 Client Secret 복사

**`.env` 파일에 추가**:
```env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

---

## 🗄️ 데이터베이스 설정

소셜 로그인 사용자는 비밀번호 없이 가입됩니다. 스키마가 이미 업데이트되어 `passwordHash` 필드가 optional입니다.

### 마이그레이션 실행 (필요시)

```bash
cd frontend-saas
pnpm db:migrate
```

---

## 🧪 테스트 방법

1. **서버 실행**:
```bash
# 백엔드 (포트 8000)
cd frontend
python app.py

# 프론트엔드 (포트 3000)
cd frontend-saas
pnpm dev
```

2. **로그인 페이지 접속**:
   - http://localhost:3000/sign-in
   - http://localhost:3000/sign-up

3. **소셜 로그인 버튼 클릭**:
   - 🟡 카카오로 3초만에 시작하기
   - 🟢 네이버로 시작하기
   - 🔵 구글로 시작하기

---

## 📁 구현된 파일 구조

```
frontend-saas/
├── app/
│   ├── (login)/
│   │   └── login.tsx                    # 소셜 로그인 버튼 UI
│   └── auth/
│       └── callback/
│           ├── kakao/route.ts           # 카카오 OAuth 콜백
│           ├── naver/route.ts           # 네이버 OAuth 콜백
│           └── google/route.ts          # 구글 OAuth 콜백
├── lib/
│   └── db/
│       └── schema.ts                    # passwordHash optional로 수정
└── .env                                 # 환경 변수 설정
```

---

## 🔐 보안 고려사항

1. **Client Secret 보안**:
   - `.env` 파일을 `.gitignore`에 추가
   - 프로덕션에서는 환경 변수로 관리

2. **HTTPS 필수**:
   - 프로덕션 환경에서는 반드시 HTTPS 사용

3. **CSRF 방어**:
   - 네이버 로그인에 `state` 파라미터 사용

4. **Redirect URI 검증**:
   - 각 플랫폼에서 정확한 Redirect URI 등록

---

## ⚠️ 주의사항

1. **카카오**: REST API 키를 사용하며, JavaScript 키가 아님
2. **네이버**: Client Secret이 필요하므로 서버 측에서만 사용
3. **구글**: OAuth 2.0 Client ID 사용 (API 키가 아님)

---

## 🎉 완료!

모든 소셜 로그인이 정상적으로 구현되었습니다. 실제 Client ID와 Secret을 `.env` 파일에 입력하면 바로 사용할 수 있습니다!
