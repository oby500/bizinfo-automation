'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Calendar,
  Building2,
  ArrowLeft,
  ExternalLink,
  FileText,
  Download,
  Clock
} from 'lucide-react';
import { BookmarkButton } from '@/components/BookmarkButton';
import { ApplicationWriter } from '@/components/ApplicationWriter';

interface AnnouncementDetail {
  id: string;
  title: string;
  organization: string | null;
  start_date: string;
  end_date: string;
  source: string;
  source_name: string;
  simple_summary: string | null;
  detailed_summary: string | null;
  summary: string | null;  // 백엔드 summary 컬럼 추가
  attachments: Array<{ url: string }>;
  pdf_url: string | null;
  original_url: string | null;
  status: string;
  days_left: number;
  created_at: string;
  extra_info: {
    target?: string | null;
    scale?: string | null;
    contact?: string | null;
  };
}

export default function AnnouncementDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const { id } = use(params);
  const [announcement, setAnnouncement] = useState<AnnouncementDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    // 페이지 진입 시 맨 위로 스크롤
    window.scrollTo(0, 0);

    async function fetchDetail() {
      try {
        const response = await fetch(`${API_URL}/api/announcement/${id}`);

        if (!response.ok) {
          throw new Error('공고를 찾을 수 없습니다');
        }

        const data = await response.json();
        setAnnouncement(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : '공고를 불러오는데 실패했습니다');
      } finally {
        setLoading(false);
      }
    }

    fetchDetail();
  }, [id, API_URL]);

  const getStatusBadge = (status: string, daysLeft: number) => {
    if (status === 'ongoing') {
      return <Badge className="bg-blue-900">진행중 (D-{daysLeft})</Badge>;
    }
    if (status === 'deadline') {
      return <Badge className="bg-gray-600">마감임박 (D-{daysLeft})</Badge>;
    }
    return <Badge variant="outline">종료</Badge>;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-500">공고를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error || !announcement) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle className="text-red-600">오류</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-gray-600 mb-4">{error || '공고를 찾을 수 없습니다'}</p>
            <Button onClick={() => router.push('/')} variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" />
              목록으로 돌아가기
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="sticky top-0 z-50 shadow-sm">
        {/* Slogan Only */}
        <div className="bg-gradient-to-r from-blue-900 to-blue-800 border-b border-blue-700">
          <div className="container mx-auto px-6">
            <div className="relative flex items-center justify-center py-8">
              {/* 로고 - 왼쪽 상단 */}
              <img
                src="/roten-logo.png"
                alt="로튼 로고"
                className="absolute left-[20px] bottom-[11px] h-26"
              />
              {/* 브랜드명 - 왼쪽 하단 */}
              <span className="absolute left-[20px] bottom-[16px] text-xl font-bold text-white z-10">로튼정부지원</span>

              {/* Slogan - 중앙 */}
              <div className="text-center">
                <h2 className="text-3xl font-extrabold text-white mb-3 tracking-tight">
                  저희가 대신 지원사업을 <span className="text-amber-400">찾고</span> / <span className="text-amber-400">작성</span>합니다
                </h2>
                <p className="text-lg font-medium text-blue-100 tracking-wide">
                  찾고 분석하고 작성하고 알림으로 언제나
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Bar */}
        <div className="bg-gray-50 border-b">
          <div className="container mx-auto px-6">
            <nav className="flex items-center gap-0">
              <button onClick={() => router.push('/')} className="px-6 py-4 text-sm font-medium text-gray-700 hover:text-blue-900 hover:bg-white transition-colors">
                <ArrowLeft className="inline mr-2 h-4 w-4" />
                목록으로
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* 메인 컨텐츠 */}
      <main className="container mx-auto px-4 py-8 max-w-4xl">
        {/* 제목 카드 */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant="outline">{announcement.source_name}</Badge>
                  {getStatusBadge(announcement.status, announcement.days_left)}
                </div>
                <h1 className="text-2xl font-bold text-gray-900 mb-4">
                  {announcement.title}
                </h1>
                {announcement.organization && (
                  <div className="flex items-center text-gray-600 mb-2">
                    <Building2 className="h-4 w-4 mr-2" />
                    {announcement.organization}
                  </div>
                )}
                <div className="flex items-center text-gray-600">
                  <Calendar className="h-4 w-4 mr-2" />
                  {announcement.start_date} ~ {announcement.end_date}
                </div>
                {announcement.days_left > 0 && (
                  <div className="flex items-center text-orange-600 mt-2">
                    <Clock className="h-4 w-4 mr-2" />
                    마감까지 {announcement.days_left}일 남음
                  </div>
                )}
              </div>
              {/* 북마크 버튼 */}
              <div className="ml-4">
                <BookmarkButton
                  announcementId={announcement.id}
                  announcementSource={announcement.source === 'kstartup' ? 'kstartup' : 'bizinfo'}
                />
              </div>
            </div>
          </CardHeader>
        </Card>

        {/* 1. 상세 설명 - detailed_summary 우선, 없으면 summary 표시 */}
        {(announcement.detailed_summary || announcement.summary) && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">
                📝 {announcement.detailed_summary ? '상세 설명' : '공고 요약'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="whitespace-pre-wrap text-gray-700 leading-relaxed">
                {announcement.detailed_summary || announcement.summary}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 2. 원문 링크 버튼 */}
        {announcement.original_url && (
          <Card className="mb-6">
            <CardContent className="pt-6">
              <a
                href={announcement.original_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-3 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                <ExternalLink className="h-5 w-5" />
                원문 페이지에서 보기
              </a>
            </CardContent>
          </Card>
        )}

        {/* 3. AI 신청서 작성 (ApplicationWriter 컴포넌트) */}
        {announcement.status !== 'closed' && (
          <ApplicationWriter
            announcementId={announcement.id}
            announcementSource={announcement.source === 'kstartup' ? 'kstartup' : 'bizinfo'}
          />
        )}

        {/* 추가 정보 */}
        {announcement.extra_info &&
         (announcement.extra_info.target || announcement.extra_info.scale || announcement.extra_info.contact) && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">ℹ️ 추가 정보</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {announcement.extra_info.target && (
                  <div>
                    <p className="text-sm font-medium text-gray-500 mb-1">지원 대상</p>
                    <p className="text-gray-900">{announcement.extra_info.target}</p>
                  </div>
                )}
                {announcement.extra_info.scale && (
                  <div>
                    <p className="text-sm font-medium text-gray-500 mb-1">지원 규모</p>
                    <p className="text-gray-900">{announcement.extra_info.scale}</p>
                  </div>
                )}
                {announcement.extra_info.contact && (
                  <div className="col-span-full">
                    <p className="text-sm font-medium text-gray-500 mb-1">문의처</p>
                    <p className="text-gray-900">{announcement.extra_info.contact}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
