#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 마이그레이션 실행 스크립트
payments, credits, credit_transactions 테이블 생성
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# .env에서 DATABASE_URL 파싱
database_url = os.getenv('POSTGRES_URL')

if not database_url:
    print("[ERROR] .env 파일에 POSTGRES_URL이 설정되지 않았습니다.")
    exit(1)

print("[START] 데이터베이스 마이그레이션 시작...\n")

migration_sql = """
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
"""

fk_sql = """
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
"""

try:
    # 데이터베이스 연결
    print("[CONNECT] 데이터베이스 연결 중...")
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # 테이블 생성
    print("[CREATE] 테이블 생성 중...")
    cursor.execute(migration_sql)
    conn.commit()
    print("[OK] 테이블 생성 완료: payments, credits, credit_transactions")

    # Foreign Key 추가
    print("[FK] Foreign Key 제약조건 추가 중...")
    cursor.execute(fk_sql)
    conn.commit()
    print("[OK] Foreign Key 제약조건 추가 완료")

    # 결과 확인
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('payments', 'credits', 'credit_transactions')
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()

    print("\n[SUCCESS] 마이그레이션 성공!\n")
    print("생성된 테이블:")
    for table in tables:
        print(f"  - {table[0]}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n[ERROR] 마이그레이션 실패: {e}")
    exit(1)
