'use client'

/**
 * ApplicationWriter 컴포넌트 - 완전히 재작성
 *
 * 올바른 플로우:
 * 1. 티어 선택
 * 2. 크레딧 결제
 * 3. Writing Analysis API 호출
 * 4. TaskSelectionChatbot 표시
 * 5. 과제 선택
 * 6. 회사 정보 입력
 * 7. 신청서 생성
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, CheckCircle2, AlertCircle, CreditCard } from 'lucide-react'
import { TaskSelectionChatbot } from '@/components/TaskSelectionChatbot'
import { ProfileCollectionChatbot } from '@/components/ProfileCollectionChatbot'
import { ApplicationFeedbackChatbot } from '@/components/ApplicationFeedbackChatbot'
import { StyleResultsTabs, type ApplicationResult } from '@/components/StyleResultsTabs'

interface ApplicationWriterProps {
  announcementId: string
  announcementSource: 'kstartup' | 'bizinfo'
  announcementTitle: string
  testMode?: boolean  // 테스트 모드 - 인증 우회
}

type Step =
  | 'tier-select'
  | 'payment-processing'
  | 'writing-analysis-loading'
  | 'task-selection'
  | 'company-info'
  | 'generating'
  | 'feedback'     // 피드백 & 수정 단계
  | 'completed'

type Tier = 'basic' | 'standard' | 'premium'

interface WritingAnalysis {
  tasks?: Array<{
    task_number: number
    task_name: string
    description: string
    required_info: string[]
    evaluation_points: string[]
  }>
  common_required_info: string[]
  has_multiple_tasks: boolean
  recommended_task?: number
  form_type?: 'simple_registration' | 'evaluation_based' | 'business_plan'
}

// 양식 유형별 티어 추천 정보
const TIER_RECOMMENDATIONS: Record<string, {
  recommendedTier: Tier
  aiValue: 'low' | 'medium' | 'high'
  message: string
  description: string
}> = {
  simple_registration: {
    recommendedTier: 'basic',
    aiValue: 'low',
    message: '💡 단순 등록 양식입니다',
    description: '이 공고는 수강/참가 신청서 같은 단순 등록 양식입니다. 복잡한 평가 심사가 없어 Basic 티어로 충분합니다.'
  },
  evaluation_based: {
    recommendedTier: 'standard',
    aiValue: 'high',
    message: '🎯 평가 심사가 있는 공고입니다',
    description: '배점 기준과 평가 항목이 있어 AI가 전략적 작성을 도와드릴 수 있습니다. Standard 이상을 추천드립니다.'
  },
  business_plan: {
    recommendedTier: 'premium',
    aiValue: 'high',
    message: '📊 사업계획서 제출이 필요합니다',
    description: '복잡한 사업계획서 구조화가 필요합니다. Premium 티어의 심층 AI 분석이 효과적입니다.'
  }
}

export function ApplicationWriter({
  announcementId,
  announcementSource,
  announcementTitle,
  testMode = false,
}: ApplicationWriterProps) {
  const [step, setStep] = useState<Step>('tier-select')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 티어 선택
  const [selectedTier, setSelectedTier] = useState<Tier>('basic')

  // 크레딧 잔액
  const [creditBalance, setCreditBalance] = useState<number>(0)

  // Writing Analysis 결과
  const [writingAnalysis, setWritingAnalysis] = useState<WritingAnalysis | null>(null)

  // 선택한 과제
  const [selectedTask, setSelectedTask] = useState<number | null>(null)

  // 회사 정보
  const [companyInfo, setCompanyInfo] = useState<any>(null)

  // 생성된 신청서 배열 (스타일별)
  const [applications, setApplications] = useState<ApplicationResult[]>([])

  // 선택된 스타일
  const [selectedStyle, setSelectedStyle] = useState<string>('story')

  // 티어별 수정권
  const getTierRevisions = (tier: Tier): number => {
    const revisions = { basic: 1, standard: 3, premium: 7 }
    return revisions[tier]
  }

  // 양식 유형 (티어 추천용)
  const [formType, setFormType] = useState<'simple_registration' | 'evaluation_based' | 'business_plan' | null>(null)
  const [formTypeLoading, setFormTypeLoading] = useState(true)

  // 개발 모드 (테스트용)
  const DEV_MODE = process.env.NODE_ENV === 'development'

  /**
   * 컴포넌트 마운트 시 크레딧 잔액 조회 + 양식 유형 분석
   */
  useEffect(() => {
    if (DEV_MODE) {
      // 개발 모드: 충분한 크레딧 설정
      setCreditBalance(1000000)
      console.log('[ApplicationWriter] 개발 모드: 크레딧 1,000,000원 설정')
    } else {
      fetchCreditBalance()
    }

    // 양식 유형 분석 (티어 추천용)
    fetchFormType()
  }, [])

  /**
   * 양식 유형 분석 (빠른 분석, 캐시 활용)
   */
  const fetchFormType = async () => {
    setFormTypeLoading(true)
    try {
      console.log('[ApplicationWriter] 양식 유형 분석 시작')
      const response = await fetch('/api/writing-analysis/form-type', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          announcement_id: announcementId,
          source: announcementSource,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setFormType(data.form_type || 'evaluation_based')
        console.log('[ApplicationWriter] 양식 유형:', data.form_type)
      } else {
        // 실패 시 기본값
        setFormType('evaluation_based')
      }
    } catch (err) {
      console.warn('[ApplicationWriter] 양식 유형 분석 실패, 기본값 사용')
      setFormType('evaluation_based')
    } finally {
      setFormTypeLoading(false)
    }
  }

  /**
   * 크레딧 잔액 조회
   */
  const fetchCreditBalance = async () => {
    try {
      console.log('[ApplicationWriter] 크레딧 잔액 조회 시작')
      const response = await fetch('/api/revision-credits/balance')

      if (!response.ok) {
        throw new Error('크레딧 잔액 조회 실패')
      }

      const data = await response.json()
      setCreditBalance(data.balance || 0)
      console.log('[ApplicationWriter] 크레딧 잔액 조회 완료:', data.balance)
    } catch (err: any) {
      console.error('[ApplicationWriter] 크레딧 잔액 조회 실패:', err)
      // 에러 발생해도 진행 가능하도록 (잔액 0으로)
      setCreditBalance(0)
    }
  }

  /**
   * 티어별 가격
   */
  const getTierPrice = (tier: Tier): number => {
    const prices = {
      basic: 4900,
      standard: 8000,
      premium: 15000,
    }
    return prices[tier]
  }

  /**
   * 크레딧으로 결제
   */
  const handleCreditPayment = async () => {
    const tierPrice = getTierPrice(selectedTier)

    console.log('[ApplicationWriter] 버튼 클릭:', {
      selectedTier,
      tierPrice,
      creditBalance,
      willUseCredits: creditBalance >= tierPrice,
      DEV_MODE,
    })

    if (creditBalance < tierPrice) {
      setError(`크레딧이 부족합니다. (잔액: ${creditBalance}원, 필요: ${tierPrice}원)`)
      return
    }

    console.log('[ApplicationWriter] 크레딧으로 결제 진행')
    setError(null)
    setLoading(true)
    setStep('payment-processing')

    try {
      // DEV_MODE일 때는 크레딧 차감 API 우회
      if (DEV_MODE) {
        console.log('[ApplicationWriter] DEV_MODE: 크레딧 차감 API 우회')
      } else {
        // 크레딧 차감
        const response = await fetch('/api/revision-credits/deduct', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            amount: tierPrice,
            reason: `${selectedTier} tier application writer`,
          }),
        })

        if (!response.ok) {
          throw new Error('크레딧 차감 실패')
        }

        console.log('[ApplicationWriter] 크레딧 차감 완료')
      }

      console.log('[ApplicationWriter] Writing Analysis 호출 시작')

      // 결제 완료 → Writing Analysis 호출
      await fetchWritingAnalysis()
    } catch (err: any) {
      console.error('[ApplicationWriter] 결제 오류:', err)
      setError(err.message || '결제 중 오류가 발생했습니다.')
      setStep('tier-select')
      setLoading(false)
    }
  }

  /**
   * Writing Analysis API 호출
   */
  const fetchWritingAnalysis = async () => {
    setStep('writing-analysis-loading')
    setError(null)

    try {
      console.log('[ApplicationWriter] Writing Analysis API 호출:', {
        announcementId,
        source: announcementSource,
      })

      const response = await fetch('/api/writing-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          announcement_id: announcementId,
          source: announcementSource,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Writing Analysis 호출 실패')
      }

      const data = await response.json()
      console.log('[ApplicationWriter] Writing Analysis 완료:', data)

      setWritingAnalysis(data.writing_analysis)
      setStep('task-selection')
      setLoading(false)
    } catch (err: any) {
      console.error('[ApplicationWriter] Writing Analysis 실패:', err)
      setError(err.message || 'Writing Analysis 중 오류가 발생했습니다.')
      setStep('tier-select')
      setLoading(false)
    }
  }

  /**
   * 과제 선택 완료
   */
  const handleTaskSelected = (taskNumber: number | null, requiredInfo: string[]) => {
    console.log('[ApplicationWriter] 과제 선택:', taskNumber)
    setSelectedTask(taskNumber)
    setStep('company-info') // 회사 정보 입력 단계로 전환
  }

  /**
   * 티어별 생성할 스타일 목록
   */
  const getStylesForTier = (tier: Tier): string[] => {
    const tierStyles: Record<Tier, string[]> = {
      basic: ['story'],
      standard: ['story', 'data', 'aggressive'],
      premium: ['story', 'data', 'aggressive', 'balanced', 'strategic'],
    }
    return tierStyles[tier]
  }

  /**
   * 회사 정보 입력 완료 → 신청서 생성 (다중 스타일)
   */
  const handleCompanyInfoSubmit = async (info: any) => {
    console.log('[ApplicationWriter] 회사 정보 제출:', info)
    setCompanyInfo(info)
    setStep('generating')
    setLoading(true)
    setError(null)

    try {
      const styles = getStylesForTier(selectedTier)
      console.log('[ApplicationWriter] 신청서 생성 시작 - 스타일:', styles)

      const generatedApplications: ApplicationResult[] = []

      // 각 스타일별로 신청서 생성
      for (let i = 0; i < styles.length; i++) {
        const style = styles[i]
        console.log(`[ApplicationWriter] 스타일 ${i + 1}/${styles.length}: ${style}`)

        const response = await fetch('/api/application-writer/compose', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            announcement_id: announcementId,
            source: announcementSource,
            task_number: selectedTask,
            company_profile: info,
            tier: selectedTier,
            style: style,  // 스타일 지정
            test_mode: testMode,
          }),
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `${style} 스타일 신청서 생성 실패`)
        }

        const data = await response.json()
        console.log(`[ApplicationWriter] ${style} 스타일 생성 완료`)

        // ApplicationResult 형식으로 변환
        const content = data.application_content && data.application_content.sections?.length > 0
          ? data.application_content
          : {
              sections: data.sections || [],
              plain_text: data.plain_text || data.application_content?.plain_text || null,
            }

        // 글자 수 계산
        let charCount = 0
        if (content.sections) {
          content.sections.forEach((section: any) => {
            if (section.subsections) {
              section.subsections.forEach((sub: any) => {
                charCount += (sub.content || '').length
              })
            } else {
              charCount += (section.content || '').length
            }
          })
        }

        generatedApplications.push({
          style,
          styleName: data.style_name || style,
          styleType: ['balanced', 'strategic', 'trusted', 'expert'].includes(style) ? 'combination' : 'base',
          styleRank: i + 1,
          isRecommended: i === 0,  // 첫 번째 스타일을 추천으로 표시
          content,
          charCount,
          sectionCount: content.sections?.length || 0,
        })
      }

      console.log('[ApplicationWriter] 전체 신청서 생성 완료:', generatedApplications.length, '개')
      setApplications(generatedApplications)
      setSelectedStyle(generatedApplications[0]?.style || 'story')

      // DB에 저장
      await saveApplicationsToDb(generatedApplications)

      // 피드백 단계로 이동
      setStep('feedback')
      setLoading(false)
    } catch (err: any) {
      console.error('[ApplicationWriter] 신청서 생성 오류:', err)
      setError(err.message || '신청서 생성 중 오류가 발생했습니다.')
      setStep('company-info')
      setLoading(false)
    }
  }

  /**
   * 생성된 신청서들을 DB에 저장
   */
  const saveApplicationsToDb = async (apps: ApplicationResult[]) => {
    try {
      const applicationsToSave = apps.map(app => ({
        announcementId,
        announcementSource,
        announcementTitle,
        tier: selectedTier,
        style: app.style,
        styleName: app.styleName,
        styleType: app.styleType,
        styleRank: app.styleRank,
        isRecommended: app.isRecommended,
        content: app.content,
        charCount: app.charCount,
        sectionCount: app.sectionCount,
      }))

      const response = await fetch('/api/applications', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ applications: applicationsToSave }),
      })

      if (!response.ok) {
        console.warn('[ApplicationWriter] 신청서 DB 저장 실패:', await response.text())
      } else {
        const result = await response.json()
        console.log('[ApplicationWriter] 신청서 DB 저장 완료:', result)
      }
    } catch (err) {
      console.warn('[ApplicationWriter] 신청서 DB 저장 중 오류:', err)
      // 저장 실패해도 진행
    }
  }

  /**
   * 피드백 수정 완료 시 콜백 - 특정 스타일의 신청서 업데이트
   */
  const handleRevisionComplete = (newContent: any) => {
    console.log('[ApplicationWriter] 수정 완료:', newContent)
    setApplications(prev =>
      prev.map(app =>
        app.style === selectedStyle
          ? { ...app, content: newContent }
          : app
      )
    )
  }

  /**
   * 스타일 선택 변경
   */
  const handleStyleSelect = (style: string) => {
    console.log('[ApplicationWriter] 스타일 선택:', style)
    setSelectedStyle(style)
  }

  /**
   * 최종 완료
   */
  const handleFinalize = () => {
    console.log('[ApplicationWriter] 최종 완료')
    setStep('completed')
  }

  /**
   * 현재 선택된 스타일의 신청서 가져오기
   */
  const getCurrentApplication = () => {
    return applications.find(app => app.style === selectedStyle)
  }

  /**
   * ApplicationResult의 content를 ApplicationFeedbackChatbot에서 요구하는 형식으로 변환
   */
  const convertToFeedbackContent = (appContent: ApplicationResult['content']) => {
    // sections 변환: subsections가 있으면 각각을 섹션으로 펼침
    const flatSections: Array<{ title: string; content: string }> = []

    if (appContent.sections) {
      appContent.sections.forEach(section => {
        if (section.subsections && section.subsections.length > 0) {
          // subsections를 개별 섹션으로 펼침
          section.subsections.forEach(sub => {
            flatSections.push({
              title: `${section.title} - ${sub.title}`,
              content: sub.content,
            })
          })
        } else if (section.content) {
          flatSections.push({
            title: section.title,
            content: section.content,
          })
        }
      })
    }

    return {
      sections: flatSections,
      plain_text: appContent.plain_text,
    }
  }

  return (
    <Card className="mt-8">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          🤖 AI 신청서 자동 작성
        </CardTitle>
        <CardDescription>
          {announcementTitle}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* 에러 메시지 */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Step 1: 티어 선택 */}
        {step === 'tier-select' && (
          <div className="space-y-4">
            {/* 로딩 중 */}
            {formTypeLoading && (
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center gap-2 text-gray-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">공고 유형 분석 중...</span>
                </div>
              </div>
            )}

            {/* 단순 등록 양식 - AI 서비스 대상 아님 */}
            {!formTypeLoading && formType === 'simple_registration' && (
              <div className="space-y-4">
                <div className="p-6 bg-gray-50 rounded-lg border border-gray-200">
                  <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                    📋 이 공고는 단순 등록 양식입니다
                  </h3>

                  <p className="text-gray-700 mb-4">
                    이 공고는 <strong>수강 신청서/참가 신청서</strong> 형태로,<br />
                    이름·연락처·소속 등 기본 정보만 입력하면 됩니다.
                  </p>

                  <div className="bg-white p-4 rounded-lg border mb-4">
                    <h4 className="font-medium text-gray-800 mb-2">AI가 도와줄 수 있는 것</h4>
                    <ul className="text-sm text-gray-600 space-y-1">
                      <li className="flex items-center gap-2">
                        <span className="text-red-500">✕</span> 평가 심사 없음 → 전략적 작성 불필요
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="text-red-500">✕</span> 사업계획서 작성 불필요
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="text-red-500">✕</span> 복잡한 서류 준비 불필요
                      </li>
                    </ul>
                  </div>

                  <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                    <p className="text-blue-800 font-medium">
                      💡 직접 신청하시는 것을 권장드립니다
                    </p>
                    <p className="text-sm text-blue-600 mt-1">
                      공고 페이지에서 바로 신청서를 작성하시면 됩니다.
                    </p>
                  </div>
                </div>

                <Button
                  variant="outline"
                  className="w-full"
                  size="lg"
                  onClick={() => window.history.back()}
                >
                  ← 공고 상세로 돌아가기
                </Button>
              </div>
            )}

            {/* 평가 기반 / 사업계획서 양식 - AI 서비스 제공 */}
            {!formTypeLoading && formType && formType !== 'simple_registration' && (
              <>
                {/* 양식 유형 안내 배너 */}
                <div className={`p-4 rounded-lg border ${
                  formType === 'business_plan'
                    ? 'bg-purple-50 border-purple-200'
                    : 'bg-blue-50 border-blue-200'
                }`}>
                  <h3 className="font-semibold mb-1">
                    {TIER_RECOMMENDATIONS[formType]?.message}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {TIER_RECOMMENDATIONS[formType]?.description}
                  </p>
                  <p className="text-xs text-blue-600 mt-2">
                    AI 지원 가치: 높음 - 전략적 작성 도움 가능
                  </p>
                </div>

                <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h3 className="font-semibold mb-2">💳 크레딧 잔액</h3>
                  <p className="text-2xl font-bold text-blue-600">
                    {creditBalance.toLocaleString()}원
                  </p>
                </div>

                <div className="grid md:grid-cols-3 gap-4">
                  {/* Basic 티어 */}
                  <Card
                    className={`cursor-pointer transition-all ${
                      selectedTier === 'basic' ? 'ring-2 ring-blue-500' : ''
                    }`}
                    onClick={() => setSelectedTier('basic')}
                  >
                    <CardHeader>
                      <CardTitle>베이직</CardTitle>
                      <CardDescription>₩4,900</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm space-y-1">
                      <p>• 📖 스토리형 신청서 1개</p>
                      <p>• 수정권 1회</p>
                      <p>• 품질 검사</p>
                      <p className="text-xs text-gray-500 mt-2">감성적 스토리텔링 중심</p>
                    </CardContent>
                  </Card>

                  {/* Standard 티어 */}
                  <Card
                    className={`cursor-pointer transition-all ${
                      selectedTier === 'standard' ? 'ring-2 ring-blue-500' : ''
                    } ${formType === 'evaluation_based' ? 'ring-2 ring-blue-400' : ''}`}
                    onClick={() => setSelectedTier('standard')}
                  >
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        스탠다드
                        {formType === 'evaluation_based' && (
                          <Badge className="bg-blue-500">추천</Badge>
                        )}
                        {!formType && <Badge variant="secondary">인기</Badge>}
                      </CardTitle>
                      <CardDescription>₩8,000</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm space-y-1">
                      <p>• 3가지 스타일 신청서</p>
                      <p>• 수정권 3회</p>
                      <p>• AI가 최적 스타일 추천</p>
                      <p className="text-xs text-gray-500 mt-2">📖스토리 📊데이터 🚀적극 중 선택</p>
                    </CardContent>
                  </Card>

                  {/* Premium 티어 */}
                  <Card
                    className={`cursor-pointer transition-all ${
                      selectedTier === 'premium' ? 'ring-2 ring-blue-500' : ''
                    } ${formType === 'business_plan' ? 'ring-2 ring-purple-400' : ''}`}
                    onClick={() => setSelectedTier('premium')}
                  >
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        프리미엄
                        {formType === 'business_plan' && (
                          <Badge className="bg-purple-500">추천</Badge>
                        )}
                      </CardTitle>
                      <CardDescription>₩15,000</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm space-y-1">
                      <p>• 5가지 스타일 신청서</p>
                      <p>• 수정권 7회</p>
                      <p>• 베이스 3 + 조합 2 스타일</p>
                      <p className="text-xs text-gray-500 mt-2">⚖️균형형 🎯전략형 등 조합 포함</p>
                    </CardContent>
                  </Card>
                </div>

                <Button
                  onClick={handleCreditPayment}
                  disabled={loading || creditBalance < getTierPrice(selectedTier)}
                  className="w-full"
                  size="lg"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      처리 중...
                    </>
                  ) : (
                    <>
                      <CreditCard className="mr-2 h-4 w-4" />
                      크레딧으로 결제 ({getTierPrice(selectedTier).toLocaleString()}원)
                    </>
                  )}
                </Button>

                {creditBalance < getTierPrice(selectedTier) && (
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      크레딧이 부족합니다. 충전 후 이용해주세요.
                    </AlertDescription>
                  </Alert>
                )}
              </>
            )}
          </div>
        )}

        {/* Step 2: 결제 처리 중 */}
        {step === 'payment-processing' && (
          <div className="text-center py-8">
            <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-500 mb-4" />
            <p className="text-lg font-semibold">결제 처리 중...</p>
          </div>
        )}

        {/* Step 3: Writing Analysis 로딩 */}
        {step === 'writing-analysis-loading' && (
          <div className="text-center py-8">
            <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-500 mb-4" />
            <p className="text-lg font-semibold">공고 심화 분석 중...</p>
            <p className="text-sm text-gray-600 mt-2">
              Claude Sonnet 4.5가 공고를 깊이 분석하고 있습니다 (약 7분 소요)
            </p>
          </div>
        )}

        {/* Step 4: 과제 선택 (TaskSelectionChatbot) */}
        {step === 'task-selection' && writingAnalysis && (
          <TaskSelectionChatbot
            announcementTitle={announcementTitle}
            writingAnalysis={writingAnalysis}
            onTaskSelected={handleTaskSelected}
            onClose={() => setStep('tier-select')}
          />
        )}

        {/* Step 5: 회사 정보 입력 */}
        {step === 'company-info' && writingAnalysis && (
          <ProfileCollectionChatbot
            announcementId={announcementId}
            announcementSource={announcementSource}
            announcementTitle={announcementTitle}
            announcementAnalysis={writingAnalysis}
            selectedTaskNumber={selectedTask}
            requiredInfoList={writingAnalysis.common_required_info || []}
            onClose={() => setStep('task-selection')}
            onComplete={handleCompanyInfoSubmit}
          />
        )}

        {/* Step 6: 신청서 생성 중 */}
        {step === 'generating' && (
          <div className="text-center py-8">
            <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-500 mb-4" />
            <p className="text-lg font-semibold">신청서 생성 중...</p>
            <p className="text-sm text-gray-600 mt-2">
              AI가 최적화된 신청서를 작성하고 있습니다...
            </p>
          </div>
        )}

        {/* Step 7: 피드백 & 수정 - 스타일별 탭으로 표시 */}
        {step === 'feedback' && applications.length > 0 && (
          <div className="space-y-6">
            {/* 스타일별 결과 탭 */}
            <StyleResultsTabs
              applications={applications}
              tier={selectedTier}
              onSelectStyle={handleStyleSelect}
              selectedStyle={selectedStyle}
            />

            {/* 수정 요청 섹션 */}
            {getCurrentApplication() && (
              <ApplicationFeedbackChatbot
                announcementId={announcementId}
                announcementSource={announcementSource}
                announcementTitle={announcementTitle}
                applicationContent={convertToFeedbackContent(getCurrentApplication()!.content)}
                tier={selectedTier}
                remainingRevisions={getTierRevisions(selectedTier)}
                onRevisionComplete={handleRevisionComplete}
                onClose={() => setStep('generating')}
                onFinalize={handleFinalize}
              />
            )}
          </div>
        )}

        {/* Step 8: 완료 */}
        {step === 'completed' && (
          <div className="space-y-6">
            <Alert className="bg-green-50 border-green-200">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="font-semibold text-green-800">
                {applications.length > 1
                  ? `${applications.length}가지 스타일의 신청서 작성이 완료되었습니다! 🎉`
                  : '신청서 작성이 완료되었습니다! 🎉'
                }
              </AlertDescription>
            </Alert>

            {/* 스타일별 결과 탭 */}
            {applications.length > 0 && (
              <StyleResultsTabs
                applications={applications}
                tier={selectedTier}
                onSelectStyle={handleStyleSelect}
                selectedStyle={selectedStyle}
              />
            )}

            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h4 className="font-semibold mb-2">다음 단계</h4>
              <ul className="text-sm text-gray-700 space-y-1">
                <li>• 각 스타일의 신청서를 비교해보세요</li>
                <li>• 마음에 드는 스타일의 신청서를 다운로드하세요</li>
                <li>• 공고 사이트에서 직접 신청서를 제출하세요</li>
                <li>• 마이페이지에서 작성 내역을 확인할 수 있습니다</li>
              </ul>
            </div>

            <Button
              onClick={() => window.location.href = '/mypage/applications'}
              className="w-full"
            >
              작성 내역 확인하기
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
