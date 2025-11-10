-- ================================================
-- Row Level Security (RLS) 정책
-- 목적: 사용자별 데이터 격리 (각 사용자는 자신의 데이터만 접근 가능)
-- 작성일: 2025-10-31
-- ================================================

-- ================================================================================
-- 1. PAYMENTS 테이블 RLS 정책
-- ================================================================================

-- RLS 활성화
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS "사용자는 자신의 결제내역만 조회 가능" ON payments;
DROP POLICY IF EXISTS "사용자는 자신의 결제내역만 생성 가능" ON payments;
DROP POLICY IF EXISTS "사용자는 자신의 결제내역만 수정 가능" ON payments;

-- SELECT 정책: 사용자는 자신의 결제 내역만 조회 가능
CREATE POLICY "사용자는 자신의 결제내역만 조회 가능"
ON payments FOR SELECT
USING (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- INSERT 정책: 사용자는 자신의 결제 내역만 생성 가능
CREATE POLICY "사용자는 자신의 결제내역만 생성 가능"
ON payments FOR INSERT
WITH CHECK (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- UPDATE 정책: 사용자는 자신의 결제 내역만 수정 가능
CREATE POLICY "사용자는 자신의 결제내역만 수정 가능"
ON payments FOR UPDATE
USING (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
))
WITH CHECK (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- ================================================================================
-- 2. CREDITS 테이블 RLS 정책
-- ================================================================================

-- RLS 활성화
ALTER TABLE credits ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS "사용자는 자신의 크레딧 잔액만 조회 가능" ON credits;
DROP POLICY IF EXISTS "사용자는 자신의 크레딧 잔액만 생성 가능" ON credits;
DROP POLICY IF EXISTS "사용자는 자신의 크레딧 잔액만 수정 가능" ON credits;

-- SELECT 정책
CREATE POLICY "사용자는 자신의 크레딧 잔액만 조회 가능"
ON credits FOR SELECT
USING (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- INSERT 정책
CREATE POLICY "사용자는 자신의 크레딧 잔액만 생성 가능"
ON credits FOR INSERT
WITH CHECK (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- UPDATE 정책
CREATE POLICY "사용자는 자신의 크레딧 잔액만 수정 가능"
ON credits FOR UPDATE
USING (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
))
WITH CHECK (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- ================================================================================
-- 3. CREDIT_TRANSACTIONS 테이블 RLS 정책
-- ================================================================================

-- RLS 활성화
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS "사용자는 자신의 크레딧 거래내역만 조회 가능" ON credit_transactions;
DROP POLICY IF EXISTS "사용자는 자신의 크레딧 거래내역만 생성 가능" ON credit_transactions;

-- SELECT 정책
CREATE POLICY "사용자는 자신의 크레딧 거래내역만 조회 가능"
ON credit_transactions FOR SELECT
USING (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- INSERT 정책
CREATE POLICY "사용자는 자신의 크레딧 거래내역만 생성 가능"
ON credit_transactions FOR INSERT
WITH CHECK (user_id = (
  SELECT id FROM users
  WHERE email = auth.jwt() ->> 'email'
));

-- ================================================================================
-- 4. USERS 테이블 RLS 정책
-- ================================================================================

-- RLS 활성화
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 기존 정책 삭제 (있다면)
DROP POLICY IF EXISTS "사용자는 자신의 정보만 조회 가능" ON users;
DROP POLICY IF EXISTS "사용자는 자신의 정보만 수정 가능" ON users;

-- SELECT 정책: 사용자는 자신의 정보만 조회 가능
CREATE POLICY "사용자는 자신의 정보만 조회 가능"
ON users FOR SELECT
USING (
  email = auth.jwt() ->> 'email'
);

-- UPDATE 정책: 사용자는 자신의 정보만 수정 가능
CREATE POLICY "사용자는 자신의 정보만 수정 가능"
ON users FOR UPDATE
USING (
  email = auth.jwt() ->> 'email'
)
WITH CHECK (
  email = auth.jwt() ->> 'email'
);

-- ================================================================================
-- 5. RLS 정책 확인 쿼리
-- ================================================================================

-- 모든 RLS 정책 조회
SELECT
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd,
  qual,
  with_check
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('payments', 'credits', 'credit_transactions', 'users')
ORDER BY tablename, policyname;

-- ================================================================================
-- 6. RLS 활성화 상태 확인
-- ================================================================================

SELECT
  schemaname,
  tablename,
  rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('payments', 'credits', 'credit_transactions', 'users')
ORDER BY tablename;

-- ================================================================================
-- 7. 테스트 쿼리 (선택사항)
-- ================================================================================

-- 현재 사용자 확인
-- SELECT auth.jwt() ->> 'email' AS current_user_email;

-- 현재 사용자의 결제 내역 조회 (RLS 적용 후)
-- SELECT * FROM payments;

-- 현재 사용자의 크레딧 잔액 조회 (RLS 적용 후)
-- SELECT * FROM credits;

-- 현재 사용자의 크레딧 거래 내역 조회 (RLS 적용 후)
-- SELECT * FROM credit_transactions;
