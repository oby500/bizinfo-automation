import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function POST() {
  // 세션 쿠키 삭제
  (await cookies()).delete('session');

  return NextResponse.json({ success: true });
}
