'use client';

import { useEffect, useState } from 'react';
import { BookmarkButton } from '@/components/BookmarkButton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface Bookmark {
  id: string;
  user_id: string;
  announcement_id: string;
  announcement_source: 'kstartup' | 'bizinfo';
  created_at: string;
}

export default function BookmarksPage() {
  const router = useRouter();
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  useEffect(() => {
    fetchBookmarks();
  }, [page]);

  const fetchBookmarks = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/bookmarks?page=${page}&page_size=${pageSize}`,
        {
          headers: {
            'X-User-ID': 'temp-user-id', // TODO: 실제 세션에서 user_id 가져오기
          },
        }
      );

      if (!response.ok) {
        throw new Error('북마크 목록을 불러오는 데 실패했습니다');
      }

      const data = await response.json();
      setBookmarks(data.bookmarks || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (error) {
      console.error('Failed to fetch bookmarks:', error);
      alert(error instanceof Error ? error.message : '북마크 목록 조회 중 오류가 발생했습니다');
    } finally {
      setLoading(false);
    }
  };

  const handleBookmarkToggle = (bookmarkId: string, isBookmarked: boolean) => {
    if (!isBookmarked) {
      // 북마크가 해제되면 목록에서 제거
      setBookmarks((prev) => prev.filter((b) => b.id !== bookmarkId));
      setTotal((prev) => prev - 1);
    }
  };

  const handleAnnouncementClick = (announcementId: string, source: string) => {
    router.push(`/announcement/${announcementId}?source=${source}`);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getSourceBadge = (source: string) => {
    if (source === 'kstartup') {
      return <Badge variant="default" className="bg-blue-600">K-Startup</Badge>;
    } else {
      return <Badge variant="default" className="bg-green-600">기업마당</Badge>;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">내 북마크</h1>
        <p className="text-gray-600">
          저장한 공고 {total}개
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      ) : bookmarks.length === 0 ? (
        <Card>
          <CardContent className="py-20 text-center">
            <p className="text-gray-500 mb-4">저장된 북마크가 없습니다</p>
            <Button onClick={() => router.push('/')}>
              공고 둘러보기
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4">
            {bookmarks.map((bookmark) => (
              <Card
                key={bookmark.id}
                className="hover:shadow-lg transition-shadow cursor-pointer"
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div
                      className="flex-1"
                      onClick={() =>
                        handleAnnouncementClick(
                          bookmark.announcement_id,
                          bookmark.announcement_source
                        )
                      }
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {getSourceBadge(bookmark.announcement_source)}
                        <span className="text-sm text-gray-500">
                          {bookmark.announcement_id}
                        </span>
                      </div>
                      <h3 className="text-lg font-semibold mb-2 hover:text-blue-600 transition-colors">
                        공고 ID: {bookmark.announcement_id}
                      </h3>
                      <p className="text-sm text-gray-500">
                        저장일: {formatDate(bookmark.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          handleAnnouncementClick(
                            bookmark.announcement_id,
                            bookmark.announcement_source
                          )
                        }
                      >
                        <ExternalLink className="h-4 w-4 mr-2" />
                        상세보기
                      </Button>
                      <BookmarkButton
                        announcementId={bookmark.announcement_id}
                        announcementSource={bookmark.announcement_source}
                        initialBookmarked={true}
                        bookmarkId={bookmark.id}
                        onToggle={(isBookmarked) =>
                          handleBookmarkToggle(bookmark.id, isBookmarked)
                        }
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <div className="flex justify-center items-center gap-2 mt-8">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-gray-600">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={page === totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
