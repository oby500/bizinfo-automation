/**
 * 개별 세션 API
 *
 * GET /api/applications/sessions/[sessionId] - 세션 상세 (관련 신청서 포함)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getCurrentUser } from '@/lib/auth/get-user';
import { getApplicationSessionWithApplications } from '@/lib/db/queries';

interface RouteParams {
  params: {
    sessionId: string;
  };
}

/**
 * GET /api/applications/sessions/[sessionId]
 * 세션 상세 조회 (관련 신청서 포함)
 */
export async function GET(request: NextRequest, { params }: RouteParams) {
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
    const sessionId = parseInt(params.sessionId);

    if (isNaN(sessionId)) {
      return NextResponse.json(
        { error: 'Invalid session ID' },
        { status: 400 }
      );
    }

    // 2. 세션 및 관련 신청서 조회
    const result = await getApplicationSessionWithApplications(sessionId, userId);

    if (!result) {
      return NextResponse.json(
        { error: 'Session not found' },
        { status: 404 }
      );
    }

    // 3. JSON 파싱
    const parsedSession = {
      ...result.session,
      styleRecommendation: result.session.styleRecommendation
        ? (typeof result.session.styleRecommendation === 'string'
          ? JSON.parse(result.session.styleRecommendation)
          : result.session.styleRecommendation)
        : null,
      selectedBaseStyles: result.session.selectedBaseStyles
        ? (typeof result.session.selectedBaseStyles === 'string'
          ? JSON.parse(result.session.selectedBaseStyles)
          : result.session.selectedBaseStyles)
        : null,
      selectedCombinationStyles: result.session.selectedCombinationStyles
        ? (typeof result.session.selectedCombinationStyles === 'string'
          ? JSON.parse(result.session.selectedCombinationStyles)
          : result.session.selectedCombinationStyles)
        : null,
      companyInfoSnapshot: result.session.companyInfoSnapshot
        ? (typeof result.session.companyInfoSnapshot === 'string'
          ? JSON.parse(result.session.companyInfoSnapshot)
          : result.session.companyInfoSnapshot)
        : null,
    };

    const parsedApplications = result.applications.map(app => ({
      ...app,
      content: typeof app.content === 'string'
        ? JSON.parse(app.content)
        : app.content,
      styleRecommendation: app.styleRecommendation
        ? (typeof app.styleRecommendation === 'string'
          ? JSON.parse(app.styleRecommendation)
          : app.styleRecommendation)
        : null,
      companyInfoSnapshot: app.companyInfoSnapshot
        ? (typeof app.companyInfoSnapshot === 'string'
          ? JSON.parse(app.companyInfoSnapshot)
          : app.companyInfoSnapshot)
        : null,
    }));

    return NextResponse.json({
      success: true,
      session: parsedSession,
      applications: parsedApplications,
    });
  } catch (error) {
    console.error('[API] Error fetching session:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch session',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
