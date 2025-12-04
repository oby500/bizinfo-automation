'use client'

/**
 * StyleResultsTabs - 스타일별 신청서 결과 탭 컴포넌트
 *
 * 티어별로 생성된 다양한 스타일의 신청서를 탭으로 표시
 * - BASIC: 1개 (story 고정)
 * - STANDARD: 3개 (AI 라우터 선택)
 * - PREMIUM: 5개 (베이스 3 + 조합 2)
 */

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Copy, Download, Star, Check } from 'lucide-react'

// 스타일 정보 매핑
const STYLE_INFO: Record<string, {
  name: string
  icon: string
  description: string
  type: 'base' | 'combination'
}> = {
  story: {
    name: '스토리형',
    icon: '📖',
    description: '스토리텔링 중심, 감성적 어필',
    type: 'base'
  },
  data: {
    name: '데이터형',
    icon: '📊',
    description: '데이터/수치 중심, 객관적 근거',
    type: 'base'
  },
  aggressive: {
    name: '적극형',
    icon: '🚀',
    description: '도전적 어조, 야심찬 목표',
    type: 'base'
  },
  conservative: {
    name: '안정형',
    icon: '🛡️',
    description: '신뢰 중심, 리스크 관리',
    type: 'base'
  },
  professional: {
    name: '전문형',
    icon: '🎓',
    description: '전문적/학술적 어조',
    type: 'base'
  },
  balanced: {
    name: '균형형',
    icon: '⚖️',
    description: '스토리와 데이터의 균형',
    type: 'combination'
  },
  strategic: {
    name: '전략형',
    icon: '🎯',
    description: '데이터 기반 공격적 전략',
    type: 'combination'
  },
  trusted: {
    name: '신뢰형',
    icon: '🤝',
    description: '신뢰를 주는 스토리',
    type: 'combination'
  },
  expert: {
    name: '전문가형',
    icon: '🔬',
    description: '전문가적 데이터 분석',
    type: 'combination'
  },
}

interface ApplicationResult {
  style: string
  styleName?: string
  styleType?: 'base' | 'combination'
  styleRank?: number
  isRecommended?: boolean
  content: {
    sections?: Array<{
      title: string
      content?: string
      subsections?: Array<{
        title: string
        content: string
      }>
    }>
    plain_text?: string
  }
  charCount?: number
  sectionCount?: number
}

interface StyleResultsTabsProps {
  applications: ApplicationResult[]
  tier: 'basic' | 'standard' | 'premium'
  onSelectStyle?: (style: string) => void
  selectedStyle?: string
}

