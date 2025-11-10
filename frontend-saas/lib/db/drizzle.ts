import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema';
import dotenv from 'dotenv';

dotenv.config();

// DB 연결을 더 안전하게 설정 (연결 실패 시에도 앱이 작동하도록)
const connectionString = process.env.POSTGRES_URL || 'postgres://localhost:5432/postgres';
export const client = postgres(connectionString, {
  connect_timeout: 5, // 5초 타임아웃
  idle_timeout: 20,
  max_lifetime: 60 * 30,
  // SSL 설정 추가
  ssl: 'require',
  // 연결 재시도 설정
  max: 1, // 최소 연결 풀 크기
});

export const db = drizzle(client, { schema });
