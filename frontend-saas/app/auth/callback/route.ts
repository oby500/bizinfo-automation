import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db/drizzle';
import { users } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { setSession } from '@/lib/auth/session';

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const redirect = searchParams.get('redirect') || '/';

  if (code) {
    try {
      // 카카오 토큰 요청
      const tokenResponse = await fetch('https://kauth.kakao.com/oauth/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: process.env.NEXT_PUBLIC_KAKAO_CLIENT_ID!,
          redirect_uri: `${origin}/auth/callback`,
          code: code,
        }),
      });

      const tokenData = await tokenResponse.json();

      if (tokenData.error) {
        console.error('Kakao token error:', tokenData);
        return NextResponse.redirect(new URL('/sign-in?error=token_failed', origin));
      }

      // 카카오 사용자 정보 요청
      const userResponse = await fetch('https://kapi.kakao.com/v2/user/me', {
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
        },
      });

      const userData = await userResponse.json();
      console.log('Kakao user data:', userData);

      // 카카오 ID를 이메일 형식으로 변환 (실제 이메일이 없으므로)
      const kakaoEmail = `kakao_${userData.id}@kakao.oauth`;
      const kakaoName = userData.kakao_account?.profile?.nickname || 'Kakao User';

      // 데이터베이스에서 기존 사용자 확인 또는 생성
      let user = await db
        .select()
        .from(users)
        .where(eq(users.email, kakaoEmail))
        .limit(1);

      if (user.length === 0) {
        // 신규 사용자 생성
        const [newUser] = await db
          .insert(users)
          .values({
            email: kakaoEmail,
            name: kakaoName,
            role: 'member',
            passwordHash: null, // 소셜 로그인은 비밀번호 없음
          })
          .returning();

        user = [newUser];
        console.log('New Kakao user created:', newUser.id);
      } else {
        console.log('Existing Kakao user found:', user[0].id);
      }

      // 세션 생성
      await setSession(user[0]);

      return NextResponse.redirect(new URL(redirect, origin));
    } catch (err) {
      console.error('Unexpected error during OAuth callback:', err);
      return NextResponse.redirect(new URL('/sign-in?error=unexpected', origin));
    }
  }

  // No code parameter, redirect to sign-in
  return NextResponse.redirect(new URL('/sign-in?error=no_code', origin));
}
