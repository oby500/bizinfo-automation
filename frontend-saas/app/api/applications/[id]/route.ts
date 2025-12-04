/**
 * 개별 신청서 API
 *
 * GET /api/applications/[id] - 신청서 상세 조회
 * PATCH /api/applications/[id] - 상태 또는 피드백 업데이트
 */

import { NextRequest, NextResponse } from 'next/server';
import { getCurrentUser } from '@/lib/auth/get-user';
import {
  getGeneratedApplicationById,
  updateApplicationStatus,
  updateApplicationFeedback,
} from '@/lib/db/queries';

interface RouteParams {
  params: {
    id: string;
  };
}

/**
 * GET /api/applications/[id]
 * 신청서 상세 조회
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
    const applicationId = parseInt(params.id);

    if (isNaN(applicationId)) {
      return NextResponse.json(
        { error: 'Invalid application ID' },
        { status: 400 }
      );
    }

    // 2. 신청서 조회
    const application = await getGeneratedApplicationById(applicationId);

    if (!application) {
      return NextResponse.json(
        { error: 'Application not found' },
        { status: 404 }
      );
    }

    // 3. 권한 확인 (본인 소유인지)
    if (application.userId !== userId) {
      return NextResponse.json(
        { error: 'Forbidden: You do not have access to this application' },
        { status: 403 }
      );
    }

    // 4. content JSON 파싱
    const parsedApplication = {
      ...application,
      content: typeof application.content === 'string'
        ? JSON.parse(application.content)
        : application.content,
      styleRecommendation: application.styleRecommendation
        ? (typeof application.styleRecommendation === 'string'
          ? JSON.parse(application.styleRecommendation)
          : application.styleRecommendation)
        : null,
      companyInfoSnapshot: application.companyInfoSnapshot
        ? (typeof application.companyInfoSnapshot === 'string'
          ? JSON.parse(application.companyInfoSnapshot)
          : application.companyInfoSnapshot)
        : null,
    };

    return NextResponse.json({
      success: true,
      application: parsedApplication,
    });
  } catch (error) {
    console.error('[API] Error fetching application:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch application',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * PATCH /api/applications/[id]
 * 신청서 상태 또는 피드백 업데이트
 *
 * Body:
 * - status?: string ('generated', 'downloaded', 'submitted', 'archived')
 * - rating?: number (1-5)
 * - feedback?: string
 */
export async function PATCH(request: NextRequest, { params }: RouteParams) {
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
    const applicationId = parseInt(params.id);

    if (isNaN(applicationId)) {
      return NextResponse.json(
        { error: 'Invalid application ID' },
        { status: 400 }
      );
    }

    // 2. 신청서 존재 및 권한 확인
    const application = await getGeneratedApplicationById(applicationId);

    if (!application) {
      return NextResponse.json(
        { error: 'Application not found' },
        { status: 404 }
      );
    }

    if (application.userId !== userId) {
      return NextResponse.json(
        { error: 'Forbidden: You do not have access to this application' },
        { status: 403 }
      );
    }

    // 3. 업데이트 실행
    const body = await request.json();
    const { status, rating, feedback } = body;

    // 상태 업데이트
    if (status) {
      const validStatuses = ['generated', 'downloaded', 'submitted', 'archived'];
      if (!validStatuses.includes(status)) {
        return NextResponse.json(
          { error: `Invalid status. Must be one of: ${validStatuses.join(', ')}` },
          { status: 400 }
        );
      }
      await updateApplicationStatus(applicationId, status);
      console.log('[API] Updated application status:', { applicationId, status });
    }

    // 피드백 업데이트
    if (rating !== undefined || feedback !== undefined) {
      const feedbackData: { rating?: number; feedback?: string } = {};

      if (rating !== undefined) {
        if (rating < 1 || rating > 5) {
          return NextResponse.json(
            { error: 'Rating must be between 1 and 5' },
            { status: 400 }
          );
        }
        feedbackData.rating = rating;
      }

      if (feedback !== undefined) {
        feedbackData.feedback = feedback;
      }

      await updateApplicationFeedback(applicationId, feedbackData);
      console.log('[API] Updated application feedback:', { applicationId, ...feedbackData });
    }

    return NextResponse.json({
      success: true,
      message: 'Application updated successfully',
    });
  } catch (error) {
    console.error('[API] Error updating application:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to update application',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
