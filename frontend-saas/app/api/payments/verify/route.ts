import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db/drizzle';
import { payments, credits, creditTransactions } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

/**
 * 결제 검증 및 크레딧 추가 API
 *
 * 프론트엔드에서 결제 완료 후 호출하여 서버에서 결제를 검증하고 크레딧을 추가합니다.
 *
 * POST /api/payments/verify
 * Body: { paymentId: string, userId: number, customData: object }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { paymentId, userId, customData } = body;

    console.log('[VERIFY] 결제 검증 요청:', { paymentId, userId });

    if (!paymentId || !userId) {
      return NextResponse.json(
        { error: 'paymentId 및 userId는 필수입니다.' },
        { status: 400 }
      );
    }

    // PortOne API를 호출하여 실제 결제 상태 확인
    console.log('[VERIFY] PortOne API 호출 시작:', paymentId);

    const portoneResponse = await fetch(`https://api.portone.io/payments/${paymentId}`, {
      headers: {
        'Authorization': `PortOne ${process.env.PORTONE_API_SECRET}`,
      },
    });

    if (!portoneResponse.ok) {
      console.error('[VERIFY] PortOne API 오류:', portoneResponse.status, await portoneResponse.text());
      return NextResponse.json(
        { error: 'PortOne API 호출 실패' },
        { status: 500 }
      );
    }

    const paymentData = await portoneResponse.json();
    console.log('[VERIFY] PortOne 응답:', paymentData);

    // 결제 상태 확인
    if (paymentData.status !== 'PAID') {
      console.error('[VERIFY] 결제 미완료:', paymentData.status);
      return NextResponse.json(
        { error: '결제가 완료되지 않았습니다.' },
        { status: 400 }
      );
    }

    // 결제 내역 저장
    const [paymentRecord] = await db
      .insert(payments)
      .values({
        userId,
        paymentId,
        orderName: customData?.orderName || '크레딧 충전',
        amount: paymentData.amount?.total || customData?.creditAmount || 0,
        status: 'paid',
        paymentMethod: paymentData.method || 'CARD',
        creditAmount: customData?.creditAmount || 0,
        bonusAmount: customData?.bonusAmount || 0,
        totalCredit: customData?.totalCredit || 0,
        paidAt: new Date(paymentData.paidAt) || new Date(),
      })
      .returning();

    console.log('[VERIFY] 결제 내역 저장 완료:', paymentRecord.id);

    // 크레딧 잔액 조회 또는 생성
    let [userCredit] = await db
      .select()
      .from(credits)
      .where(eq(credits.userId, userId));

    if (!userCredit) {
      // 첫 충전 - 크레딧 레코드 생성
      [userCredit] = await db
        .insert(credits)
        .values({
          userId,
          balance: customData?.totalCredit || 0,
          totalCharged: customData?.totalCredit || 0,
          totalUsed: 0,
        })
        .returning();

      console.log('[VERIFY] 크레딧 레코드 생성:', userCredit);
    } else {
      // 기존 잔액에 추가
      const newBalance = userCredit.balance + (customData?.totalCredit || 0);
      const newTotalCharged = userCredit.totalCharged + (customData?.totalCredit || 0);

      [userCredit] = await db
        .update(credits)
        .set({
          balance: newBalance,
          totalCharged: newTotalCharged,
          updatedAt: new Date(),
        })
        .where(eq(credits.userId, userId))
        .returning();

      console.log('[VERIFY] 크레딧 잔액 업데이트:', userCredit);
    }

    // 크레딧 거래 내역 저장
    await db.insert(creditTransactions).values({
      userId,
      paymentId: paymentRecord.id,
      type: 'charge',
      amount: customData?.totalCredit || 0,
      balance: userCredit.balance,
      description: `크레딧 충전: ${customData?.creditAmount || 0}원 (보너스: ${customData?.bonusAmount || 0}원)`,
    });

    console.log('[VERIFY] 크레딧 거래 내역 저장 완료');

    return NextResponse.json({
      success: true,
      payment: paymentRecord,
      credit: userCredit,
    });

  } catch (error) {
    console.error('[VERIFY] 결제 검증 오류:', error);
    return NextResponse.json(
      { error: '결제 검증에 실패했습니다.' },
      { status: 500 }
    );
  }
}
