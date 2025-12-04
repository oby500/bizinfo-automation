import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';
import { db } from '@/lib/db/drizzle';
import { userProfiles } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

/**
 * Get Company Profile API
 *
 * 저장된 회사 프로필 조회
 * - 사용자의 저장된 회사 정보 반환
 * - 프로필이 없으면 null 반환
 */

export async function GET(request: NextRequest) {
  try {
    // 🔍 DEBUG: Request headers and cookies
    console.log('[Get Profile] ==================== REQUEST DEBUG ====================');
    console.log('[Get Profile] Request URL:', request.url);
    console.log('[Get Profile] Request Headers:', Object.fromEntries(request.headers));
    console.log('[Get Profile] Cookies:', request.cookies.getAll());

    // 1. 인증 확인
    const session = await auth();

    // 🔍 DEBUG: Session details
    console.log('[Get Profile] ==================== SESSION DEBUG ====================');
    console.log('[Get Profile] Session object:', JSON.stringify(session, null, 2));
    console.log('[Get Profile] Session exists:', !!session);
    console.log('[Get Profile] Session.user:', session?.user);
    console.log('[Get Profile] Session.user.id:', session?.user?.id);
    console.log('[Get Profile] ================================================================');

    if (!session || !session.user?.id) {
      console.log('[Get Profile] ❌ AUTHENTICATION FAILED - Returning 401');
      console.log('[Get Profile] Reason:', !session ? 'No session' : 'No user.id in session');
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const userId = parseInt(session.user.id);

    console.log('[Get Profile] Fetching profile for user:', userId);

    // 2. 프로필 조회
    const profiles = await db
      .select()
      .from(userProfiles)
      .where(eq(userProfiles.userId, userId))
      .limit(1);

    const profile = profiles[0];

    if (!profile) {
      console.log('[Get Profile] No profile found');
      return NextResponse.json({
        success: true,
        has_profile: false,
        profile: null,
      });
    }

    // 3. ApplicationWriter 형식으로 변환
    const profileData = {
      company_name: profile.companyName,
      business_registration_number: profile.businessNumber,
      business_field: profile.industry,
      founding_year: profile.establishmentYear,
      revenue: profile.annualRevenue,
      employee_count: profile.employeeCount ? parseInt(profile.employeeCount) : undefined,
      main_products: profile.mainProducts,
      target_goal: profile.targetGoal,
      technology: profile.technology,
      past_support: profile.pastSupport,
      additional_info: profile.additionalInfo,
    };

    console.log('[Get Profile] Profile found and formatted');

    return NextResponse.json({
      success: true,
      has_profile: true,
      profile: profileData,
      last_updated: profile.updatedAt,
    });

  } catch (error) {
    console.error('[Get Profile] Error:', error);
    return NextResponse.json(
      {
        error: 'Failed to get profile',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
