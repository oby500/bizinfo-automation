'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { requestPayment } from '@portone/browser-sdk/v2';

interface ChargeOption {
  id: string;
  amount: number;
  price: number;
  bonus: number;
  popular?: boolean;
}

export default function ChargePage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [selectedOption, setSelectedOption] = useState<ChargeOption | null>(null);
  const [currentBalance, setCurrentBalance] = useState(0);

  // 로그인 체크 - 미로그인 시 로그인 페이지로 리디렉트
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login?callbackUrl=/charge');
    }
  }, [status, router]);

  const chargeOptions: ChargeOption[] = [
    { id: '1', amount: 10000, price: 10000, bonus: 0 },
    { id: '2', amount: 30000, price: 30000, bonus: 3000 },
    { id: '3', amount: 50000, price: 50000, bonus: 7000, popular: true },
    { id: '4', amount: 100000, price: 100000, bonus: 20000 },
    { id: '5', amount: 300000, price: 300000, bonus: 100000 },
  ];

  const handleCharge = async () => {
    if (!selectedOption) {
      alert('충전할 금액을 선택해주세요.');
      return;
    }

    // 로그인 확인
    if (!session?.user?.id) {
      alert('로그인이 필요합니다.');
      router.push('/login?callbackUrl=/charge');
      return;
    }

    const totalAmount = selectedOption.amount + selectedOption.bonus;

    try {
      // 고유한 결제 ID 생성
      const paymentId = `charge-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const orderName = `크레딧 충전 ${selectedOption.price.toLocaleString()}원 (보너스 ${selectedOption.bonus.toLocaleString()}원)`;

      console.log('결제 요청:', {
        paymentId,
        orderName,
        amount: selectedOption.price,
        totalCredit: totalAmount
      });

      // PortOne 결제 SDK 호출
      const response = await requestPayment({
        storeId: process.env.NEXT_PUBLIC_PORTONE_STORE_ID!,
        paymentId,
        orderName,
        totalAmount: selectedOption.price,
        currency: 'KRW',
        channelKey: 'channel-key-5238b15c-b9f4-4393-852b-a80b2c7d4488',
        payMethod: 'CARD',
        customer: {
          fullName: session.user.name || '사용자',
          email: session.user.email || '',
        },
        customData: {
          creditAmount: selectedOption.amount,
          bonusAmount: selectedOption.bonus,
          totalCredit: totalAmount,
        },
      });

      console.log('결제 응답:', response);

      // 결제 성공 여부 확인
      if (response?.code != null) {
        // 결제 실패
        console.error('결제 실패:', response);
        alert(`결제가 취소되었거나 실패했습니다.\n${response.message || '알 수 없는 오류'}`);
        return;
      }

      // 결제 성공 - 서버에 결제 검증 요청
      console.log('결제 성공! 서버 검증 중...');

      // 서버 API를 호출해서 결제 검증 및 크레딧 추가
      const verifyResponse = await fetch('/api/payments/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paymentId,
          userId: parseInt(session.user.id),
          customData: {
            orderName,
            creditAmount: selectedOption.amount,
            bonusAmount: selectedOption.bonus,
            totalCredit: totalAmount,
          },
        }),
      });

      if (!verifyResponse.ok) {
        throw new Error('결제 검증 실패');
      }

      const verifyData = await verifyResponse.json();
      console.log('결제 검증 완료:', verifyData);

      // 크레딧 잔액 업데이트
      const newBalance = verifyData.credit.balance;
      setCurrentBalance(newBalance);

      // 임시: localStorage에도 저장 (실제로는 DB에서 가져오기)
      localStorage.setItem('userBalance', newBalance.toString());

      alert(
        `✅ 충전이 완료되었습니다!\n\n` +
        `결제 금액: ${selectedOption.price.toLocaleString()}원\n` +
        `충전 크레딧: ${selectedOption.amount.toLocaleString()}원\n` +
        `보너스 크레딧: ${selectedOption.bonus.toLocaleString()}원\n\n` +
        `현재 잔액: ${newBalance.toLocaleString()}원`
      );

      // 결제 내역 페이지로 이동
      router.push('/mypage');

    } catch (error) {
      console.error('결제 오류:', error);
      alert('결제 중 오류가 발생했습니다. 다시 시도해주세요.');
    }
  };

  // 컴포넌트 마운트 시 잔액 로드
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const balance = localStorage.getItem('userBalance');
      if (balance) {
        setCurrentBalance(parseInt(balance));
      }
    }
  }, []);

  // 로딩 중이거나 미로그인 시 로딩 화면
  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  // 미로그인 시 빈 화면 (리디렉트 진행 중)
  if (!session) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="container mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-1">충전하기</h1>
              <p className="text-gray-600">
                신청서 작성, 사업계획서 초안 작성 서비스를 이용하려면 충전이 필요합니다
              </p>
            </div>
            <Button onClick={() => router.push('/')} variant="outline">
              ← 홈으로
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8">
        {/* 현재 잔액 */}
        <Card className="mb-8 bg-gradient-to-r from-orange-500 to-orange-600 text-white">
          <CardContent className="py-8">
            <div className="text-center">
              <p className="text-lg mb-2 opacity-90">현재 보유 크레딧</p>
              <p className="text-5xl font-bold">{currentBalance.toLocaleString()}원</p>
            </div>
          </CardContent>
        </Card>

        {/* 충전 옵션 */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">충전 금액 선택</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {chargeOptions.map((option) => (
              <Card
                key={option.id}
                className={`cursor-pointer transition-all hover:shadow-lg ${
                  selectedOption?.id === option.id
                    ? 'border-2 border-orange-500 shadow-md'
                    : 'border border-gray-200'
                } ${option.popular ? 'relative' : ''}`}
                onClick={() => setSelectedOption(option)}
              >
                {option.popular && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <Badge className="bg-red-500 text-white">인기</Badge>
                  </div>
                )}
                <CardHeader>
                  <CardTitle className="text-2xl text-center">
                    {option.price.toLocaleString()}원
                  </CardTitle>
                  {option.bonus > 0 && (
                    <CardDescription className="text-center">
                      <span className="text-orange-500 font-semibold">
                        +{option.bonus.toLocaleString()}원 보너스
                      </span>
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="text-center">
                    <p className="text-sm text-gray-600 mb-2">총 충전 금액</p>
                    <p className="text-3xl font-bold text-orange-500">
                      {(option.amount + option.bonus).toLocaleString()}원
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* 충전 버튼 */}
        <div className="text-center">
          <Button
            onClick={handleCharge}
            disabled={!selectedOption}
            size="lg"
            className="px-12 py-6 text-lg bg-orange-500 hover:bg-orange-600"
          >
            {selectedOption
              ? `${selectedOption.price.toLocaleString()}원 충전하기`
              : '충전할 금액을 선택해주세요'}
          </Button>
        </div>

        {/* 서비스 이용 요금표 */}
        <Card className="mt-12">
          <CardHeader>
            <CardTitle>서비스 이용 요금</CardTitle>
            <CardDescription>로튼 서비스 이용 시 차감되는 크레딧입니다</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between py-3 border-b">
                <div>
                  <p className="font-semibold text-gray-900">신청서 초안 작성 (기본)</p>
                  <p className="text-sm text-gray-600">1개 공고 신청서 기본 초안</p>
                </div>
                <p className="text-lg font-bold text-orange-500">5,000원</p>
              </div>

              <div className="flex items-center justify-between py-3 border-b">
                <div>
                  <p className="font-semibold text-gray-900">신청서 초안 작성 (프리미엄)</p>
                  <p className="text-sm text-gray-600">상세 분석 + 맞춤 작성 + 2회 수정</p>
                </div>
                <p className="text-lg font-bold text-orange-500">15,000원</p>
              </div>

              <div className="flex items-center justify-between py-3 border-b">
                <div>
                  <p className="font-semibold text-gray-900">사업계획서 초안 작성</p>
                  <p className="text-sm text-gray-600">10페이지 내외 기본 구조 + 내용</p>
                </div>
                <p className="text-lg font-bold text-orange-500">30,000원</p>
              </div>

              <div className="flex items-center justify-between py-3 border-b">
                <div>
                  <p className="font-semibold text-gray-900">사업계획서 프리미엄</p>
                  <p className="text-sm text-gray-600">상세 분석 + 산업 조사 + 3회 수정</p>
                </div>
                <p className="text-lg font-bold text-orange-500">80,000원</p>
              </div>

              <div className="flex items-center justify-between py-3">
                <div>
                  <p className="font-semibold text-gray-900">AI 컨설팅 (1시간)</p>
                  <p className="text-sm text-gray-600">실시간 질의응답 + 맞춤 조언</p>
                </div>
                <p className="text-lg font-bold text-orange-500">50,000원</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 결제 안내 */}
        <div className="mt-8 p-6 bg-blue-50 rounded-lg border border-blue-200">
          <h3 className="font-semibold text-blue-900 mb-3">💡 결제 안내</h3>
          <ul className="text-sm text-blue-800 space-y-2">
            <li>• 신용카드, 체크카드, 계좌이체, 간편결제(카카오페이, 네이버페이 등) 가능</li>
            <li>• 충전 금액은 유효기간 없이 자유롭게 사용 가능</li>
            <li>• 보너스 크레딧은 환불 시 제외됩니다</li>
            <li>• 미사용 크레딧은 언제든지 환불 가능 (수수료 5% 차감)</li>
            <li>• 영수증은 마이페이지에서 출력 가능</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
