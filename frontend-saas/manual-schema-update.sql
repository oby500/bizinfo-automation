-- 2025-10-31: 인증 시스템 스키마 업데이트
-- 목적: password_hash 컬럼 추가 및 unique constraint 추가

-- 1. users 테이블에 password_hash 컬럼 추가 (이미 있으면 무시)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- 2. payments 테이블에 payment_id unique constraint 추가
-- 기존 데이터가 있으므로 먼저 중복 확인
DO $$
BEGIN
  -- unique constraint가 이미 존재하는지 확인
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'payments_payment_id_unique'
  ) THEN
    -- 중복 payment_id가 있는지 확인
    IF NOT EXISTS (
      SELECT payment_id FROM payments
      GROUP BY payment_id
      HAVING COUNT(*) > 1
    ) THEN
      -- 중복이 없으면 unique constraint 추가
      ALTER TABLE payments
      ADD CONSTRAINT payments_payment_id_unique UNIQUE (payment_id);
    ELSE
      RAISE NOTICE '중복된 payment_id가 존재합니다. 먼저 중복을 제거해주세요.';
    END IF;
  END IF;
END $$;

-- 3. 현재 테이블 구조 확인 (선택사항)
SELECT
  table_name,
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name IN ('users', 'payments', 'credits', 'credit_transactions')
ORDER BY table_name, ordinal_position;
