# 네이버 로그인 설정 가이드

## 🔧 네이버 개발자 센터 설정

### 1. 네이버 개발자 센터 접속
👉 https://developers.naver.com/main/

### 2. 로그인 및 애플리케이션 등록

1. **네이버 계정으로 로그인**
2. **상단 메뉴** → **Application** → **애플리케이션 등록** 클릭

### 3. 애플리케이션 정보 입력

#### 기본 정보
- **애플리케이션 이름**: 정부지원사업 검색 (또는 원하는 서비스명)
- **사용 API**:
  - ✅ **네이버 로그인** 체크

#### 제공 정보 선택
필수로 선택해야 할 항목:
- ✅ **회원이름**
- ✅ **이메일 주소**
- ✅ **별명** (선택)
- ✅ **프로필 이미지** (선택)

#### 서비스 환경 설정

**개발 환경 (localhost)**:
- 서비스 URL: `http://localhost:3000`
- Callback URL: `http://localhost:3000/auth/callback/naver`

**프로덕션 환경** (나중에 추가):
- 서비스 URL: `https://yourdomain.com`
- Callback URL: `https://yourdomain.com/auth/callback/naver`

### 4. Client ID 및 Client Secret 확인

애플리케이션 등록 후:

1. **내 애플리케이션** 페이지에서 등록한 앱 선택
2. **Client ID** 복사
3. **Client Secret** 복사

### 5. .env 파일 업데이트

```env
NEXT_PUBLIC_NAVER_CLIENT_ID=your_actual_client_id_here
NAVER_CLIENT_SECRET=your_actual_client_secret_here
```

**중요**:
- `Client ID`는 `NEXT_PUBLIC_` 접두사가 있어 클라이언트에서 사용
- `Client Secret`은 서버 측에서만 사용 (절대 노출 금지!)

---

## ⚠️ 주의사항

### 1. Callback URL 정확히 입력
- 반드시 `/auth/callback/naver` 경로로 끝나야 함
- 포트 번호까지 정확히 일치해야 함 (예: `http://localhost:3000`)

### 2. 제공 정보 동의
- 회원이름, 이메일은 필수 항목
- 사용자가 로그인 시 동의해야 정보 제공 가능

### 3. 도메인 검증
- 프로덕션 배포 시 실제 도메인 추가 필요
- HTTP는 localhost만 허용, 프로덕션은 반드시 HTTPS

---

## 🧪 테스트 방법

### 1. 서버 재시작
.env 파일 수정 후 Next.js 서버 재시작 필요:
```bash
# 현재 서버 종료 (Ctrl+C)
# 다시 시작
pnpm dev
```

### 2. 로그인 테스트
1. http://localhost:3000/sign-in 접속
2. **"네이버로 시작하기"** 버튼 클릭
3. 네이버 로그인 페이지로 이동
4. 네이버 계정으로 로그인
5. 정보 제공 동의
6. 자동으로 서비스 홈으로 리다이렉트

### 3. DB 확인
사용자 정보가 `users` 테이블에 저장되었는지 확인:
```sql
SELECT * FROM users WHERE email LIKE 'naver_%@naver.oauth';
-- 또는 실제 네이버 이메일로 저장된 경우
SELECT * FROM users WHERE email LIKE '%@naver.com';
```

---

## 🔍 문제 해결

### Error: redirect_uri_mismatch
- **원인**: Callback URL이 네이버 개발자 센터에 등록된 URL과 다름
- **해결**: 네이버 개발자 센터에서 정확한 URL 확인 및 수정

### Error: invalid_client
- **원인**: Client ID 또는 Client Secret이 잘못됨
- **해결**: .env 파일의 값 확인, 공백 제거

### 로그인 후 에러 페이지
- **원인**: 서버 측 에러 (DB 연결, 세션 생성 등)
- **해결**:
  1. 서버 콘솔 로그 확인
  2. Supabase 연결 확인
  3. `users` 테이블 존재 확인

---

## 📸 스크린샷 가이드

### 1. 애플리케이션 등록 화면
- 애플리케이션 이름 입력
- 사용 API: 네이버 로그인 체크
- 제공 정보: 회원이름, 이메일 체크

### 2. 서비스 환경 설정
- 서비스 URL: `http://localhost:3000`
- Callback URL: `http://localhost:3000/auth/callback/naver`

### 3. 등록 완료 후
- Client ID 확인 (공개 가능)
- Client Secret 확인 (비밀 유지!)

---

## ✅ 체크리스트

설정 완료 후 확인:
- [ ] 네이버 개발자 센터에 애플리케이션 등록 완료
- [ ] Client ID, Client Secret 발급 완료
- [ ] .env 파일에 두 값 모두 입력
- [ ] Callback URL이 정확히 일치
- [ ] 서버 재시작
- [ ] 로그인 테스트 성공
- [ ] DB에 사용자 정보 저장 확인

---

## 🎉 완료!

네이버 간편 로그인 설정이 완료되었습니다!
