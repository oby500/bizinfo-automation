import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db/drizzle';
import { teams } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    console.log('PortOne webhook received:', body);

    // PortOne webhook 시그니처 검증
    const signature = request.headers.get('portone-signature');

    // TODO: 실제 프로덕션에서는 시그니처 검증 구현 필요
    // const isValid = verifyPortOneSignature(body, signature);
    // if (!isValid) {
    //   return NextResponse.json({ error: 'Invalid signature' }, { status: 401 });
    // }

    const { type, data } = body;

    switch (type) {
      case 'Transaction.Paid':
        // 결제 완료 처리
        await handlePaymentSuccess(data);
        break;

      case 'Transaction.Failed':
        // 결제 실패 처리
        await handlePaymentFailed(data);
        break;

      case 'Transaction.Cancelled':
        // 결제 취소 처리
        await handlePaymentCancelled(data);
        break;

      case 'BillingKey.Issued':
        // 정기결제 빌링키 발급
        await handleBillingKeyIssued(data);
        break;

      default:
        console.log('Unknown webhook type:', type);
    }

    return NextResponse.json({ received: true });
  } catch (error) {
    console.error('PortOne webhook error:', error);
    return NextResponse.json(
      { error: 'Webhook processing failed' },
      { status: 500 }
    );
  }
}

async function handlePaymentSuccess(data: any) {
  const { paymentId, orderName, totalAmount, customer, metadata } = data;

  console.log('Payment successful:', {
    paymentId,
    orderName,
    totalAmount,
    customer,
  });

  // TODO: 데이터베이스 업데이트
  // 1. 사용자의 구독 상태 업데이트
  // 2. 크레딧 충전의 경우 크레딧 추가
  // 3. 결제 내역 저장

  // 예시: 팀 구독 상태 업데이트
  if (metadata?.teamId) {
    await db
      .update(teams)
      .set({
        subscriptionStatus: 'active',
        planName: metadata.planName,
        updatedAt: new Date(),
      })
      .where(eq(teams.id, parseInt(metadata.teamId)));
  }

  // TODO: 결제 완료 이메일 발송
}

async function handlePaymentFailed(data: any) {
  const { paymentId, failReason } = data;

  console.error('Payment failed:', {
    paymentId,
    failReason,
  });

  // TODO: 결제 실패 처리
  // 1. 사용자에게 알림
  // 2. 재시도 안내
}

async function handlePaymentCancelled(data: any) {
  const { paymentId, cancelReason } = data;

  console.log('Payment cancelled:', {
    paymentId,
    cancelReason,
  });

  // TODO: 결제 취소 처리
  // 1. 구독 상태 변경
  // 2. 환불 처리
}

async function handleBillingKeyIssued(data: any) {
  const { billingKey, customer, metadata } = data;

  console.log('Billing key issued:', {
    billingKey,
    customer,
  });

  // TODO: 정기결제 빌링키 저장
  // 1. 데이터베이스에 빌링키 저장
  // 2. 다음 결제일 설정
}
