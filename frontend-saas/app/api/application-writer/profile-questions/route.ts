import { NextRequest, NextResponse } from 'next/server';

/**
 * Profile Questions Generation API
 *
 * Y (공고 가이드라인)를 기반으로 Z (회사 정보) 수집을 위한 질문 생성
 * - 공고의 지원자격, 평가기준, 지원내용을 분석
 * - 맞춤형 프로필 수집 질문 전략 생성
 * - 웰컴 메시지와 첫 질문 반환
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    // ⭐ 언더스코어 필드명으로 변경 (프론트엔드와 일치)
    const { announcement_id, announcement_source, announcement_title, announcement_analysis } = body;
    const announcementId = announcement_id;
    const announcementSource = announcement_source;
    const announcementTitle = announcement_title;
    const announcementAnalysis = announcement_analysis;  // ⭐ Y 분석 결과 (자격요건, 평가기준, 작성전략)

    // 필수 파라미터 검증
    if (!announcementId || !announcementSource) {
      return NextResponse.json(
        { error: 'Missing required parameters: announcement_id, announcement_source' },
        { status: 400 }
      );
    }

    console.log('Generating profile questions for announcement:', {
      id: announcementId,
      source: announcementSource,
      title: announcementTitle,
      hasAnalysis: !!announcementAnalysis,  // ⭐ Y 분석 결과 여부 로깅
    });

    // FastAPI 백엔드로 공고 정보 조회 및 Y 분석
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    console.log('[DEBUG] Fetching announcement from backend:', `${backendUrl}/api/announcement/${announcementId}`);

    const response = await fetch(`${backendUrl}/api/announcement/${announcementId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.error('[ERROR] Failed to fetch announcement:', response.status, response.statusText);
      const errorText = await response.text().catch(() => 'Unable to read error response');
      console.error('[ERROR] Backend response:', errorText);
      return NextResponse.json(
        { error: 'Failed to fetch announcement details' },
        { status: 500 }
      );
    }

    const announcementData = await response.json();
    console.log('[DEBUG] Backend announcement data received:', {
      hasTitle: !!announcementData.title,
      hasSummary: !!announcementData.summary || !!announcementData.detailed_summary || !!announcementData.simple_summary,
      hasExtraInfo: !!announcementData.extra_info,
      hasOrganization: !!announcementData.organization
    });

    // OpenAI GPT-4o-mini를 사용하여 Y → Z 질문 전략 생성
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      console.error('OPENAI_API_KEY not configured');
      return NextResponse.json(
        { error: 'AI service not configured' },
        { status: 500 }
      );
    }

    // Y (공고 가이드라인) 추출
    const announcementGuidelines = {
      title: announcementData.title || announcementTitle,
      summary: announcementData.summary || announcementData.detailed_summary || announcementData.simple_summary || '',
      target: announcementData.extra_info?.target || '',
      scale: announcementData.extra_info?.scale || '',
      organization: announcementData.organization || '',
    };
    console.log('[DEBUG] Extracted announcement guidelines:', {
      titleLength: announcementGuidelines.title?.length || 0,
      summaryLength: announcementGuidelines.summary?.length || 0,
      hasTarget: !!announcementGuidelines.target,
      hasScale: !!announcementGuidelines.scale,
      hasOrganization: !!announcementGuidelines.organization
    });

    // AI 프롬프트: Y 분석 결과를 기반으로 Z 질문 전략 생성
    // ⭐ Y 분석 결과가 있으면 활용, 없으면 기본 공고 정보만 사용
    const systemPrompt = announcementAnalysis
      ? `당신은 정부 지원사업 신청서 작성을 돕는 AI 어시스턴트입니다.
사용자가 신청하려는 공고(Y)에 대한 심층 분석 결과를 활용하여, 최적의 신청서 작성에 필요한 회사 정보(Z)를 수집하기 위한 맞춤형 질문 전략을 수립합니다.

## 공고 심층 분석 결과 (Y Analysis - Writing Analysis에서 제공)
${JSON.stringify(announcementAnalysis, null, 2)}

위 분석 결과에는 다음이 포함되어 있습니다:
- 자격요건: 지원 가능한 기업의 필수 조건
- 평가기준: 신청서 심사 시 중점적으로 평가하는 항목
- 핵심키워드: 신청서에 반드시 포함해야 할 키워드
- 작성전략: 효과적인 신청서 작성을 위한 전략

## 목표
1. **Y 분석 결과를 최대한 활용**하여 이 공고에 최적화된 회사 정보(Z) 수집
2. **⭐ 우선순위 1**: Y 분석에 "과제별 상세 정보"가 있다면 어떤 과제에 신청할지 먼저 질문 (가장 중요!)
3. 평가기준과 직접 연관된 정보를 우선적으로 수집
4. 자연스러운 대화형 질문 전략 수립

## 회사 정보(Z) 필수 항목
- company_name: 회사명
- business_field: 사업 분야 (Y 분석의 자격요건과 연계)
- founding_year: 설립 연도 (Y 분석의 자격요건과 연계)
- main_products: 주요 제품/서비스 (Y 분석의 평가기준과 연계)
- target_goal: 지원사업 목표 (Y 분석의 핵심키워드 활용)

## 회사 정보(Z) 선택 항목 (Y 분석 결과에 따라 우선순위 조정)
- business_registration_number: 사업자등록번호
- revenue: 매출액 (평가기준에 매출 관련 항목이 있는 경우 필수)
- employee_count: 직원 수 (평가기준에 인력 관련 항목이 있는 경우 필수)
- technology: 보유 기술/특허 (평가기준에 기술력 관련 항목이 있는 경우 필수)
- past_support: 과거 지원사업 수혜 경험 (평가기준에 관련 항목이 있는 경우 필수)
- additional_info: Y 분석 결과에 따른 추가 맞춤 정보

## 질문 전략 원칙 (Y 분석 기반)
1. **평가기준과 직접 연관된 정보를 최우선으로 수집**
2. 자격요건 충족 여부를 확인할 수 있는 정보 수집
3. 핵심키워드와 관련된 회사의 강점 정보 수집
4. 자연스러운 대화체로 1개씩 질문 (면접처럼 묻지 말고, 친근하게)
5. 사용자 응답에 공감하며 다음 질문으로 자연스럽게 연결
6. Y 분석 결과와 무관한 정보는 과감히 생략

## 응답 형식
환영 메시지와 첫 질문을 포함한 자연스러운 대화 시작
- 환영 메시지에서 "이 공고의 핵심 평가 포인트"를 자연스럽게 언급
- 첫 질문은 회사명부터 시작하되, 왜 이 정보가 중요한지 Y 분석 결과와 연결`
      : `당신은 정부 지원사업 신청서 작성을 돕는 AI 어시스턴트입니다.
사용자가 신청하려는 공고(Y)를 분석하여, 필요한 회사 정보(Z)를 수집하기 위한 질문 전략을 수립합니다.

## 목표
1. 공고의 지원자격, 평가기준, 지원내용을 분석 (Y 분석)
2. 양질의 신청서 작성에 필요한 회사 정보(Z) 파악
3. 자연스러운 대화형 질문 전략 수립

## 회사 정보(Z) 필수 항목
- company_name: 회사명
- business_field: 사업 분야 (업종)
- founding_year: 설립 연도
- main_products: 주요 제품/서비스
- target_goal: 지원사업 목표 (왜 이 공고에 지원하는가?)

## 회사 정보(Z) 선택 항목 (공고 특성에 따라)
- business_registration_number: 사업자등록번호
- revenue: 매출액
- employee_count: 직원 수
- technology: 보유 기술/특허
- past_support: 과거 지원사업 수혜 경험
- additional_info: 기타 공고 특화 정보

## 질문 전략 원칙
1. 필수 정보부터 순차적으로 수집
2. 공고의 평가기준과 연관된 정보 우선 순위 부여
3. 자연스러운 대화체로 1개씩 질문 (면접처럼 묻지 말고, 친근하게)
4. 사용자 응답에 공감하며 다음 질문으로 자연스럽게 연결
5. 불필요한 정보는 과감히 생략 (공고와 무관한 경우)

## 응답 형식
환영 메시지와 첫 질문을 포함한 자연스러운 대화 시작`;

    const userPrompt = announcementAnalysis
      ? `다음은 Writing Analysis 단계에서 심층 분석한 공고 정보입니다:

공고 제목: ${announcementGuidelines.title}
주관 기관: ${announcementGuidelines.organization}
지원 대상: ${announcementGuidelines.target}
지원 규모: ${announcementGuidelines.scale}

공고 요약:
${announcementGuidelines.summary}

**중요: 위 공고에 대한 심층 분석 결과(Y Analysis)가 시스템 프롬프트에 제공되어 있습니다.**
이 분석 결과에는 자격요건, 평가기준, 핵심키워드, 작성전략이 포함되어 있습니다.

## 수행해야 할 작업:
1. **⭐ 최우선**: Y 분석 결과에 "과제별 상세 정보" 또는 "선택 가능한 과제 트랙"이 있는지 확인
   - **있다면 (과제가 2개 이상)**:
     - 환영 메시지에서 "이 공고는 여러 과제 중 하나를 선택하여 신청하는 방식입니다"라고 명확히 안내
     - 첫 번째 질문에서 **반드시 각 과제의 이름과 핵심 목표를 나열**한 후 선택하게 함
     - 예시 형식: 이 공고에는 다음 3가지 과제가 있습니다: 1. 과제1 이름 - 핵심 목표 한 줄 요약, 2. 과제2 이름 - 핵심 목표 한 줄 요약, 3. 과제3 이름 - 핵심 목표 한 줄 요약. 어떤 과제에 지원하실 계획이신가요?
   - **없다면 (과제가 1개 또는 과제 구분 없음)**: 기존 방식대로 회사명부터 질문

2. **Y 분석 결과를 기반으로** 이 공고에 최적화된 회사 정보(Z) 수집 전략 수립

3. 환영 메시지 작성:
   - 공고 이름 언급
   - Y 분석에서 도출된 "핵심 평가 포인트"를 자연스럽게 소개 (예: "이 공고는 특히 [핵심키워드]를 중점적으로 평가합니다")
   - **과제가 여러 개인 경우**: "여러 과제 중 하나를 선택하는 방식"이라는 점을 명확히 안내
   - 정보 수집 목적 설명 (약 3-4문장)

4. 첫 번째 질문 작성:
   - **⭐ 과제가 여러 개인 경우 (필수!)**:
     - 각 과제의 **이름**과 **핵심 목표**를 번호 매겨서 나열
     - "어떤 과제에 지원하실 계획이신가요?" 질문
     - 사용자가 과제명이나 번호로 선택할 수 있도록 명확히 제시
   - **과제가 1개인 경우**: 회사명부터 시작하되, Y 분석과 자연스럽게 연결

자연스럽고 친근한 톤으로 작성하되, Y 분석 결과가 신청서 작성에 어떻게 활용될지 사용자가 이해할 수 있도록 해주세요.`
      : `다음 공고를 분석하여 회사 정보 수집을 위한 웰컴 메시지와 첫 질문을 생성해주세요:

공고 제목: ${announcementGuidelines.title}
주관 기관: ${announcementGuidelines.organization}
지원 대상: ${announcementGuidelines.target}
지원 규모: ${announcementGuidelines.scale}
공고 요약:
${announcementGuidelines.summary}

위 공고를 분석하여:
1. 이 공고에 맞는 신청서를 작성하려면 어떤 회사 정보(Z)가 필요한지 파악
2. 환영 메시지 작성 (공고 이름 언급, 정보 수집 목적 설명, 약 2-3문장)
3. 첫 번째 질문 작성 (회사명부터 시작)

자연스럽고 친근한 톤으로 작성해주세요.`;

    // OpenAI GPT-4o-mini API 호출
    console.log('[DEBUG] Calling OpenAI GPT-4o-mini API...');
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
          {
            role: 'user',
            content: userPrompt,
          },
        ],
        max_tokens: 1024,
        temperature: 0.7,
      }),
    });

    if (!openaiResponse.ok) {
      const errorData = await openaiResponse.json().catch(() => ({}));
      console.error('[ERROR] OpenAI API error:', openaiResponse.status, openaiResponse.statusText, errorData);
      return NextResponse.json(
        { error: 'Failed to generate questions' },
        { status: 500 }
      );
    }

    console.log('[DEBUG] OpenAI API response received');
    const openaiData = await openaiResponse.json();
    console.log('[DEBUG] OpenAI response structure:', {
      hasChoices: !!openaiData.choices,
      choicesLength: openaiData.choices?.length || 0,
      hasMessage: !!openaiData.choices?.[0]?.message
    });

    if (!openaiData.choices || !Array.isArray(openaiData.choices) || openaiData.choices.length === 0) {
      console.error('[ERROR] Invalid OpenAI response structure:', openaiData);
      return NextResponse.json(
        { error: 'Invalid AI response structure' },
        { status: 500 }
      );
    }

    const welcomeMessage = openaiData.choices[0].message.content;

    console.log('Profile questions generated successfully');

    return NextResponse.json({
      success: true,
      welcome_message: welcomeMessage,
      announcement_summary: announcementGuidelines,
      required_fields: [
        'company_name',
        'business_field',
        'founding_year',
        'main_products',
        'target_goal',
      ],
      optional_fields: [
        'business_registration_number',
        'revenue',
        'employee_count',
        'technology',
        'past_support',
        'additional_info',
      ],
    });

  } catch (error) {
    console.error('[ERROR] Profile questions API error:', error);
    console.error('[ERROR] Error details:', {
      message: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : 'No stack trace',
      type: typeof error,
      errorObject: error
    });
    return NextResponse.json(
      {
        error: 'Failed to generate profile questions',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
