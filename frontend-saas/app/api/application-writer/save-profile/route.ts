import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';
import { db } from '@/lib/db/drizzle';
import { userProfiles } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

/**
 * Save Company Profile API
 *
 * 회사 프로필 데이터를 저장하거나 업데이트
 * - 첫 번째 저장 시: userProfiles에 새 레코드 생성
 * - 이후 업데이트: 기존 레코드 업데이트
 */

interface SaveProfileRequest {
  profile_data: {
    company_name?: string;
    business_registration_number?: string;
    business_field?: string;
    founding_year?: number;
    revenue?: string;
    employee_count?: number;
    main_products?: string;
    target_goal?: string;
    technology?: string;
    past_support?: string;
    additional_info?: string;
    [key: string]: any;
  };
}

export async function POST(request: NextRequest) {
  try {
    // 1. 인증 확인
    const session = await auth();
    if (!session || !session.user?.id) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const userId = parseInt(session.user.id);

    // 2. 요청 데이터 파싱
    const body: SaveProfileRequest = await request.json();
    const { profile_data } = body;

    if (!profile_data) {
      return NextResponse.json(
        { error: 'Missing profile_data' },
        { status: 400 }
      );
    }

    console.log('[Save Profile] Saving profile for user:', userId);

    // 3. 기존 프로필 확인
    const existingProfiles = await db
      .select()
      .from(userProfiles)
      .where(eq(userProfiles.userId, userId))
      .limit(1);

    const existingProfile = existingProfiles[0];

    // 4. 저장할 데이터 준비
    const profileData = {
      userId,
      companyName: profile_data.company_name || null,
      businessNumber: profile_data.business_registration_number || null,
      industry: profile_data.business_field || null,
      establishmentYear: profile_data.founding_year || null,
      annualRevenue: profile_data.revenue || null,
      employeeCount: profile_data.employee_count?.toString() || null,
      mainProducts: profile_data.main_products || null,
      targetGoal: profile_data.target_goal || null,
      technology: profile_data.technology || null,
      pastSupport: profile_data.past_support || null,
      additionalInfo: profile_data.additional_info || null,
      profileCompleted: true,
      lastUpdatedSource: 'application_writer',
      updatedAt: new Date(),
    };

    let savedProfile;

    // 5. 프로필 저장 또는 업데이트
    if (existingProfile) {
      // 기존 프로필 업데이트
      console.log('[Save Profile] Updating existing profile');

      const updated = await db
        .update(userProfiles)
        .set(profileData)
        .where(eq(userProfiles.userId, userId))
        .returning();

      savedProfile = updated[0];
    } else {
      // 새 프로필 생성
      console.log('[Save Profile] Creating new profile');

      const inserted = await db
        .insert(userProfiles)
        .values({
          ...profileData,
          createdAt: new Date(),
        })
        .returning();

      savedProfile = inserted[0];
    }

    console.log('[Save Profile] Profile saved successfully');

    return NextResponse.json({
      success: true,
      message: existingProfile ? 'Profile updated successfully' : 'Profile created successfully',
      profile: savedProfile,
    });

  } catch (error) {
    console.error('[Save Profile] Error:', error);
    return NextResponse.json(
      {
        error: 'Failed to save profile',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
