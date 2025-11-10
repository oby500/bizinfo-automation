'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bookmark, Clock, Bell, Trash2, Coins, Plus } from 'lucide-react';
import useSWR from 'swr';
import { User } from '@/lib/db/schema';
import Link from 'next/link';

const fetcher = (url: string) => fetch(url).then((res) => res.json());

interface Announcement {
  id: string;
  title: string;
  organization: string;
  source: string;
  start_date: string;
  end_date: string;
  status: string;
  category?: string;
  simple_summary?: string;
}

export default function MyPage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const { data: user } = useSWR<User>('/api/user', fetcher);
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [bookmarkedAnnouncements, setBookmarkedAnnouncements] = useState<Announcement[]>([]);
  const [recentViews, setRecentViews] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'bookmarks' | 'recent' | 'notifications'>('bookmarks');
  const [isLoadingBookmarks, setIsLoadingBookmarks] = useState(false);
  const [bookmarkError, setBookmarkError] = useState<string | null>(null);
  const [recentViewsError, setRecentViewsError] = useState<string | null>(null);

  // 로그인 체크 - 미로그인 시 로그인 페이지로 리디렉트
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login?callbackUrl=/mypage');
    }
  }, [status, router]);

  useEffect(() => {
    // 북마크 불러오기
    try {
      const saved = JSON.parse(localStorage.getItem('bookmarkedAnnouncements') || '[]');
      setBookmarks(saved);

      // 북마크 ID로 실제 데이터 불러오기
      if (saved.length > 0) {
        fetchBookmarkData(saved);
      }
    } catch (error) {
      console.error('북마크 로드 실패:', error);
    }

    // 최근 본 공고 불러오기
    try {
      const recent = JSON.parse(localStorage.getItem('recentAnnouncements') || '[]');
      setRecentViews(recent);
    } catch (error) {
      console.error('최근 본 공고 로드 실패:', error);
    }
  }, []);

  const fetchBookmarkData = async (ids: string[]) => {
    if (!ids || ids.length === 0) {
      setBookmarkedAnnouncements([]);
      setBookmarkError(null);
      return;
    }

    setIsLoadingBookmarks(true);
    setBookmarkError(null);

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_URL}/api/announcements/bulk`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ announcement_ids: ids }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`서버 응답 실패 (${response.status}): ${errorText}`);
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error('데이터 조회 실패');
      }

      setBookmarkedAnnouncements(data.announcements || []);

      // 조회 실패한 ID들이 있으면 경고
      if (data.announcements.length < ids.length) {
        setBookmarkError(`${ids.length}개 중 ${data.announcements.length}개만 불러왔습니다.`);
      }
    } catch (error) {
      console.error('북마크 데이터 불러오기 실패:', error);
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
      setBookmarkError(`북마크를 불러올 수 없습니다: ${errorMessage}`);
      // 에러 발생 시에도 빈 배열로 설정 (ID는 localStorage에 유지됨)
      setBookmarkedAnnouncements([]);
    } finally {
      setIsLoadingBookmarks(false);
    }
  };

  const calculateDday = (endDate: string) => {
    if (!endDate) return null;
    try {
      const end = new Date(endDate);
      if (isNaN(end.getTime())) return null;
      const today = new Date();
      const diffTime = end.getTime() - today.getTime();
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays;
    } catch (error) {
      console.error('D-day 계산 실패:', error);
      return null;
    }
  };

  const removeBookmark = (id: string) => {
    try {
      const updated = bookmarks.filter(bookmark => bookmark !== id);
      localStorage.setItem('bookmarkedAnnouncements', JSON.stringify(updated));
      setBookmarks(updated);
      setBookmarkedAnnouncements(bookmarkedAnnouncements.filter(item => item.id !== id));
      setBookmarkError(null);
    } catch (error) {
      console.error('북마크 삭제 실패:', error);
      setBookmarkError('북마크 삭제 중 오류가 발생했습니다.');
    }
  };

  const removeRecentView = (id: string) => {
    try {
      const updated = recentViews.filter(view => view.id !== id);
      localStorage.setItem('recentAnnouncements', JSON.stringify(updated));
      setRecentViews(updated);
      setRecentViewsError(null);
    } catch (error) {
      console.error('최근 본 공고 삭제 실패:', error);
      setRecentViewsError('삭제 중 오류가 발생했습니다.');
    }
  };

  const clearAllBookmarks = () => {
    if (confirm('모든 북마크를 삭제하시겠습니까?')) {
      try {
        localStorage.setItem('bookmarkedAnnouncements', JSON.stringify([]));
        setBookmarks([]);
        setBookmarkedAnnouncements([]);
        setBookmarkError(null);
      } catch (error) {
        console.error('북마크 전체 삭제 실패:', error);
        setBookmarkError('전체 삭제 중 오류가 발생했습니다.');
      }
    }
  };

  const clearAllRecentViews = () => {
    if (confirm('모든 최근 본 공고를 삭제하시겠습니까?')) {
      try {
        localStorage.setItem('recentAnnouncements', JSON.stringify([]));
        setRecentViews([]);
        setRecentViewsError(null);
      } catch (error) {
        console.error('최근 본 공고 전체 삭제 실패:', error);
        setRecentViewsError('전체 삭제 중 오류가 발생했습니다.');
      }
    }
  };

  // 로딩 중이거나 미로그인 시 로딩 화면
  if (status === 'loading') {
    return (
      <div className="flex-1 bg-gray-50 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  // 미로그인 시 빈 화면 (리디렉트 진행 중)
  if (!session) {
    return null;
  }

  return (
    <div className="flex-1 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 사용자 정보 카드 */}
        <Card className="mb-6">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-2xl">마이페이지</CardTitle>
              <CardDescription>
                {user?.email || '로딩 중...'}
              </CardDescription>
            </div>
            <Link href="/pricing">
              <Button className="bg-orange-500 hover:bg-orange-600">
                <Plus className="w-4 h-4 mr-2" />
                포인트 충전
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4 text-center">
              <div className="p-4 bg-gradient-to-br from-orange-400 to-orange-600 text-white rounded-lg shadow-lg">
                <Coins className="w-6 h-6 mx-auto mb-2" />
                <div className="text-3xl font-bold">0</div>
                <div className="text-sm mt-1 opacity-90">보유 포인트</div>
              </div>
              <div className="p-4 bg-orange-50 rounded-lg border border-orange-100">
                <Bookmark className="w-5 h-5 mx-auto mb-2 text-orange-600" />
                <div className="text-2xl font-bold text-orange-600">{bookmarks.length}</div>
                <div className="text-sm text-gray-600 mt-1">북마크</div>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                <Clock className="w-5 h-5 mx-auto mb-2 text-blue-600" />
                <div className="text-2xl font-bold text-blue-600">{recentViews.length}</div>
                <div className="text-sm text-gray-600 mt-1">최근 본 공고</div>
              </div>
              <div className="p-4 bg-green-50 rounded-lg border border-green-100">
                <Bell className="w-5 h-5 mx-auto mb-2 text-green-600" />
                <div className="text-2xl font-bold text-green-600">0</div>
                <div className="text-sm text-gray-600 mt-1">활성 알림</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 탭 메뉴 */}
        <div className="flex space-x-1 mb-6 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('bookmarks')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'bookmarks'
                ? 'text-orange-600 border-b-2 border-orange-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Bookmark className="inline-block w-4 h-4 mr-2" />
            북마크 ({bookmarks.length})
          </button>
          <button
            onClick={() => setActiveTab('recent')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'recent'
                ? 'text-orange-600 border-b-2 border-orange-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Clock className="inline-block w-4 h-4 mr-2" />
            최근 본 공고 ({recentViews.length})
          </button>
          <button
            onClick={() => setActiveTab('notifications')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'notifications'
                ? 'text-orange-600 border-b-2 border-orange-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Bell className="inline-block w-4 h-4 mr-2" />
            알림 설정
          </button>
        </div>

        {/* 북마크 탭 */}
        {activeTab === 'bookmarks' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">저장한 공고</h2>
              {bookmarks.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearAllBookmarks}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  전체 삭제
                </Button>
              )}
            </div>

            {/* 에러 메시지 */}
            {bookmarkError && (
              <Card className="mb-4 border-orange-200 bg-orange-50">
                <CardContent className="py-3">
                  <div className="flex items-start gap-2 text-orange-800">
                    <span className="text-orange-600">⚠️</span>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{bookmarkError}</p>
                      <button
                        onClick={() => {
                          setBookmarkError(null);
                          if (bookmarks.length > 0) {
                            fetchBookmarkData(bookmarks);
                          }
                        }}
                        className="text-xs text-orange-600 hover:text-orange-700 underline mt-1"
                      >
                        다시 시도
                      </button>
                    </div>
                    <button
                      onClick={() => setBookmarkError(null)}
                      className="text-orange-600 hover:text-orange-700"
                    >
                      ✕
                    </button>
                  </div>
                </CardContent>
              </Card>
            )}

            {bookmarks.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-gray-500">
                  저장한 공고가 없습니다.
                </CardContent>
              </Card>
            ) : isLoadingBookmarks ? (
              <Card>
                <CardContent className="py-12 text-center text-gray-500">
                  <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mr-3"></div>
                    북마크 데이터를 불러오는 중...
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {bookmarkedAnnouncements.map((item) => (
                  <Card
                    key={item.id}
                    className="hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => window.open(`/announcement/${item.id}`, '_blank')}
                  >
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                              item.source === 'kstartup'
                                ? 'bg-blue-100 text-blue-700'
                                : 'bg-green-100 text-green-700'
                            }`}>
                              {item.source === 'kstartup' ? 'K-Startup' : 'BizInfo'}
                            </span>
                            <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                              item.status === 'ongoing' ? 'bg-green-100 text-green-700' :
                              item.status === 'deadline' ? 'bg-orange-100 text-orange-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {item.status === 'ongoing' ? '진행중' :
                               item.status === 'deadline' ? '마감임박' : '종료'}
                            </span>
                          </div>
                          <h3 className="font-semibold text-gray-900 mb-1">{item.title}</h3>
                          <p className="text-sm text-gray-600 mb-2">{item.organization}</p>
                          {item.simple_summary && (
                            <p className="text-sm text-gray-500 line-clamp-2 mb-2">
                              {item.simple_summary}
                            </p>
                          )}
                          <div className="flex items-center gap-3 text-xs text-gray-500">
                            {item.start_date && item.end_date ? (
                              <>
                                <span>{item.start_date} ~ {item.end_date}</span>
                                {item.status !== 'closed' && calculateDday(item.end_date) !== null && (
                                  <span className="text-orange-500 font-medium">
                                    D-{calculateDday(item.end_date)}
                                  </span>
                                )}
                              </>
                            ) : (
                              <span className="text-gray-400">날짜 정보 없음</span>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeBookmark(item.id);
                          }}
                          className="text-gray-400 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 최근 본 공고 탭 */}
        {activeTab === 'recent' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">최근 본 공고</h2>
              {recentViews.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearAllRecentViews}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  전체 삭제
                </Button>
              )}
            </div>

            {/* 에러 메시지 */}
            {recentViewsError && (
              <Card className="mb-4 border-orange-200 bg-orange-50">
                <CardContent className="py-3">
                  <div className="flex items-start gap-2 text-orange-800">
                    <span className="text-orange-600">⚠️</span>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{recentViewsError}</p>
                    </div>
                    <button
                      onClick={() => setRecentViewsError(null)}
                      className="text-orange-600 hover:text-orange-700"
                    >
                      ✕
                    </button>
                  </div>
                </CardContent>
              </Card>
            )}

            {recentViews.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-gray-500">
                  최근 본 공고가 없습니다.
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {recentViews.map((item) => (
                  <Card
                    key={item.id}
                    className="hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => window.open(`/announcement/${item.id}`, '_blank')}
                  >
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900 mb-1">{item.title}</h3>
                          <p className="text-sm text-gray-600">{item.organization || '기관 정보 없음'}</p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                            {item.start_date && item.end_date ? (
                              <>
                                <span>{item.start_date} ~ {item.end_date}</span>
                                {calculateDday(item.end_date) !== null && (
                                  <span className="text-orange-500 font-medium">
                                    D-{calculateDday(item.end_date)}
                                  </span>
                                )}
                              </>
                            ) : (
                              <span className="text-gray-400">날짜 정보 없음</span>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeRecentView(item.id);
                          }}
                          className="text-gray-400 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 알림 설정 탭 */}
        {activeTab === 'notifications' && (
          <Card>
            <CardHeader>
              <CardTitle>알림 설정</CardTitle>
              <CardDescription>
                마감 임박 공고에 대한 알림을 받을 수 있습니다.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <h4 className="font-medium">D-3 알림</h4>
                    <p className="text-sm text-gray-500">마감 3일 전에 알림을 받습니다</p>
                  </div>
                  <Button variant="outline" size="sm">
                    활성화
                  </Button>
                </div>
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <h4 className="font-medium">D-1 알림</h4>
                    <p className="text-sm text-gray-500">마감 1일 전에 알림을 받습니다</p>
                  </div>
                  <Button variant="outline" size="sm">
                    활성화
                  </Button>
                </div>
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <h4 className="font-medium">새 공고 알림</h4>
                    <p className="text-sm text-gray-500">관심 분야의 새 공고가 등록되면 알림을 받습니다</p>
                  </div>
                  <Button variant="outline" size="sm">
                    활성화
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