export function StyleResultsTabs({
  applications,
  tier,
  onSelectStyle,
  selectedStyle: externalSelectedStyle,
}: StyleResultsTabsProps) {
  const [internalSelectedStyle, setInternalSelectedStyle] = useState(
    applications[0]?.style || 'story'
  )
  const [copiedStyle, setCopiedStyle] = useState<string | null>(null)

  const selectedStyle = externalSelectedStyle || internalSelectedStyle

  const handleTabChange = (style: string) => {
    setInternalSelectedStyle(style)
    onSelectStyle?.(style)
  }

  const handleCopy = async (app: ApplicationResult) => {
    const text = getPlainText(app)
    await navigator.clipboard.writeText(text)
    setCopiedStyle(app.style)
    setTimeout(() => setCopiedStyle(null), 2000)
  }

  const handleDownload = (app: ApplicationResult) => {
    const text = getPlainText(app)
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `신청서_${STYLE_INFO[app.style]?.name || app.style}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const getPlainText = (app: ApplicationResult): string => {
    if (app.content.plain_text) return app.content.plain_text

    let text = ''
    app.content.sections?.forEach(section => {
      text += `\n## ${section.title}\n\n`
      if (section.subsections) {
        section.subsections.forEach(sub => {
          text += `### ${sub.title}\n${sub.content}\n\n`
        })
      } else if (section.content) {
        text += `${section.content}\n\n`
      }
    })
    return text.trim()
  }

  const getStyleInfo = (style: string) => {
    return STYLE_INFO[style] || {
      name: style,
      icon: '📝',
      description: '기본 스타일',
      type: 'base' as const
    }
  }

  // 단일 스타일 (BASIC)
  if (applications.length === 1) {
    const app = applications[0]
    const styleInfo = getStyleInfo(app.style)

    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              {styleInfo.icon} {styleInfo.name} 스타일
            </CardTitle>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleCopy(app)}
              >
                {copiedStyle === app.style ? (
                  <><Check className="h-4 w-4 mr-1" /> 복사됨</>
                ) : (
                  <><Copy className="h-4 w-4 mr-1" /> 복사</>
                )}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDownload(app)}
              >
                <Download className="h-4 w-4 mr-1" /> 다운로드
              </Button>
            </div>
          </div>
          <p className="text-sm text-gray-600">{styleInfo.description}</p>
        </CardHeader>
        <CardContent>
          <ApplicationContent application={app} />
        </CardContent>
      </Card>
    )
  }

  // 다중 스타일 (STANDARD, PREMIUM)
  return (
    <div className="space-y-4">
      {/* 스타일 안내 */}
      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
        <h4 className="font-semibold text-blue-800 mb-2">
          {tier === 'standard' ? '3가지' : '5가지'} 스타일로 작성되었습니다
        </h4>
        <p className="text-sm text-blue-700">
          AI가 공고 특성에 맞는 최적의 스타일을 추천했습니다.
          각 탭을 클릭하여 스타일별 신청서를 확인하세요.
        </p>
      </div>

      <Tabs value={selectedStyle} onValueChange={handleTabChange}>
        <TabsList className="w-full flex-wrap h-auto gap-1 p-1">
          {applications.map((app) => {
            const styleInfo = getStyleInfo(app.style)
            return (
              <TabsTrigger
                key={app.style}
                value={app.style}
                className="flex items-center gap-1 data-[state=active]:bg-blue-100"
              >
                <span>{styleInfo.icon}</span>
                <span className="hidden sm:inline">{styleInfo.name}</span>
                {app.isRecommended && (
                  <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />
                )}
              </TabsTrigger>
            )
          })}
        </TabsList>

        {applications.map((app) => {
          const styleInfo = getStyleInfo(app.style)
          return (
            <TabsContent key={app.style} value={app.style} className="mt-4">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <CardTitle className="flex items-center gap-2">
                        {styleInfo.icon} {styleInfo.name}
                      </CardTitle>
                      {app.isRecommended && (
                        <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300">
                          <Star className="h-3 w-3 mr-1 fill-yellow-500" />
                          AI 추천
                        </Badge>
                      )}
                      <Badge variant={styleInfo.type === 'combination' ? 'secondary' : 'outline'}>
                        {styleInfo.type === 'combination' ? '조합' : '베이스'}
                      </Badge>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCopy(app)}
                      >
                        {copiedStyle === app.style ? (
                          <><Check className="h-4 w-4 mr-1" /> 복사됨</>
                        ) : (
                          <><Copy className="h-4 w-4 mr-1" /> 복사</>
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDownload(app)}
                      >
                        <Download className="h-4 w-4 mr-1" /> 다운로드
                      </Button>
                    </div>
                  </div>
                  <p className="text-sm text-gray-600">{styleInfo.description}</p>
                  {app.charCount && (
                    <p className="text-xs text-gray-500">
                      {app.charCount.toLocaleString()}자 | {app.sectionCount || 0}개 섹션
                    </p>
                  )}
                </CardHeader>
                <CardContent>
                  <ApplicationContent application={app} />
                </CardContent>
              </Card>
            </TabsContent>
          )
        })}
      </Tabs>
    </div>
  )
}

/**
 * 신청서 내용 렌더링 컴포넌트
 */
function ApplicationContent({ application }: { application: ApplicationResult }) {
  const { content } = application

  if (!content.sections || content.sections.length === 0) {
    return (
      <div className="prose prose-sm max-w-none">
        <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-lg">
          {content.plain_text || '내용이 없습니다.'}
        </pre>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {content.sections.map((section, idx) => (
        <div key={idx} className="border-l-4 border-blue-200 pl-4">
          <h3 className="font-semibold text-lg mb-3">{section.title}</h3>

          {section.subsections ? (
            <div className="space-y-4">
              {section.subsections.map((sub, subIdx) => (
                <div key={subIdx} className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium text-gray-800 mb-2">{sub.title}</h4>
                  <p className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
                    {sub.content}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
              {section.content}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

export type { ApplicationResult }
