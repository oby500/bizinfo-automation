import { NextRequest, NextResponse } from 'next/server'

/**
 * 신청서 수정 API
 *
 * 사용자 피드백을 받아 신청서를 수정
 * - 수정권 차감
 * - FastAPI 백엔드로 수정 요청 프록시
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // FastAPI 백엔드 URL
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

    console.log('[Application Revise Proxy] 요청:', {
      backendUrl,
      announcement_id: body.announcement_id,
      source: body.source,
      revision_number: body.revision_number,
      feedback_length: body.feedback?.length,
    })

    // FastAPI로 프록시 (피드백 기반 수정)
    const response = await fetch(`${backendUrl}/api/application-writer/revise-with-feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('[Application Revise Proxy] FastAPI 오류:', {
        status: response.status,
        statusText: response.statusText,
        error: errorText,
      })

      return NextResponse.json(
        {
          detail: `FastAPI 오류: ${response.statusText}`,
          error: errorText
        },
        { status: response.status }
      )
    }

    const data = await response.json()

    console.log('[Application Revise Proxy] 성공:', {
      has_revised_content: !!data.revised_content,
      sections_count: data.revised_content?.sections?.length,
    })

    return NextResponse.json(data)

  } catch (error: any) {
    console.error('[Application Revise Proxy] 예외:', error)

    return NextResponse.json(
      {
        detail: '서버 오류가 발생했습니다.',
        error: error.message
      },
      { status: 500 }
    )
  }
}
