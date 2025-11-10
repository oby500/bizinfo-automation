/**
 * 데이터베이스 마이그레이션 실행 스크립트
 * payments, credits, credit_transactions 테이블 생성
 */
const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

async function runMigration() {
  console.log('🚀 데이터베이스 마이그레이션 시작...\n');

  const migrationSQL = `
-- payments 테이블 생성
CREATE TABLE IF NOT EXISTS payments (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  payment_id VARCHAR(255) NOT NULL UNIQUE,
  order_name VARCHAR(255) NOT NULL,
  amount INTEGER NOT NULL,
  status VARCHAR(20) NOT NULL,
  payment_method VARCHAR(50),
  credit_amount INTEGER,
  bonus_amount INTEGER,
  total_credit INTEGER,
  paid_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- credits 테이블 생성
CREATE TABLE IF NOT EXISTS credits (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE,
  balance INTEGER DEFAULT 0 NOT NULL,
  total_charged INTEGER DEFAULT 0 NOT NULL,
  total_used INTEGER DEFAULT 0 NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- credit_transactions 테이블 생성
CREATE TABLE IF NOT EXISTS credit_transactions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  payment_id INTEGER,
  type VARCHAR(20) NOT NULL,
  amount INTEGER NOT NULL,
  balance INTEGER NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Foreign Key 제약조건 추가 (이미 있으면 무시)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'payments_user_id_users_id_fk'
  ) THEN
    ALTER TABLE payments ADD CONSTRAINT payments_user_id_users_id_fk
      FOREIGN KEY (user_id) REFERENCES users(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'credits_user_id_users_id_fk'
  ) THEN
    ALTER TABLE credits ADD CONSTRAINT credits_user_id_users_id_fk
      FOREIGN KEY (user_id) REFERENCES users(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'credit_transactions_user_id_users_id_fk'
  ) THEN
    ALTER TABLE credit_transactions ADD CONSTRAINT credit_transactions_user_id_users_id_fk
      FOREIGN KEY (user_id) REFERENCES users(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'credit_transactions_payment_id_payments_id_fk'
  ) THEN
    ALTER TABLE credit_transactions ADD CONSTRAINT credit_transactions_payment_id_payments_id_fk
      FOREIGN KEY (payment_id) REFERENCES payments(id);
  END IF;
END $$;
  `;

  try {
    // Supabase에는 직접 SQL 실행 기능이 없으므로 postgres 클라이언트를 사용해야 합니다
    // 대신 Drizzle ORM을 사용해서 테이블을 생성합니다
    console.log('✅ 마이그레이션 SQL 준비 완료');
    console.log('\n📝 다음 SQL을 Supabase Dashboard의 SQL Editor에서 실행하세요:\n');
    console.log(migrationSQL);
    console.log('\n💡 또는 drizzle-kit push를 사용하세요: pnpm drizzle-kit push');

  } catch (error) {
    console.error('❌ 마이그레이션 실패:', error);
    process.exit(1);
  }
}

runMigration();
