'use client'

/**
 * ApplicationWriter 컴포넌트
 *
 * AI 신청서 자동 작성 메인 컴포넌트
 * - 공고 분석 (Claude Sonnet 4.5)
 * - 회사 정보 입력 (Z)
 * - 티어 선택 (Basic/Standard/Premium)
 * - 신청서 생성 (GPT-4o)
 * - 진행률 표시 및 다운로드
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, CheckCircle2, AlertCircle, Download } from 'lucide-react'

interface Announcement {
  announcement_id: string
  title: string
  organization: string
  end_date: string
  status: string
}

interface ApplicationWriterProps {
  announcement: Announcement
}

type Step = 'analyze' | 'company-info' | 'tier-select' | 'generating' | 'completed'

interface AnalysisResult {
  analysis_id: string
  analysis: {
    자격요건: any[]
    평가기준: any[]
    심사위원_프로파일: any
    핵심키워드: any
    경쟁강도: any
    작성전략: any
    _metadata: {
      cost_usd: number
      cost_krw: number
    }
  }
}

interface CompanyAnalysis {
  analysis_id: string
  company_analysis: {
    강점분석: any[]
    약점분석: any[]
    차별화포인트: any[]
    리스크체크: any
    최종전략: any
    _metadata: {
      cost_usd: number
      cost_krw: number
    }
  }
}

export function ApplicationWriter({ announcement }: ApplicationWriterProps) {
  const [step, setStep] = useState<Step>('analyze')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 공고 분석 결과
  const [announcementAnalysis, setAnnouncementAnalysis] = useState<AnalysisResult | null>(null)

  // 회사 분석 결과
  const [companyAnalysis, setCompanyAnalysis] = useState<CompanyAnalysis | null>(null)

  // 회사 정보 (Z)
  const [companyInfo, setCompanyInfo] = useState<any>(null)

  // 선택한 티어
  const [selectedTier, setSelectedTier] = useState<'basic' | 'standard' | 'premium'>('basic')

  // 신청서 생성 ID
  const [applicationId, setApplicationId] = useState<string | null>(null)

  // 생성 진행률
  const [progress, setProgress] = useState(0)
  const [currentStepText, setCurrentStepText] = useState('')

  // 생성 완료된 문서들
  const [documents, setDocuments] = useState<any[]>([])

  /**
   * Step 1: 공고 분석
   */
  const analyzeAnnouncement = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/application/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          announcement_id: announcement.announcement_id,
          source: 'kstartup', // or 'bizinfo'
          force_refresh: false
        })
      })

      if (!response.ok) {
        throw new Error('공고 분석에 실패했습니다.')
      }

      const data: AnalysisResult = await response.json()
      setAnnouncementAnalysis(data)
      setStep('company-info')
    } catch (err: any) {
      setError(err.message || '공고 분석 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Step 2: 회사 분석 (회사 정보 입력 후)
   */
  const analyzeCompany = async (companyData: any) => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/application/analyze-company', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          announcement_analysis: announcementAnalysis?.analysis,
          company_info: companyData
        })
      })

      if (!response.ok) {
        throw new Error('회사 분석에 실패했습니다.')
      }

      const data: CompanyAnalysis = await response.json()
      setCompanyAnalysis(data)
      setCompanyInfo(companyData)
      setStep('tier-select')
    } catch (err: any) {
      setError(err.message || '회사 분석 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Step 3: 신청서 생성
   */
  const generateApplication = async () => {
    setLoading(true)
    setError(null)

    try {
      // TODO: 실제 user_id는 세션에서 가져와야 함
      const userId = 'test-user-id'

      const response = await fetch('/api/application/compose', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          announcement_analysis: announcementAnalysis?.analysis,
          company_analysis: companyAnalysis?.company_analysis,
          style: 'balanced', // 기본 스타일 (티어에 따라 여러 개 생성됨)
          tier: selectedTier,
          user_id: userId
        })
      })

      if (!response.ok) {
        throw new Error('신청서 생성에 실패했습니다.')
      }

      const data = await response.json()
      setApplicationId(data.application_id)
      setStep('generating')

      // 폴링 시작
      startPolling(data.application_id)
    } catch (err: any) {
      setError(err.message || '신청서 생성 중 오류가 발생했습니다.')
      setLoading(false)
    }
  }

  /**
   * 진행 상태 폴링 (2초마다)
   */
  const startPolling = (appId: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/api/application/status/${appId}`)

        if (!response.ok) {
          clearInterval(interval)
          setError('진행 상태 확인에 실패했습니다.')
          setLoading(false)
          return
        }

        const data = await response.json()
        setProgress(data.progress)
        setCurrentStepText(data.current_step || '')

        if (data.status === 'completed') {
          clearInterval(interval)
          setDocuments(data.documents)
          setStep('completed')
          setLoading(false)
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setError(data.error || '신청서 생성에 실패했습니다.')
          setLoading(false)
        }
      } catch (err: any) {
        clearInterval(interval)
        setError('진행 상태 확인 중 오류가 발생했습니다.')
        setLoading(false)
      }
    }, 2000) // 2초마다 폴링
  }

  /**
   * 다운로드
   */
  const downloadApplication = async (format: 'docx' | 'pdf' | 'hwp' = 'docx') => {
    if (!applicationId) return

    try {
      const response = await fetch(`/api/application/download/${applicationId}?format=${format}`)

      if (!response.ok) {
        throw new Error('다운로드에 실패했습니다.')
      }

      const data = await response.json()

      // TODO: 실제 다운로드 URL로 리다이렉트
      window.open(data.download_url, '_blank')
    } catch (err: any) {
      setError(err.message || '다운로드 중 오류가 발생했습니다.')
    }
  }

  return (
    <Card className="mt-8">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          🤖 AI 신청서 자동 작성
        </CardTitle>
        <CardDescription>
          Claude Sonnet 4.5 + GPT-4o로 전문가 수준의 신청서를 자동 작성합니다
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

        {/* Step 1: 공고 분석 */}
        {step === 'analyze' && (
          <div className="space-y-4">
            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="font-semibold mb-2">📋 공고 정보</h3>
              <p className="text-sm text-gray-700">{announcement.title}</p>
              <p className="text-sm text-gray-500 mt-1">
                주관: {announcement.organization} | 마감: {announcement.end_date}
              </p>
            </div>

            <Button
              onClick={analyzeAnnouncement}
              disabled={loading}
              className="w-full"
              size="lg"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  공고 분석 중...
                </>
              ) : (
                '1단계: 공고 분석 시작'
              )}
            </Button>

            <p className="text-xs text-gray-500 text-center">
              Claude Sonnet 4.5가 공고문을 상세 분석합니다 (약 10-20초 소요)
            </p>
          </div>
        )}

        {/* Step 2: 회사 정보 입력 */}
        {step === 'company-info' && announcementAnalysis && (
          <div className="space-y-4">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                공고 분석 완료! 비용: ₩{announcementAnalysis.analysis._metadata.cost_krw}
              </AlertDescription>
            </Alert>

            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <h3 className="font-semibold mb-2">✅ 분석 완료</h3>
              <div className="text-sm space-y-1">
                <p>• 자격요건: {announcementAnalysis.analysis.자격요건.length}개 항목</p>
                <p>• 평가기준: {announcementAnalysis.analysis.평가기준.length}개 항목</p>
                <p>• 작성 전략 수립 완료</p>
              </div>
            </div>

            {/* TODO: 실제 회사 정보 입력 폼 컴포넌트 */}
            <div className="p-4 border rounded-lg">
              <h3 className="font-semibold mb-4">2단계: 회사 정보 입력</h3>
              <p className="text-sm text-gray-600 mb-4">
                회사 정보 입력 폼이 여기에 표시됩니다.
              </p>

              {/* 임시 버튼 (실제로는 폼 제출 후) */}
              <Button
                onClick={() => {
                  // 임시 테스트 데이터
                  const testCompanyData = {
                    회사정보: {
                      상호: '테스트 회사',
                      사업자번호: '123-45-67890',
                      설립일: '2020-01-01',
                      직원수: 10,
                      업종: '제조업'
                    },
                    사업내용: {
                      주력제품: 'AI 솔루션',
                      기술분야: ['인공지능', '자동화']
                    },
                    사업계획: {
                      자금계획: {
                        총사업비: 100000000,
                        자부담: 30000000,
                        정부지원_희망액: 70000000,
                        용도: {
                          연구개발: 50000000,
                          마케팅: 30000000,
                          인력채용: 20000000
                        }
                      }
                    }
                  }
                  analyzeCompany(testCompanyData)
                }}
                disabled={loading}
                className="w-full"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    회사 분석 중...
                  </>
                ) : (
                  '회사 정보 제출 및 분석'
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: 티어 선택 */}
        {step === 'tier-select' && companyAnalysis && (
          <div className="space-y-4">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                회사 분석 완료! 강점 {companyAnalysis.company_analysis.강점분석.length}개,
                약점 {companyAnalysis.company_analysis.약점분석.length}개 파악
              </AlertDescription>
            </Alert>

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
                  <p>• 신청서 1개</p>
                  <p>• 수정권 1회</p>
                  <p>• 품질 검사</p>
                </CardContent>
              </Card>

              {/* Standard 티어 */}
              <Card
                className={`cursor-pointer transition-all ${
                  selectedTier === 'standard' ? 'ring-2 ring-blue-500' : ''
                }`}
                onClick={() => setSelectedTier('standard')}
              >
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    스탠다드
                    <Badge variant="secondary">추천</Badge>
                  </CardTitle>
                  <CardDescription>₩14,900</CardDescription>
                </CardHeader>
                <CardContent className="text-sm space-y-1">
                  <p>• 신청서 3개</p>
                  <p>• 수정권 3회</p>
                  <p>• AI 추천 자동</p>
                  <p>• 공고 분석</p>
                </CardContent>
              </Card>

              {/* Premium 티어 */}
              <Card
                className={`cursor-pointer transition-all ${
                  selectedTier === 'premium' ? 'ring-2 ring-blue-500' : ''
                }`}
                onClick={() => setSelectedTier('premium')}
              >
                <CardHeader>
                  <CardTitle>프리미엄</CardTitle>
                  <CardDescription>₩29,900</CardDescription>
                </CardHeader>
                <CardContent className="text-sm space-y-1">
                  <p>• 신청서 5개</p>
                  <p>• 수정권 7회</p>
                  <p>• AI 심층 추천</p>
                  <p>• 맞춤 조합</p>
                </CardContent>
              </Card>
            </div>

            <Button
              onClick={generateApplication}
              disabled={loading}
              className="w-full"
              size="lg"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  생성 시작 중...
                </>
              ) : (
                `${selectedTier === 'basic' ? '베이직' : selectedTier === 'standard' ? '스탠다드' : '프리미엄'} 신청서 생성 시작`
              )}
            </Button>
          </div>
        )}

        {/* Step 4: 생성 중 */}
        {step === 'generating' && (
          <div className="space-y-4">
            <div className="text-center">
              <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-500 mb-4" />
              <h3 className="font-semibold text-lg mb-2">신청서 생성 중...</h3>
              <p className="text-sm text-gray-600">
                {currentStepText === 'analyzing' && 'AI가 공고와 회사 정보를 재분석 중입니다...'}
                {currentStepText === 'generating' && 'GPT-4o가 신청서를 작성 중입니다...'}
                {currentStepText === 'finalizing' && '최종 검토 및 품질 검사 중입니다...'}
                {!currentStepText && '준비 중입니다...'}
              </p>
            </div>

            <Progress value={progress} className="w-full" />
            <p className="text-center text-sm text-gray-500">{progress}% 완료</p>
          </div>
        )}

        {/* Step 5: 완료 */}
        {step === 'completed' && (
          <div className="space-y-4">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription className="font-semibold">
                신청서 생성 완료! 🎉
              </AlertDescription>
            </Alert>

            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <h3 className="font-semibold mb-2">생성된 신청서</h3>
              <p className="text-sm">
                {selectedTier === 'basic' && '1개의 신청서가 생성되었습니다.'}
                {selectedTier === 'standard' && '3개의 신청서가 생성되었습니다.'}
                {selectedTier === 'premium' && '5개의 신청서가 생성되었습니다.'}
              </p>
            </div>

            <div className="flex gap-2">
              <Button
                onClick={() => downloadApplication('docx')}
                className="flex-1"
              >
                <Download className="mr-2 h-4 w-4" />
                DOCX 다운로드
              </Button>
              <Button
                onClick={() => downloadApplication('pdf')}
                variant="outline"
                className="flex-1"
              >
                <Download className="mr-2 h-4 w-4" />
                PDF 다운로드
              </Button>
            </div>

            <p className="text-xs text-gray-500 text-center">
              문서함에서 언제든지 다시 다운로드할 수 있습니다.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
