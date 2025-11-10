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
      // 구글 토큰 요청
      const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!,
          client_secret: process.env.GOOGLE_CLIENT_SECRET!,
          redirect_uri: `${origin}/auth/callback/google`,
          code: code,
        }),
      });

      const tokenData = await tokenResponse.json();

      if (tokenData.error) {
        console.error('Google token error:', tokenData);
        return NextResponse.redirect(new URL('/sign-in?error=token_failed', origin));
      }

      // 구글 사용자 정보 요청
      const userResponse = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
        },
      });

      const userData = await userResponse.json();
      console.log('Google user data:', userData);

      // 구글은 항상 이메일 제공
      const googleEmail = userData.email;
      const googleName = userData.name || 'Google User';

      // 데이터베이스에서 기존 사용자 확인 또는 생성
      let user = await db
        .select()
        .from(users)
        .where(eq(users.email, googleEmail))
        .limit(1);

      if (user.length === 0) {
        // 신규 사용자 생성
        const [newUser] = await db
          .insert(users)
          .values({
            email: googleEmail,
            name: googleName,
            role: 'member',
            passwordHash: null,
          })
          .returning();

        user = [newUser];
        console.log('New Google user created:', newUser.id);
      } else {
        console.log('Existing Google user found:', user[0].id);
      }

      // 세션 생성
      await setSession(user[0]);

      return NextResponse.redirect(new URL(redirect, origin));
    } catch (err) {
      console.error('Unexpected error during Google OAuth callback:', err);
      return NextResponse.redirect(new URL('/sign-in?error=unexpected', origin));
    }
  }

  return NextResponse.redirect(new URL('/sign-in?error=no_code', origin));
}
