/**
 * 신청서 생성 세션 API
 *
 * POST /api/applications/sessions - 세션 생성
 * GET /api/applications/sessions - 세션 목록 조회
 */

import { NextRequest, NextResponse } from 'next/server';
import { getCurrentUser } from '@/lib/auth/get-user';
import {
  createApplicationSession,
  getUserApplicationSessions,
} from '@/lib/db/queries';
import type { NewApplicationSession } from '@/lib/db/schema';

/**
 * POST /api/applications/sessions
 * 신청서 생성 세션 저장
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

    // 2. 세션 데이터 준비
    const session: NewApplicationSession = {
      userId,
      announcementId: body.announcementId,
      announcementSource: body.announcementSource,
      tier: body.tier,
      totalApplications: body.totalApplications,
      totalCostKrw: body.totalCostKrw,
      totalTokens: body.totalTokens,
      styleRecommendation: body.styleRecommendation
        ? (typeof body.styleRecommendation === 'string'
          ? body.styleRecommendation
          : JSON.stringify(body.styleRecommendation))
        : null,
      selectedBaseStyles: body.selectedBaseStyles
        ? (typeof body.selectedBaseStyles === 'string'
          ? body.selectedBaseStyles
          : JSON.stringify(body.selectedBaseStyles))
        : null,
      selectedCombinationStyles: body.selectedCombinationStyles
        ? (typeof body.selectedCombinationStyles === 'string'
          ? body.selectedCombinationStyles
          : JSON.stringify(body.selectedCombinationStyles))
        : null,
      companyInfoSnapshot: body.companyInfoSnapshot
        ? (typeof body.companyInfoSnapshot === 'string'
          ? body.companyInfoSnapshot
          : JSON.stringify(body.companyInfoSnapshot))
        : null,
      status: body.status || 'completed',
      creditTransactionId: body.creditTransactionId,
    };

    // 3. 세션 생성
    const result = await createApplicationSession(session);

    console.log('[API] Created application session:', {
      userId,
      sessionId: result.id,
      tier: body.tier,
      totalApplications: body.totalApplications,
    });

    return NextResponse.json({
      success: true,
      id: result.id,
    });
  } catch (error) {
    console.error('[API] Error creating session:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to create session',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/applications/sessions
 * 사용자의 세션 목록 조회
 *
 * Query params:
 * - limit: number (default 20)
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
    const limit = parseInt(searchParams.get('limit') || '20');

    // 2. 세션 목록 조회
    const sessions = await getUserApplicationSessions(userId, limit);

    // 3. JSON 파싱
    const parsedSessions = sessions.map(session => ({
      ...session,
      styleRecommendation: session.styleRecommendation
        ? (typeof session.styleRecommendation === 'string'
          ? JSON.parse(session.styleRecommendation)
          : session.styleRecommendation)
        : null,
      selectedBaseStyles: session.selectedBaseStyles
        ? (typeof session.selectedBaseStyles === 'string'
          ? JSON.parse(session.selectedBaseStyles)
          : session.selectedBaseStyles)
        : null,
      selectedCombinationStyles: session.selectedCombinationStyles
        ? (typeof session.selectedCombinationStyles === 'string'
          ? JSON.parse(session.selectedCombinationStyles)
          : session.selectedCombinationStyles)
        : null,
      companyInfoSnapshot: session.companyInfoSnapshot
        ? (typeof session.companyInfoSnapshot === 'string'
          ? JSON.parse(session.companyInfoSnapshot)
          : session.companyInfoSnapshot)
        : null,
    }));

    return NextResponse.json({
      success: true,
      sessions: parsedSessions,
      total: parsedSessions.length,
    });
  } catch (error) {
    console.error('[API] Error fetching sessions:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch sessions',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
