import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db/drizzle';
import { users } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { setSession } from '@/lib/auth/session';

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const redirect = searchParams.get('redirect') || '/';

  if (code && state) {
    try {
      // 네이버 토큰 요청
      const tokenResponse = await fetch('https://nid.naver.com/oauth2.0/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: process.env.NEXT_PUBLIC_NAVER_CLIENT_ID!,
          client_secret: process.env.NAVER_CLIENT_SECRET!,
          redirect_uri: `${origin}/auth/callback/naver`,
          code: code,
          state: state,
        }),
      });

      const tokenData = await tokenResponse.json();

      if (tokenData.error) {
        console.error('Naver token error:', tokenData);
        return NextResponse.redirect(new URL('/sign-in?error=token_failed', origin));
      }

      // 네이버 사용자 정보 요청
      const userResponse = await fetch('https://openapi.naver.com/v1/nid/me', {
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
        },
      });

      const userData = await userResponse.json();
      console.log('Naver user data:', userData);

      if (userData.resultcode !== '00') {
        console.error('Naver user info error:', userData);
        return NextResponse.redirect(new URL('/sign-in?error=user_info_failed', origin));
      }

      // 네이버 ID를 이메일 형식으로 변환 (실제 이메일이 있으면 사용, 없으면 ID 사용)
      const naverEmail = userData.response.email || `naver_${userData.response.id}@naver.oauth`;
      const naverName = userData.response.name || userData.response.nickname || 'Naver User';

      // 데이터베이스에서 기존 사용자 확인 또는 생성
      let user = await db
        .select()
        .from(users)
        .where(eq(users.email, naverEmail))
        .limit(1);

      if (user.length === 0) {
        // 신규 사용자 생성
        const [newUser] = await db
          .insert(users)
          .values({
            email: naverEmail,
            name: naverName,
            role: 'member',
            passwordHash: null,
          })
          .returning();

        user = [newUser];
        console.log('New Naver user created:', newUser.id);
      } else {
        console.log('Existing Naver user found:', user[0].id);
      }

      // 세션 생성
      await setSession(user[0]);

      return NextResponse.redirect(new URL(redirect, origin));
    } catch (err) {
      console.error('Unexpected error during Naver OAuth callback:', err);
      return NextResponse.redirect(new URL('/sign-in?error=unexpected', origin));
    }
  }

  return NextResponse.redirect(new URL('/sign-in?error=no_code', origin));
}
