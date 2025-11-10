#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테스트 사용자 생성 스크립트
userId=1인 테스트 사용자를 users 테이블에 추가
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv('POSTGRES_URL')

if not database_url:
    print("[ERROR] .env 파일에 POSTGRES_URL이 설정되지 않았습니다.")
    exit(1)

print("[START] 테스트 사용자 생성 시작...\n")

try:
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # users 테이블이 있는지 확인
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'users';
    """)

    if not cursor.fetchone():
        print("[INFO] users 테이블이 없습니다. 생성합니다...")
        cursor.execute("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW() NOT NULL
            );
        """)
        conn.commit()
        print("[OK] users 테이블 생성 완료")

    # userId=1인 사용자가 있는지 확인
    cursor.execute("SELECT id, email FROM users WHERE id = 1;")
    existing_user = cursor.fetchone()

    if existing_user:
        print(f"[INFO] userId=1 사용자가 이미 존재합니다: {existing_user[1]}")
    else:
        # 테스트 사용자 삽입
        cursor.execute("""
            INSERT INTO users (id, email, name)
            VALUES (1, 'test@example.com', '테스트 사용자')
            ON CONFLICT (id) DO NOTHING;
        """)
        conn.commit()
        print("[OK] 테스트 사용자 생성 완료 (userId=1)")

    # 확인
    cursor.execute("SELECT id, email, name FROM users WHERE id = 1;")
    user = cursor.fetchone()
    print(f"\n[SUCCESS] 테스트 사용자 정보:")
    print(f"  - ID: {user[0]}")
    print(f"  - Email: {user[1]}")
    print(f"  - Name: {user[2]}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n[ERROR] 테스트 사용자 생성 실패: {e}")
    exit(1)
