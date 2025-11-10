'use client';

import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';
import { loadPaymentWidget } from '@portone/browser-sdk/v2';

export default function PricingPage() {
  const [loading, setLoading] = useState(false);

  const handlePayment = async (planName: string, amount: number) => {
    setLoading(true);

    try {
      const paymentId = `payment-${Date.now()}`;
      const orderName = `${planName} 플랜 구독`;

      // PortOne 결제 위젯 로드 및 결제 요청
      await loadPaymentWidget(process.env.NEXT_PUBLIC_PORTONE_STORE_ID!, {
        paymentId,
        orderName,
        totalAmount: amount,
        currency: 'KRW',
        channelKey: 'channel-key-here', // PortOne 채널 키
        payMethod: 'CARD', // 카드 결제
      });

      // 결제 완료 후 처리는 webhook에서
      console.log('Payment initiated:', { paymentId, orderName, amount });

    } catch (error) {
      console.error('Payment error:', error);
      alert('결제 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          정부지원사업 검색 서비스
        </h1>
        <p className="text-xl text-gray-600">
          AI 기반 맞춤형 공고 검색으로 최적의 지원사업을 찾아보세요
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        {/* 무료 플랜 */}
        <PricingCard
          name="무료"
          price={0}
          interval="월"
          features={[
            '기본 검색 기능',
            '일 10회 검색 제한',
            '최근 공고 조회',
            '북마크 10개',
          ]}
          buttonText="시작하기"
          onPayment={() => window.location.href = '/sign-up'}
          isPopular={false}
          disabled={loading}
        />

        {/* 베이직 플랜 */}
        <PricingCard
          name="베이직"
          price={9900}
          interval="월"
          features={[
            '무제한 검색',
            'AI 의미 검색',
            '고급 필터링',
            '무제한 북마크',
            '마감일 알림',
            '이메일 고객지원',
          ]}
          buttonText="구독하기"
          onPayment={() => handlePayment('베이직', 9900)}
          isPopular={true}
          disabled={loading}
        />

        {/* 프리미엄 플랜 */}
        <PricingCard
          name="프리미엄"
          price={29900}
          interval="월"
          features={[
            '베이직 플랜 모든 기능',
            'AI 맞춤 추천',
            '공고 비교 분석',
            '전문가 컨설팅 (월 1회)',
            '우선 고객지원',
            '신기능 우선 체험',
          ]}
          buttonText="구독하기"
          onPayment={() => handlePayment('프리미엄', 29900)}
          isPopular={false}
          disabled={loading}
        />
      </div>

      {/* 크레딧 충전 섹션 */}
      <div className="mt-16 max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-8">
          크레딧 충전
        </h2>
        <p className="text-center text-gray-600 mb-8">
          구독 없이 필요한 만큼만 사용하고 싶으신가요?
        </p>
        <div className="grid md:grid-cols-3 gap-6">
          <CreditCard
            credits={100}
            price={9900}
            onPayment={() => handlePayment('크레딧 100', 9900)}
            disabled={loading}
          />
          <CreditCard
            credits={500}
            price={39900}
            bonus={50}
            onPayment={() => handlePayment('크레딧 500', 39900)}
            disabled={loading}
          />
          <CreditCard
            credits={1000}
            price={69900}
            bonus={200}
            onPayment={() => handlePayment('크레딧 1000', 69900)}
            disabled={loading}
          />
        </div>
      </div>
    </main>
  );
}

function PricingCard({
  name,
  price,
  interval,
  features,
  buttonText,
  onPayment,
  isPopular,
  disabled,
}: {
  name: string;
  price: number;
  interval: string;
  features: string[];
  buttonText: string;
  onPayment: () => void;
  isPopular: boolean;
  disabled: boolean;
}) {
  return (
    <div className={`relative pt-6 pb-8 px-6 rounded-2xl border-2 ${
      isPopular
        ? 'border-orange-500 shadow-lg scale-105'
        : 'border-gray-200'
    }`}>
      {isPopular && (
        <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
          <span className="bg-orange-500 text-white px-4 py-1 rounded-full text-sm font-medium">
            인기
          </span>
        </div>
      )}

      <h2 className="text-2xl font-bold text-gray-900 mb-2">{name}</h2>
      <div className="mb-6">
        <span className="text-4xl font-bold text-gray-900">
          {price === 0 ? '무료' : `₩${price.toLocaleString()}`}
        </span>
        {price > 0 && (
          <span className="text-gray-600 ml-2">/ {interval}</span>
        )}
      </div>

      <ul className="space-y-3 mb-8">
        {features.map((feature, index) => (
          <li key={index} className="flex items-start">
            <Check className="h-5 w-5 text-orange-500 mr-3 mt-0.5 flex-shrink-0" />
            <span className="text-gray-700">{feature}</span>
          </li>
        ))}
      </ul>

      <Button
        onClick={onPayment}
        disabled={disabled}
        className={`w-full py-3 rounded-full font-medium ${
          isPopular
            ? 'bg-orange-500 hover:bg-orange-600 text-white'
            : 'bg-gray-100 hover:bg-gray-200 text-gray-900'
        }`}
      >
        {disabled ? '처리 중...' : buttonText}
      </Button>
    </div>
  );
}

function CreditCard({
  credits,
  price,
  bonus,
  onPayment,
  disabled,
}: {
  credits: number;
  price: number;
  bonus?: number;
  onPayment: () => void;
  disabled: boolean;
}) {
  return (
    <div className="border-2 border-gray-200 rounded-xl p-6 hover:border-orange-500 transition-colors">
      <div className="text-center mb-4">
        <div className="text-3xl font-bold text-gray-900 mb-2">
          {credits}
          {bonus && <span className="text-orange-500 ml-1">+{bonus}</span>}
        </div>
        <div className="text-sm text-gray-600">크레딧</div>
      </div>

      <div className="text-center mb-4">
        <div className="text-2xl font-bold text-gray-900">
          ₩{price.toLocaleString()}
        </div>
      </div>

      {bonus && (
        <div className="bg-orange-50 text-orange-700 text-sm text-center py-2 rounded-lg mb-4">
          🎁 보너스 {bonus} 크레딧
        </div>
      )}

      <Button
        onClick={onPayment}
        disabled={disabled}
        className="w-full bg-gray-900 hover:bg-gray-800 text-white rounded-full"
      >
        {disabled ? '처리 중...' : '충전하기'}
      </Button>
    </div>
  );
}
