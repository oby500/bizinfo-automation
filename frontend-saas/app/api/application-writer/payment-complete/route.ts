import { NextRequest, NextResponse } from 'next/server';
import { getCurrentUser } from '@/lib/auth/get-user';
import { sendNotificationSafe } from '@/lib/notifications/send';
import { db } from '@/lib/db/drizzle';
import { users } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { withRetry, PaymentErrorCode } from '@/lib/errors/payment-errors';

/**
 * Application Writer 결제 완료 처리 API
 *
 * 프론트엔드에서 PortOne 결제 완료 후 호출
 * FastAPI 백엔드로 결제 정보를 전달하여 수정권 할당 처리
 * 결제 완료 알림 발송 (카카오 알림톡 → SMS 폴백)
 */
export async function POST(request: NextRequest) {
  try {
    // 사용자 인증 확인
    const user = await getCurrentUser();
    if (!user || !user.id) {
      return NextResponse.json(
        { error: 'Unauthorized: Please login first' },
        { status: 401 }
      );
    }

    const body = await request.json();
    const { paymentId, tier, amount, announcementId, announcementSource } = body;

    // 세션의 userId 사용 (보안: 클라이언트가 임의로 userId 변경 불가)
    const userId = user.id;

    console.log('Application Writer payment complete:', {
      paymentId,
      userId,
      tier,
      amount,
      announcementId,
      announcementSource,
    });

    // 필수 파라미터 검증
    if (!paymentId || !tier || !amount || !announcementId) {
      return NextResponse.json(
        { error: 'Missing required parameters' },
        { status: 400 }
      );
    }

    // Tier 검증
    if (!['basic', 'standard', 'premium'].includes(tier)) {
      return NextResponse.json(
        { error: 'Invalid tier' },
        { status: 400 }
      );
    }

    // FastAPI 백엔드로 결제 완료 정보 전달 (재시도 로직 포함)
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    const result = await withRetry(async () => {
      const response = await fetch(`${backendUrl}/api/application-writer/payment-complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          payment_id: paymentId,
          user_id: userId,
          tier,
          amount,
          announcement_id: announcementId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || `Backend error: ${response.status}`;

        console.error('Backend payment processing failed:', {
          status: response.status,
          statusText: response.statusText,
          error: errorData,
        });

        // HTTP 상태 코드에 따른 재시도 여부 결정
        if (response.status >= 500 && response.status < 600) {
          // 5xx 서버 에러는 재시도
          throw new Error(`${PaymentErrorCode.SERVER_ERROR}: ${errorMessage}`);
        } else if (response.status === 429) {
          // Rate limit 에러는 재시도
          throw new Error(`${PaymentErrorCode.RATE_LIMIT}: ${errorMessage}`);
        } else if (response.status === 408 || response.status === 504) {
          // Timeout 에러는 재시도
          throw new Error(`${PaymentErrorCode.TIMEOUT}: ${errorMessage}`);
        } else {
          // 4xx 클라이언트 에러는 재시도하지 않음
          throw new Error(`${PaymentErrorCode.VALIDATION_ERROR}: ${errorMessage}`);
        }
      }

      return await response.json();
    }, {
      maxAttempts: 3,
      delayMs: 1000,
      backoffMultiplier: 2,
    });

    console.log('Payment processing successful:', result);

    // 알림 발송 (비동기, 실패해도 결제는 성공)
    try {
      // 사용자 정보 조회 (전화번호, 알림 설정)
      const [userInfo] = await db
        .select({
          name: users.name,
          email: users.email,
          phone: users.phone,
          notificationEnabled: users.notificationEnabled,
        })
        .from(users)
        .where(eq(users.id, parseInt(userId)))
        .limit(1);

      // 알림 수신 동의 + 전화번호가 있는 경우에만 발송
      if (userInfo?.notificationEnabled && userInfo.phone) {
        const tierCreditsMap = {
          basic: 2,
          standard: 3,
          premium: 4,
        };

        await sendNotificationSafe('payment', {
          userId: parseInt(userId),
          phoneNumber: userInfo.phone,
          userName: userInfo.name || userInfo.email || '고객님',
          tier: tier as 'basic' | 'standard' | 'premium',
          credits: tierCreditsMap[tier as keyof typeof tierCreditsMap] || 0,
          amount,
          paymentDate: new Date().toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          }),
        });

        console.log('Payment notification sent successfully');
      } else {
        console.log('Notification skipped: user has not enabled notifications or no phone number');
      }
    } catch (notificationError) {
      // 알림 발송 실패는 로그만 남기고 결제는 정상 처리
      console.error('Failed to send payment notification:', notificationError);
    }

    return NextResponse.json({
      success: true,
      credits: result.credits || {
        tier_credits: result.tier_credits || 0,
        purchased_credits: result.purchased_credits || 0,
        total_available: result.total_available || 0,
      },
      message: '결제가 완료되고 수정권이 할당되었습니다.',
    });

  } catch (error) {
    console.error('Payment complete API error:', error);
    return NextResponse.json(
      {
        error: 'Payment processing failed',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}
