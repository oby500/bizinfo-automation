import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { auth } from '@/auth'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

    console.log('[Application Compose Proxy] Request:', {
      backendUrl,
      announcement_id: body.announcement_id,
      source: body.source,
      task_number: body.task_number,
      tier: body.tier,
      style: body.style,
      test_mode: body.test_mode,
    })

    const isTestMode = body.test_mode === true
    let userEmail: string

    if (isTestMode) {
      console.log('[Application Compose Proxy] Test mode - bypassing auth')
      userEmail = 'test@example.com'
    } else {
      const session = await auth()
      if (!session?.user?.email) {
        return NextResponse.json({ detail: 'Login required' }, { status: 401 })
      }
      userEmail = session.user.email
    }

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
    const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!
    const supabase = createClient(supabaseUrl, supabaseKey)

    let userId: number
    if (isTestMode) {
      userId = 1
    } else {
      const { data: userData, error: userError } = await supabase.from('users').select('id').eq('email', userEmail).single()
      if (userError || !userData) {
        return NextResponse.json({ detail: 'User not found' }, { status: 404 })
      }
      userId = userData.id
    }

    const tableName = body.source === 'kstartup' ? 'kstartup_complete' : 'bizinfo_complete'
    const { data: announcementData, error: dbError } = await supabase.from(tableName).select('writing_analysis, bsns_title').eq('announcement_id', body.announcement_id).single()

    if (dbError || !announcementData) {
      return NextResponse.json({ detail: 'Announcement not found: ' + body.announcement_id }, { status: 404 })
    }

    const analyzeCompanyResponse = await fetch(backendUrl + '/api/application-writer/analyze-company', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ announcement_analysis: announcementData.writing_analysis, company_info: body.company_profile }),
    })

    if (!analyzeCompanyResponse.ok) {
      const errorText = await analyzeCompanyResponse.text()
      return NextResponse.json({ detail: 'Company analysis failed', error: errorText }, { status: analyzeCompanyResponse.status })
    }

    const analyzeCompanyData = await analyzeCompanyResponse.json()
    const company_analysis = analyzeCompanyData.company_analysis

    const orderId = crypto.randomUUID()
    await supabase.from('orders').insert({
      id: orderId,
      user_id: userEmail,
      amount: body.tier === 'basic' ? 10000 : (body.tier === 'standard' ? 20000 : 30000),
      status: 'paid',
      tier: body.tier
    })

    // Use style from request body, default to 'story' for basic tier
    const requestedStyle = body.style || 'story'

    const backendRequest = {
      announcement_analysis: announcementData.writing_analysis,
      company_analysis: company_analysis,
      style: requestedStyle,
      tier: body.tier,
      user_id: userEmail,
      company_info: body.company_profile || {},
      order_id: orderId
    }

    // Use compose-sync for synchronous result
    const response = await fetch(backendUrl + '/api/application-writer/compose-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backendRequest),
    })

    if (!response.ok) {
      const errorText = await response.text()
      return NextResponse.json({ detail: 'FastAPI error', error: errorText }, { status: response.status })
    }

    const data = await response.json()

    console.log('[Application Compose Proxy] Success:', { documents_keys: data.documents ? Object.keys(data.documents) : [] })

    let applicationContent = {
      sections: [] as Array<{ title: string; content: string }>,
      html_content: null as string | null,
      plain_text: null as string | null,
    }

    const extractSections = (doc: any): Array<{ title: string; content: string }> => {
      const result: Array<{ title: string; content: string }> = []
      if (!doc) return result

      if (Array.isArray(doc.sections)) {
        for (const section of doc.sections) {
          if (section.title && section.content) {
            result.push({ title: section.title, content: section.content })
          }
        }
      } else if (doc.sections && typeof doc.sections === 'object') {
        for (const [title, content] of Object.entries(doc.sections)) {
          result.push({ title, content: String(content) })
        }
      }

      if (result.length === 0 && doc.content && typeof doc.content === 'string') {
        result.push({ title: 'Application Content', content: doc.content })
      }

      return result
    }

    // First try to get the requested style, then fallback to priority order
    const stylePriority = [requestedStyle, 'upgraded', 'professional', 'data', 'story', 'balanced', 'conservative', 'aggressive']
    for (const style of stylePriority) {
      const doc = data.documents?.[style]
      if (doc) {
        applicationContent.sections = extractSections(doc)
        if (applicationContent.sections.length > 0) break
      }
    }

    const primaryDoc = data.documents?.[requestedStyle] || data.documents?.upgraded || data.documents?.professional || data.documents?.data
    if (primaryDoc?.content && typeof primaryDoc.content === 'string') {
      applicationContent.plain_text = primaryDoc.content
    }

    console.log('[Application Compose Proxy] Transform complete:', {
      style: requestedStyle,
      sections_count: applicationContent.sections.length
    })

    return NextResponse.json({
      ...data,
      application_content: applicationContent,
      requested_style: requestedStyle,
    })

  } catch (error: any) {
    console.error('[Application Compose Proxy] Exception:', error)
    return NextResponse.json({ detail: 'Server error', error: error.message }, { status: 500 })
  }
}
