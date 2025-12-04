/**
 * 생성된 신청서 API
 *
 * POST /api/applications - 신청서 저장
 * GET /api/applications - 사용자의 신청서 목록 조회
 */

import { NextRequest, NextResponse } from 'next/server';
import { getCurrentUser } from '@/lib/auth/get-user';
import {
  saveGeneratedApplication,
  saveGeneratedApplicationsBatch,
  getUserGeneratedApplications,
  getUserApplicationsForAnnouncement,
} from '@/lib/db/queries';
import type { NewGeneratedApplication } from '@/lib/db/schema';

/**
 * POST /api/applications
 * 생성된 신청서 저장 (단일 또는 배치)
 */
export async function POST(request: NextRequest) {
  try {
    // 1. 사용자 인증 확인
    const user = await getCurrentUser();
    if (!user || !user.id) {
      return NextResponse.json(
        { error: 'Unauthorized: Please login first' },
        { status: 401 }
      );
    }

    const userId = parseInt(user.id);
    const body = await request.json();

    // 2. 단일 저장 vs 배치 저장 판단
    const isBatch = Array.isArray(body.applications);

    if (isBatch) {
      // 배치 저장
      const applications: NewGeneratedApplication[] = body.applications.map(
        (app: Partial<NewGeneratedApplication>) => ({
          ...app,
          userId,
          content: typeof app.content === 'string' ? app.content : JSON.stringify(app.content),
          styleRecommendation: app.styleRecommendation
            ? (typeof app.styleRecommendation === 'string' ? app.styleRecommendation : JSON.stringify(app.styleRecommendation))
            : null,
          companyInfoSnapshot: app.companyInfoSnapshot
            ? (typeof app.companyInfoSnapshot === 'string' ? app.companyInfoSnapshot : JSON.stringify(app.companyInfoSnapshot))
            : null,
        })
      );

      const result = await saveGeneratedApplicationsBatch(applications);

      console.log('[API] Batch saved applications:', {
        userId,
        count: result.ids.length,
        ids: result.ids,
      });

      return NextResponse.json({
        success: true,
        ids: result.ids,
        count: result.ids.length,
      });
    } else {
      // 단일 저장
      const application: NewGeneratedApplication = {
        userId,
        announcementId: body.announcementId,
        announcementSource: body.announcementSource,
        announcementTitle: body.announcementTitle,
        tier: body.tier,
        style: body.style,
        styleName: body.styleName,
        styleType: body.styleType,
        styleRank: body.styleRank,
        isRecommended: body.isRecommended || false,
        content: typeof body.content === 'string' ? body.content : JSON.stringify(body.content),
        charCount: body.charCount,
        sectionCount: body.sectionCount,
        inputTokens: body.inputTokens,
        outputTokens: body.outputTokens,
        costKrw: body.costKrw,
        modelUsed: body.modelUsed,
        styleRecommendation: body.styleRecommendation
          ? (typeof body.styleRecommendation === 'string' ? body.styleRecommendation : JSON.stringify(body.styleRecommendation))
          : null,
        companyInfoSnapshot: body.companyInfoSnapshot
          ? (typeof body.companyInfoSnapshot === 'string' ? body.companyInfoSnapshot : JSON.stringify(body.companyInfoSnapshot))
          : null,
        status: body.status || 'generated',
        creditTransactionId: body.creditTransactionId,
      };

      const result = await saveGeneratedApplication(application);

      console.log('[API] Saved application:', {
        userId,
        id: result.id,
        style: body.style,
        announcementId: body.announcementId,
      });

      return NextResponse.json({
        success: true,
        id: result.id,
      });
    }
  } catch (error) {
    console.error('[API] Error saving application:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to save application',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/applications
 * 사용자의 생성된 신청서 목록 조회
 *
 * Query params:
 * - limit: number (default 50)
 * - announcementId: string (optional, filter by announcement)
 * - announcementSource: string (required if announcementId is provided)
 */
export async function GET(request: NextRequest) {
  try {
    // 1. 사용자 인증 확인
    const user = await getCurrentUser();
    if (!user || !user.id) {
      return NextResponse.json(
        { error: 'Unauthorized: Please login first' },
        { status: 401 }
      );
    }

    const userId = parseInt(user.id);
    const { searchParams } = new URL(request.url);

    const limit = parseInt(searchParams.get('limit') || '50');
    const announcementId = searchParams.get('announcementId');
    const announcementSource = searchParams.get('announcementSource');

    let applications;

    if (announcementId && announcementSource) {
      // 특정 공고에 대한 신청서 조회
      applications = await getUserApplicationsForAnnouncement(
        userId,
        announcementId,
        announcementSource
      );
    } else {
      // 전체 신청서 목록 조회
      applications = await getUserGeneratedApplications(userId, limit);
    }

    // content를 JSON 파싱
    const parsedApplications = applications.map(app => ({
      ...app,
      content: typeof app.content === 'string' ? JSON.parse(app.content) : app.content,
      styleRecommendation: app.styleRecommendation
        ? (typeof app.styleRecommendation === 'string' ? JSON.parse(app.styleRecommendation) : app.styleRecommendation)
        : null,
      companyInfoSnapshot: app.companyInfoSnapshot
        ? (typeof app.companyInfoSnapshot === 'string' ? JSON.parse(app.companyInfoSnapshot) : app.companyInfoSnapshot)
        : null,
    }));

    return NextResponse.json({
      success: true,
      applications: parsedApplications,
      total: parsedApplications.length,
    });
  } catch (error) {
    console.error('[API] Error fetching applications:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch applications',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
