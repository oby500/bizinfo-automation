import { NextRequest, NextResponse } from 'next/server';

/**
 * Profile Chat API
 *
 * 대화형 회사 정보(Z) 수집
 * - 사용자 응답 분석 및 데이터 추출
 * - 다음 질문 생성
 * - 완료 여부 판단 (completion_percentage)
 */

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface CompanyProfile {
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
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      announcement_id: announcementId,
      announcement_source: announcementSource,
      conversation_history: conversationHistory,
      user_message: userMessage,
      collected_data: currentProfile,
    } = body;

    // 필수 파라미터 검증
    if (!announcementId || !announcementSource || !userMessage) {
      return NextResponse.json(
        { error: 'Missing required parameters' },
        { status: 400 }
      );
    }

    console.log('Processing profile chat:', {
      announcementId,
      messageLength: userMessage.length,
      historyLength: conversationHistory?.length || 0,
      currentFields: Object.keys(currentProfile || {}).length,
    });

    // OpenAI GPT-4o-mini API 설정
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      console.error('OPENAI_API_KEY not configured');
      return NextResponse.json(
        { error: 'AI service not configured' },
        { status: 500 }
      );
    }

    // 현재까지 수집된 프로필 데이터
    const collectedProfile: CompanyProfile = currentProfile || {};

    // 필수 필드 체크
    const requiredFields = [
      'company_name',
      'business_field',
      'founding_year',
      'main_products',
      'target_goal',
    ];

    const collectedRequiredFields = requiredFields.filter(
      (field) => collectedProfile[field] !== undefined && collectedProfile[field] !== null && collectedProfile[field] !== ''
    );

    // 완료 퍼센티지 계산
    const completionPercentage = Math.round((collectedRequiredFields.length / requiredFields.length) * 100);

    console.log('[Profile Chat] 현재 수집 상태:', {
      collectedRequiredFields: collectedRequiredFields,
      totalRequired: requiredFields.length,
      percentage: completionPercentage,
      collectedProfile: collectedProfile
    });

    // AI 시스템 프롬프트 - 점진적 수정 전략 반영
    const systemPrompt = `당신은 정부 지원사업 신청서 작성을 돕는 AI 어시스턴트입니다.
사용자와 대화하며 회사 정보(Z)를 수집하고 있습니다.

⚠️ **중요: 반드시 JSON 형식으로만 응답해야 합니다. 일반 텍스트 응답은 절대 안됩니다!**

## ⭐ 점진적 수정 전략 (Iterative Refinement)
- **60% 이상 수집되면 신청서 초안 작성 시작 가능**
- 초반에는 최소한의 정보로 초안을 빠르게 작성
- 부족한 정보는 나중에 추가 질문으로 보완
- 수정권(Revision Credits)을 활용한 점진적 개선 프로세스

## 현재 수집 상태
필수 정보 (${collectedRequiredFields.length}/${requiredFields.length} 완료 = ${completionPercentage}%):
${requiredFields.map((field) => {
  const collected = collectedProfile[field];
  const fieldNames: Record<string, string> = {
    company_name: '회사명',
    business_field: '사업 분야',
    founding_year: '설립 연도',
    main_products: '주요 제품/서비스',
    target_goal: '지원 목표',
  };
  return `- ${fieldNames[field]}: ${collected ? '✅ ' + collected : '❌ 미수집'}`;
}).join('\n')}

선택 정보:
${Object.entries(collectedProfile)
  .filter(([key]) => !requiredFields.includes(key))
  .map(([key, value]) => `- ${key}: ${value}`)
  .join('\n') || '(없음)'}

## 작업 지시
1. 사용자의 최근 응답("${userMessage}")을 분석하여 정보 추출
2. **이미 수집된 정보(✅)는 extracted_data에 포함하지 마세요** (중복 방지)
3. **60% 이상 수집되었다면** 완료 안내 (나머지는 나중에 보완 가능)
4. 60% 미만이라면 **미수집 정보(❌) 중에서만** 다음 질문 선택

## 응답 형식
JSON 형식으로만 응답하세요:
{
  "extracted_data": {
    "field_name": "추출된 값",
    ...
  },
  "ai_response": "사용자에게 보여줄 응답 메시지 (공감 + 다음 질문 또는 완료 안내)",
  "next_question_field": "다음에 물어볼 필드명 (없으면 null)",
  "is_complete": true 또는 false,
  "completion_percentage": 0-100 사이 숫자
}

## 완료 조건 (⭐ 중요)
- **60% 이상 (3개 이상)** 수집되면 is_complete: true
- 완료 메시지 예시: "기본 정보 수집이 완료되었습니다! 이제 신청서 초안을 작성하겠습니다. 부족한 정보가 있다면 나중에 수정을 통해 보완할 수 있습니다."

## 질문 가이드라인 (⭐ 중요: 중복 질문 방지!)
- **이미 수집된 정보(✅ 표시)는 절대 다시 묻지 마세요!**
- 미수집 정보(❌ 표시) 중에서만 다음 질문 선택
- 한 번에 1가지만 물어보기
- 자연스럽고 친근한 톤 유지
- 사용자 응답에 간단히 공감한 후 다음 질문
- 필수 정보 우선 수집
- 60% 이상 수집되면 완료 안내 (100% 수집 필요 없음!)

## ⭐ "지원 목표" (target_goal) 질문 전략 - 사용자 친화적으로!
"지원 목표"라는 추상적 용어 대신 구체적이고 이해하기 쉬운 질문으로 물어보세요:

**좋은 질문 예시:**
- "이 지원사업을 통해 어떤 목표를 달성하고 싶으신가요?"
- "이번 지원사업으로 회사에서 이루고 싶은 성과가 있으신가요?"
- "지원금을 받으시면 주로 어디에 활용하실 계획이신가요?" (예: 제품 개발, 시장 확대, 인력 채용 등)
- "이 공고에 지원하시는 주된 목적은 무엇인가요?"

**나쁜 질문 예시:**
- ❌ "지원 목표를 알려주세요" (너무 추상적)
- ❌ "target_goal을 입력해주세요" (기술 용어 사용)
- ❌ "목표가 뭔가요?" (불친절하고 모호함)

**답변 유도 팁:**
- 구체적인 예시 제공: "예를 들어, 신제품 개발이나 해외 진출 같은 목표를 말씀해주시면 됩니다"
- 선택지 제시: "기술 개발, 사업 확장, 인력 확보 등 여러 목적이 있을 수 있어요"
- 실용적 접근: "이 지원금으로 무엇을 하고 싶으신가요?"

## 정보 추출 규칙
- founding_year: 숫자만 추출 (예: "2020년" → 2020)
- employee_count: 숫자만 추출 (예: "50명" → 50)
- target_goal: 사용자가 "어떤 목표?"라고 반문하면 구체적 예시로 다시 질문
- 명확하지 않은 경우 extracted_data에 포함하지 말고 재질문`;

    // 대화 히스토리 구성
    const messages: Message[] = conversationHistory || [];
    messages.push({
      role: 'user',
      content: userMessage,
    });

    // OpenAI GPT-4o-mini API 호출
    const openaiResponse = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: systemPrompt,
          },
          ...messages.map((msg) => ({
            role: msg.role,
            content: msg.content,
          })),
        ],
        response_format: { type: 'json_object' },
        max_tokens: 2048,
        temperature: 0.7,
      }),
    });

    if (!openaiResponse.ok) {
      const errorData = await openaiResponse.json().catch(() => ({}));
      console.error('OpenAI API error:', openaiResponse.status, errorData);
      return NextResponse.json(
        { error: 'Failed to process chat message' },
        { status: 500 }
      );
    }

    const openaiData = await openaiResponse.json();
    let aiResponseText = openaiData.choices[0].message.content;

    // JSON 응답 파싱
    let parsedResponse;
    try {
      // JSON 코드 블록 제거
      if (aiResponseText.includes('```json')) {
        aiResponseText = aiResponseText.split('```json')[1].split('```')[0].trim();
      } else if (aiResponseText.includes('```')) {
        aiResponseText = aiResponseText.split('```')[1].split('```')[0].trim();
      }

      parsedResponse = JSON.parse(aiResponseText);
    } catch (parseError) {
      console.error('Failed to parse AI response:', aiResponseText);
      // Fallback: 간단한 응답 생성
      parsedResponse = {
        extracted_data: {},
        ai_response: aiResponseText,
        next_question_field: null,
        is_complete: false,
        completion_percentage: completionPercentage,
      };
    }

    // 추출된 데이터 병합
    const updatedProfile: CompanyProfile = {
      ...collectedProfile,
      ...parsedResponse.extracted_data,
    };

    // 완료 상태 재계산
    const updatedRequiredFields = requiredFields.filter(
      (field) => updatedProfile[field] !== undefined && updatedProfile[field] !== null && updatedProfile[field] !== ''
    );
    const updatedCompletionPercentage = Math.round((updatedRequiredFields.length / requiredFields.length) * 100);

    // ⭐ 점진적 수정 전략: 60% 이상 수집되면 신청서 초안 작성 시작 가능
    // - 초반에는 최소한의 정보로 초안 작성
    // - 부족한 정보는 나중에 추가 질문으로 보완
    // - 수정권(Revision Credits)을 활용한 점진적 개선
    const isComplete = updatedCompletionPercentage >= 60;  // 100% → 60%로 변경

    console.log('Profile chat processed:', {
      extractedFields: Object.keys(parsedResponse.extracted_data || {}),
      completionPercentage: updatedCompletionPercentage,
      isComplete,
    });

    return NextResponse.json({
      success: true,
      ai_response: parsedResponse.ai_response,
      extracted_data: parsedResponse.extracted_data || {},
      profile_data: updatedProfile,
      completion_percentage: updatedCompletionPercentage,
      is_complete: isComplete,
      next_question_field: isComplete ? null : parsedResponse.next_question_field,
    });

  } catch (error) {
    console.error('Profile chat API error:', error);
    return NextResponse.json(
      {
        error: 'Failed to process chat message',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
