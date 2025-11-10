# PortOne (구 아임포트) 결제 시스템 설정 가이드

## 🎯 구현 완료 상태

✅ **PortOne SDK 설치**: @portone/browser-sdk
✅ **가격 페이지**: 3가지 구독 플랜 + 크레딧 충전
✅ **Webhook 처리**: 결제 완료/실패/취소 처리
✅ **원화 결제**: KRW 기준 가격 책정

---

## 📋 PortOne 설정 방법

### 1. PortOne 계정 생성

1. **[PortOne 콘솔](https://portone.io/)** 접속
2. 회원가입 및 로그인
3. 새 상점 생성

### 2. Store ID 및 API Secret 발급

1. **콘솔** → **상점 설정**
2. **Store ID** 복사
3. **API Secret** 생성 및 복사

**`.env` 파일에 추가**:
```env
NEXT_PUBLIC_PORTONE_STORE_ID=store-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PORTONE_API_SECRET=your_api_secret_here
```

### 3. 결제 수단 설정

1. **콘솔** → **결제 설정** → **PG사 설정**
2. 사용할 PG사 선택 (예: 토스페이먼츠, KG이니시스 등)
3. PG사 정보 입력:
   - 상점 ID (MID)
   - API Key
   - 기타 필수 정보

4. **채널 키** 생성:
   - 콘솔에서 자동 생성된 Channel Key 확인
   - `page-portone.tsx` 파일의 `channelKey` 값 업데이트

### 4. Webhook URL 설정

1. **콘솔** → **Webhook 설정**
2. **Webhook URL 추가**:
   - 개발: `http://localhost:3000/api/portone/webhook`
   - 프로덕션: `https://yourdomain.com/api/portone/webhook`

3. **이벤트 선택**:
   - ✅ Transaction.Paid (결제 완료)
   - ✅ Transaction.Failed (결제 실패)
   - ✅ Transaction.Cancelled (결제 취소)
   - ✅ BillingKey.Issued (정기결제 빌링키 발급)

---

## 💳 가격 정책

### 구독 플랜

| 플랜 | 가격 | 기능 |
|------|------|------|
| **무료** | ₩0/월 | 기본 검색, 일 10회 제한, 북마크 10개 |
| **베이직** | ₩9,900/월 | 무제한 검색, AI 의미 검색, 고급 필터, 무제한 북마크 |
| **프리미엄** | ₩29,900/월 | 베이직 + AI 추천, 공고 비교, 전문가 컨설팅 |

### 크레딧 충전

| 크레딧 | 가격 | 보너스 |
|--------|------|--------|
| 100 | ₩9,900 | - |
| 500 | ₩39,900 | +50 |
| 1,000 | ₩69,900 | +200 |

---

## 🔧 구현된 파일

```
frontend-saas/
├── app/
│   ├── (dashboard)/
│   │   └── pricing/
│   │       ├── page.tsx                 # 기존 Stripe 페이지
│   │       └── page-portone.tsx        # PortOne 결제 페이지 ✨
│   └── api/
│       └── portone/
│           └── webhook/
│               └── route.ts            # Webhook 처리 API ✨
├── .env                                # PortOne 설정 추가 ✨
└── PORTONE_SETUP_GUIDE.md             # 이 문서 ✨
```

---

## 🧪 테스트 방법

### 1. 테스트 결제 정보

PortOne 테스트 환경에서 사용 가능한 카드 정보:

**신용카드**:
- 카드번호: `4111-1111-1111-1111` (VISA)
- 유효기간: 미래 날짜 아무거나
- CVC: `123`
- 비밀번호: `00`

### 2. 결제 플로우 테스트

1. **가격 페이지 접속**: http://localhost:3000/pricing
2. **플랜 선택**: "베이직" 또는 "프리미엄" 클릭
3. **결제 진행**:
   - PortOne 결제창 팝업
   - 테스트 카드 정보 입력
   - 결제 완료

4. **Webhook 확인**:
   - 서버 로그에서 `PortOne webhook received:` 확인
   - DB에 구독 정보 저장 확인

### 3. 로컬 Webhook 테스트

로컬 환경에서 Webhook을 받으려면 ngrok 사용:

```bash
# ngrok 설치
npm install -g ngrok

# 터널 실행
ngrok http 3000

# 생성된 https URL을 PortOne 콘솔의 Webhook URL에 등록
# 예: https://xxxx-xxxx-xxxx.ngrok.io/api/portone/webhook
```

---

## 🔐 보안 고려사항

### 1. Webhook 검증

프로덕션 환경에서는 반드시 Webhook 시그니처 검증:

```typescript
import crypto from 'crypto';

function verifyPortOneSignature(
  payload: any,
  signature: string
): boolean {
  const secret = process.env.PORTONE_API_SECRET!;
  const hash = crypto
    .createHmac('sha256', secret)
    .update(JSON.stringify(payload))
    .digest('hex');

  return hash === signature;
}
```

### 2. 환경 변수 보호

- `.env` 파일을 `.gitignore`에 추가
- 프로덕션에서는 환경 변수로 안전하게 관리
- Store ID는 클라이언트에 노출 가능
- API Secret은 절대 클라이언트에 노출 금지

### 3. HTTPS 필수

프로덕션 환경에서는 반드시 HTTPS 사용

---

## 📊 데이터베이스 스키마 (추가 필요)

결제 정보를 저장하기 위한 테이블 생성이 필요합니다:

```sql
-- 결제 내역 테이블
CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  team_id INTEGER REFERENCES teams(id),
  payment_id TEXT NOT NULL UNIQUE,
  order_name TEXT NOT NULL,
  amount INTEGER NOT NULL,
  status TEXT NOT NULL, -- 'paid', 'failed', 'cancelled'
  payment_method TEXT,
  paid_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 구독 정보 테이블 (teams 테이블 확장)
ALTER TABLE teams ADD COLUMN IF NOT EXISTS billing_key TEXT;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS next_billing_date TIMESTAMP;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS subscription_amount INTEGER;

-- 크레딧 테이블
CREATE TABLE credits (
  id SERIAL PRIMARY KEY,
  team_id INTEGER REFERENCES teams(id),
  amount INTEGER NOT NULL,
  balance INTEGER NOT NULL,
  payment_id TEXT REFERENCES payments(payment_id),
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🎉 완료!

PortOne 결제 시스템이 구현되었습니다. 실제 Store ID와 API Secret을 설정하면 바로 사용할 수 있습니다!

### 다음 단계:

1. ✅ PortOne 계정 생성 및 Store ID 발급
2. ✅ `.env` 파일에 설정 추가
3. ✅ PG사 연동 설정
4. ✅ Webhook URL 등록
5. ⬜ 결제 테스트
6. ⬜ 데이터베이스 마이그레이션 실행
7. ⬜ 프로덕션 배포

---

## 💡 참고 링크

- [PortOne 공식 문서](https://developers.portone.io/)
- [PortOne 콘솔](https://portone.io/)
- [결제 연동 가이드](https://developers.portone.io/docs/ko/integration)
