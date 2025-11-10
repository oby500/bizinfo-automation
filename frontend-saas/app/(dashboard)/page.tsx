'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, Filter, Calendar, Building2, ChevronLeft, ChevronRight, Clock } from 'lucide-react';
import AutoSlideCarousel from '@/components/AutoSlideCarousel';
import { BookmarkButton } from '@/components/BookmarkButton';

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
  detailed_summary?: string;
  created_at?: string;
  views?: number;
  relevance?: number; // AI 검색 유사도 점수
}

interface SearchFilters {
  status: 'all' | 'ongoing' | 'deadline';
  category?: string;
  region?: string;
  target?: string;
  age?: string;
  businessYear?: string;
  sort?: 'newest' | 'deadline' | 'views' | 'relevance';
}

interface FilterOptions {
  categories: string[];
  regions: string[];
  targets: string[];
  ages: string[];
  business_years: string[];
}

export default function HomePage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [searchQuery, setSearchQuery] = useState('');
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<SearchFilters>({
    status: 'all',
    sort: 'newest'
  });
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    categories: [],
    regions: [],
    targets: [],
    ages: [],
    business_years: []
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [useAISearch, setUseAISearch] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission>('default');
  const [compareList, setCompareList] = useState<Announcement[]>([]);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const [recentViews, setRecentViews] = useState<any[]>([]);
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [userBalance, setUserBalance] = useState(0);
  const [userName, setUserName] = useState<string>('사용자');
  const [carouselAnnouncements, setCarouselAnnouncements] = useState<Announcement[]>([]);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const PAGE_SIZE = 10;  // 페이지당 10개 표시
  const MAX_COMPARE = 3;

  // 서브 슬로건 목록
  const subSlogans = [
    '추천·분석·작성·알림까지 한 번에',
    '검색부터 신청서 작성까지 한 번에',
    '맞춤 검색·AI 분석·신청서 작성·마감 알림'
  ];

  // 랜덤 서브 슬로건 선택
  const [randomSubSlogan] = useState(() => {
    return subSlogans[Math.floor(Math.random() * subSlogans.length)];
  });

  // 일반 검색 함수 (첫 검색)
  const handleSearch = async (resetPage = true) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);

    const page = resetPage ? 1 : currentPage;

    try {
      const params = new URLSearchParams({
        q: searchQuery,
        page: page.toString(),
        limit: PAGE_SIZE.toString(),
      });

      if (filters.status !== 'all') {
        params.append('status', filters.status);
      }

      if (filters.sort) {
        params.append('sort', filters.sort);
      }

      const response = await fetch(`${API_URL}/api/search?${params}`);

      if (!response.ok) {
        throw new Error(`검색 실패: ${response.statusText}`);
      }

      const data = await response.json();

      if (resetPage) {
        setAnnouncements(data.results || []);
        setCurrentPage(1);
      } else {
        setAnnouncements(prev => [...prev, ...(data.results || [])]);
      }

      setTotalResults(data.total || 0);
    } catch (error) {
      console.error('검색 실패:', error);
      setError(error instanceof Error ? error.message : '검색 중 오류가 발생했습니다.');
      if (resetPage) {
        setAnnouncements([]);
        setTotalResults(0);
      }
    } finally {
      setLoading(false);
    }
  };


  // AI 의미 검색 함수 (첫 검색)
  const handleSemanticSearch = async (resetPage = true) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        q: searchQuery,
        threshold: '0.5',
        limit: PAGE_SIZE.toString(),
      });

      if (filters.status !== 'all') {
        params.append('status', filters.status);
      }

      const response = await fetch(`${API_URL}/api/search/semantic?${params}`);

      if (!response.ok) {
        throw new Error('AI 검색 서비스를 사용할 수 없습니다. 일반 검색으로 전환합니다.');
      }

      const data = await response.json();

      // 의미 검색 결과를 일반 검색과 동일한 형식으로 변환
      const semanticResults = (data.data || []).map((item: any) => ({
        ...item,
        relevance: item.similarity, // 유사도 점수 추가
      }));

      if (resetPage) {
        setAnnouncements(semanticResults);
        setCurrentPage(1);
      } else {
        setAnnouncements(prev => [...prev, ...semanticResults]);
      }

      setTotalResults(data.total || 0);
    } catch (error) {
      console.error('AI 검색 실패:', error);
      setError(error instanceof Error ? error.message : 'AI 검색 실패. 일반 검색으로 전환합니다.');
      // 실패 시 일반 검색으로 폴백
      await handleSearch(resetPage);
    } finally {
      setLoading(false);
    }
  };

  // 필터 옵션 로드
  useEffect(() => {
    async function fetchFilterOptions() {
      try {
        console.log('[DEBUG] Fetching filter options from:', `${API_URL}/api/filters`);
        const response = await fetch(`${API_URL}/api/filters`);
        const data = await response.json();
        console.log('[DEBUG] Filter API response:', data);

        if (data.success) {
          console.log('[DEBUG] Setting filter options:', {
            categories: data.filters.categories?.length,
            regions: data.filters.regions?.length,
            targets: data.filters.targets?.length,
            ages: data.filters.ages?.length,
            business_years: data.filters.business_years?.length
          });
          setFilterOptions(data.filters);
        } else {
          console.error('[ERROR] Filter API returned success=false');
        }
      } catch (error) {
        console.error('[ERROR] 필터 옵션 로딩 실패:', error);
      }
    }
    fetchFilterOptions();
  }, []);

  // 최근 공고 불러오기 (초기 로딩 - 마감된 공고 제외)
  useEffect(() => {
    async function fetchRecent() {
      console.log('[DEBUG] 최근 공고 로딩 시작...');
      console.log('[DEBUG] API_URL:', API_URL);
      try {
        const url = `${API_URL}/api/recent?page=1&limit=${PAGE_SIZE}&status=ongoing`;
        console.log('[DEBUG] Fetching:', url);

        const response = await fetch(url);
        console.log('[DEBUG] Response status:', response.status);
        console.log('[DEBUG] Response OK:', response.ok);

        const data = await response.json();
        console.log('[DEBUG] Data received:', data);
        console.log('[DEBUG] Results count:', data.results?.length);
        console.log('[DEBUG] Total:', data.total);

        setAnnouncements(data.results || []);
        setTotalResults(data.total || 0);
        setCurrentPage(1);

        console.log('[DEBUG] State updated - announcements:', data.results?.length, 'total:', data.total);
      } catch (error) {
        console.error('[ERROR] 최근 공고 로딩 실패:', error);
      }
    }

    async function fetchCarousel() {
      console.log('[DEBUG] 캐러셀 공고 로딩 시작...');
      try {
        // 캐러셀용 추천 공고: 최근 공고 중 30개 (슬라이드용)
        // status 필터 제거하여 모든 공고 표시
        const url = `${API_URL}/api/recent?limit=30`;
        console.log('[DEBUG] 캐러셀 API URL:', url);
        const response = await fetch(url);
        console.log('[DEBUG] 캐러셀 Response status:', response.status);
        const data = await response.json();
        console.log('[DEBUG] 캐러셀 Data:', data);

        setCarouselAnnouncements(data.results || []);
        console.log('[DEBUG] 캐러셀 공고 로딩 완료:', data.results?.length, '개');
      } catch (error) {
        console.error('[ERROR] 캐러셀 공고 로딩 실패:', error);
      }
    }

    fetchRecent();
    fetchCarousel();
  }, []);

  // 페이지 변경 핸들러
  const handlePageChange = async (newPage: number) => {
    setCurrentPage(newPage);
    setLoading(true);

    window.scrollTo({ top: 0, behavior: 'smooth' });

    try {
      const params = new URLSearchParams({
        q: searchQuery || '',
        page: newPage.toString(),
        limit: PAGE_SIZE.toString(),
      });

      if (filters.status !== 'all') {
        params.append('status', filters.status);
      }

      if (filters.sort) {
        params.append('sort', filters.sort);
      }

      const endpoint = useAISearch ? '/api/search/semantic' : (searchQuery ? '/api/search' : '/api/recent');
      const response = await fetch(`${API_URL}${endpoint}?${params}`);

      if (!response.ok) {
        throw new Error('페이지 로드 실패');
      }

      const data = await response.json();
      const results = useAISearch
        ? (data.data || []).map((item: any) => ({ ...item, relevance: item.similarity }))
        : (data.results || []);

      setAnnouncements(results);
      setTotalResults(data.total || 0);
    } catch (error) {
      console.error('페이지 로딩 실패:', error);
    } finally {
      setLoading(false);
    }
  };

  // 알림 권한 확인 및 정기 체크
  useEffect(() => {
    // 브라우저 알림 권한 상태 확인
    if ('Notification' in window) {
      setNotificationPermission(Notification.permission);

      // 권한이 있으면 알림 체크
      if (Notification.permission === 'granted') {
        checkAndSetupNotifications();

        // 매 시간마다 알림 체크 (1시간 = 3600000ms)
        const interval = setInterval(checkAndSetupNotifications, 3600000);
        return () => clearInterval(interval);
      }
    }

    // 최근 본 공고 로드
    loadRecentViews();

    // 북마크 로드
    loadBookmarks();

    // 사용자 잔액 로드
    loadUserBalance();

    // 사용자 정보 로드
    loadUserInfo();
  }, []);

  // 검색어 입력 처리
  const handleSearchInput = async (value: string) => {
    setSearchQuery(value);

    if (value.trim().length >= 2) {
      try {
        const response = await fetch(`${API_URL}/api/suggestions?q=${encodeURIComponent(value)}`);
        const data = await response.json();

        if (data.success) {
          setSuggestions(data.suggestions || []);
          setShowSuggestions(true);
        }
      } catch (error) {
        console.error('자동완성 조회 실패:', error);
        setSuggestions([]);
      }
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  // 제안 선택
  const handleSuggestionClick = (suggestion: string) => {
    setSearchQuery(suggestion);
    setShowSuggestions(false);
    setSuggestions([]);
  };

  // 엔터키로 검색
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      setShowSuggestions(false);
      useAISearch ? handleSemanticSearch() : handleSearch();
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  // D-Day 계산 함수
  const calculateDday = (endDate: string) => {
    const today = new Date();
    const end = new Date(endDate);
    const diffTime = end.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  // 카테고리별 색상 반환 (청색 + 회색 계열)
  const getCategoryColor = (category?: string) => {
    if (!category) return 'bg-gray-200 text-gray-700';

    // 자금/금융 계열 (중요도 높음 - 진한 파랑)
    if (category.includes('자금지원')) return 'bg-blue-700 text-blue-50';
    if (category.includes('정책자금')) return 'bg-blue-600 text-white';

    // 기술/혁신 계열 (차별화 - 보라)
    if (category.includes('기술개발')) return 'bg-purple-600 text-purple-50';

    // 사업/창업 계열 (중요 - 중간 파랑)
    if (category.includes('시설') || category.includes('공간')) return 'bg-blue-500 text-white';
    if (category.includes('교육') || category.includes('컨설팅') || category.includes('멘토링')) return 'bg-blue-400 text-white';

    // 확장/성장 계열 (활동적 - 연한 파랑)
    if (category.includes('해외진출') || category.includes('수출')) return 'bg-blue-300 text-blue-900';
    if (category.includes('판로') || category.includes('마케팅')) return 'bg-blue-200 text-blue-900';

    // 운영 지원 계열 (실용적 - 회색)
    if (category.includes('인력') || category.includes('일자리')) return 'bg-gray-600 text-gray-50';
    if (category.includes('네트워킹') || category.includes('커뮤니티')) return 'bg-gray-500 text-white';

    // 특수 분야 (구분 - 연한 회색)
    if (category.includes('농림축수산업')) return 'bg-gray-300 text-gray-800';
    if (category.includes('기타')) return 'bg-gray-200 text-gray-700';

    return 'bg-gray-200 text-gray-700';
  };

  // 최근 본 공고 로드
  const loadRecentViews = () => {
    try {
      const recent = JSON.parse(localStorage.getItem('recentAnnouncements') || '[]');
      setRecentViews(recent);
    } catch (error) {
      console.error('최근 본 공고 로드 실패:', error);
    }
  };

  // 최근 본 공고 저장 (로컬 스토리지)
  const saveRecentView = (announcement: Announcement) => {
    try {
      const recent = JSON.parse(localStorage.getItem('recentAnnouncements') || '[]');

      // 중복 제거 (같은 ID가 있으면 제거)
      const filtered = recent.filter((item: any) => item.id !== announcement.id);

      // 맨 앞에 추가
      const updated = [
        {
          id: announcement.id,
          title: announcement.title,
          organization: announcement.organization,
          end_date: announcement.end_date,
          viewedAt: new Date().toISOString()
        },
        ...filtered
      ].slice(0, 10); // 최대 10개만 저장

      localStorage.setItem('recentAnnouncements', JSON.stringify(updated));
      setRecentViews(updated); // 상태 업데이트
    } catch (error) {
      console.error('최근 본 공고 저장 실패:', error);
    }
  };

  // 공고 클릭 핸들러
  const handleAnnouncementClick = (announcement: Announcement) => {
    saveRecentView(announcement);
    router.push(`/announcement/${announcement.id}`);
  };

  // 브라우저 알림 권한 요청
  const requestNotificationPermission = async () => {
    if (!('Notification' in window)) {
      alert('이 브라우저는 알림을 지원하지 않습니다.');
      return;
    }

    const permission = await Notification.requestPermission();
    setNotificationPermission(permission);

    if (permission === 'granted') {
      // 테스트 알림
      new Notification('알림이 활성화되었습니다', {
        body: '마감 임박 공고에 대한 알림을 받으실 수 있습니다.',
        icon: '/logo.png'
      });

      // 알림 설정 활성화
      checkAndSetupNotifications();
    }
  };

  // 마감 알림 설정
  const setupDeadlineNotification = (announcement: Announcement) => {
    try {
      const notifications = JSON.parse(localStorage.getItem('deadlineNotifications') || '[]');

      // 이미 등록된 공고인지 확인
      const exists = notifications.find((item: any) => item.id === announcement.id);
      if (exists) {
        alert('이미 알림이 설정된 공고입니다.');
        return;
      }

      // 알림 추가
      const updated = [
        ...notifications,
        {
          id: announcement.id,
          title: announcement.title,
          end_date: announcement.end_date,
          createdAt: new Date().toISOString()
        }
      ];

      localStorage.setItem('deadlineNotifications', JSON.stringify(updated));
      alert('마감 알림이 설정되었습니다. (D-3, D-1에 알림)');
    } catch (error) {
      console.error('알림 설정 실패:', error);
    }
  };

  // 알림 체크 및 발송
  const checkAndSetupNotifications = () => {
    if (notificationPermission !== 'granted') return;

    try {
      const notifications = JSON.parse(localStorage.getItem('deadlineNotifications') || '[]');
      const today = new Date();

      notifications.forEach((item: any) => {
        const endDate = new Date(item.end_date);
        const diffTime = endDate.getTime() - today.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        // D-3 또는 D-1 알림
        if (diffDays === 3 || diffDays === 1) {
          new Notification(`마감 ${diffDays}일 전!`, {
            body: item.title,
            icon: '/logo.png',
            tag: `deadline-${item.id}-${diffDays}`
          });
        }

        // 마감일 지난 알림 삭제
        if (diffDays < 0) {
          const filtered = notifications.filter((n: any) => n.id !== item.id);
          localStorage.setItem('deadlineNotifications', JSON.stringify(filtered));
        }
      });
    } catch (error) {
      console.error('알림 체크 실패:', error);
    }
  };

  // 비교 목록에 추가/제거
  const toggleCompare = (announcement: Announcement) => {
    const exists = compareList.find(item => item.id === announcement.id);

    if (exists) {
      // 이미 있으면 제거
      setCompareList(compareList.filter(item => item.id !== announcement.id));
    } else {
      // 없으면 추가 (최대 3개)
      if (compareList.length >= MAX_COMPARE) {
        alert(`최대 ${MAX_COMPARE}개까지 비교할 수 있습니다.`);
        return;
      }
      setCompareList([...compareList, announcement]);
    }
  };

  // 비교 목록 초기화
  const clearCompare = () => {
    setCompareList([]);
    setShowCompareModal(false);
  };

  // 북마크 로드
  const loadBookmarks = () => {
    try {
      const saved = JSON.parse(localStorage.getItem('bookmarkedAnnouncements') || '[]');
      setBookmarks(saved);
    } catch (error) {
      console.error('북마크 로드 실패:', error);
    }
  };

  // 북마크 토글
  const toggleBookmark = (announcementId: string) => {
    try {
      const saved = JSON.parse(localStorage.getItem('bookmarkedAnnouncements') || '[]');

      let updated: string[];
      if (saved.includes(announcementId)) {
        // 이미 북마크되어 있으면 제거
        updated = saved.filter((id: string) => id !== announcementId);
      } else {
        // 없으면 추가
        updated = [...saved, announcementId];
      }

      localStorage.setItem('bookmarkedAnnouncements', JSON.stringify(updated));
      setBookmarks(updated);
    } catch (error) {
      console.error('북마크 토글 실패:', error);
    }
  };

  // 북마크 여부 확인
  const isBookmarked = (announcementId: string) => {
    return bookmarks.includes(announcementId);
  };

  // 사용자 잔액 로드
  const loadUserBalance = () => {
    try {
      const balance = localStorage.getItem('userBalance');
      setUserBalance(balance ? parseInt(balance) : 0);
    } catch (error) {
      console.error('잔액 로드 실패:', error);
    }
  };

  // 사용자 정보 로드
  const loadUserInfo = async () => {
    try {
      const response = await fetch('/api/user');
      const data = await response.json();

      if (data.user && data.user.user_metadata) {
        const fullName = data.user.user_metadata.full_name || data.user.user_metadata.name;

        if (fullName) {
          // 이름 마스킹 (예: "홍길동" → "홍OO")
          const maskedName = fullName.charAt(0) + 'OO';
          setUserName(maskedName);
        } else {
          setUserName('사용자');
        }
      }
    } catch (error) {
      console.error('사용자 정보 로드 실패:', error);
      setUserName('사용자');
    }
  };

  const totalPages = Math.ceil(totalResults / PAGE_SIZE);

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* K-Startup Style Header */}
      <header className="bg-white">
        {/* Top Gray Bar - 중소벤처기업부 등 */}
        <div className="bg-gray-100 border-b border-gray-200">
          <div className="container mx-auto px-6">
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-4 text-xs text-gray-600">
                <Link href="https://www.mss.go.kr" target="_blank" className="hover:text-blue-600">
                  중소벤처기업부
                </Link>
                <span className="text-gray-300">|</span>
                <Link href="https://www.kised.or.kr" target="_blank" className="hover:text-blue-600">
                  창업진흥원
                </Link>
                <span className="text-gray-300">|</span>
                <Link href="https://www.kosmes.or.kr" target="_blank" className="hover:text-blue-600">
                  중소벤처기업진흥공단
                </Link>
              </div>
              <div className="flex items-center gap-3">
                {session?.user ? (
                  <>
                    <span className="text-xs text-gray-600">
                      보유 크레딧: <span className="font-bold text-blue-600">{userBalance.toLocaleString()}원</span>
                    </span>
                    <Link href="/pricing">
                      <Button className="bg-blue-600 hover:bg-blue-700 h-7 text-xs">충전하기</Button>
                    </Link>
                    <Link href="/profile">
                      <Button variant="ghost" className="h-7 text-xs">{userName}님</Button>
                    </Link>
                  </>
                ) : (
                  <>
                    <Link href="/pricing">
                      <Button asChild variant="ghost" className="h-7 text-xs">
                        <span>요금제</span>
                      </Button>
                    </Link>
                    <Link href="/login">
                      <Button asChild className="bg-blue-600 hover:bg-blue-700 h-7 text-xs">
                        <span>로그인</span>
                      </Button>
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Main Header - Slogan Only */}
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
                  {randomSubSlogan}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Bar */}
        <div className="bg-gray-50 border-b">
          <div className="container mx-auto px-6">
            <nav className="flex items-center gap-0">
              <Link href="/" className="px-6 py-4 text-sm font-medium text-gray-700 hover:text-blue-900 hover:bg-white transition-colors">
                사업소개
              </Link>
              <Link href="/" className="px-6 py-4 text-sm font-medium text-gray-700 hover:text-blue-900 hover:bg-white transition-colors">
                사업공고
              </Link>
              <Link href="/" className="px-6 py-4 text-sm font-medium text-gray-700 hover:text-blue-900 hover:bg-white transition-colors">
                양식마당
              </Link>
              <Link href="/" className="px-6 py-4 text-sm font-medium text-gray-700 hover:text-blue-900 hover:bg-white transition-colors">
                민원지원
              </Link>
              <Link href="/" className="px-6 py-4 text-sm font-medium text-gray-700 hover:text-blue-900 hover:bg-white transition-colors">
                고객센터
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Carousel Section - 추천 공고 (2행 3열 유지) */}
      <div className="bg-gray-50 py-8">
        <div className="container mx-auto px-6">
          <AutoSlideCarousel
            announcements={carouselAnnouncements}
            onAnnouncementClick={handleAnnouncementClick}
          />
        </div>
      </div>

      {/* Main Content - K-Startup Style */}
      <main className="flex-1 container mx-auto px-6 py-8">
        {/* 가로 필터 영역 - 스크롤 시 상단 고정 */}
        <div className="sticky top-0 z-10 bg-white pb-6 mb-6">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-4 flex-wrap">
              {/* AI 검색 토글 */}
              <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg border border-purple-200">
                <input
                  type="checkbox"
                  id="ai-search"
                  checked={useAISearch}
                  onChange={(e) => setUseAISearch(e.target.checked)}
                  className="w-4 h-4 accent-purple-600 flex-shrink-0"
                />
                <label htmlFor="ai-search" className="text-sm font-medium text-purple-900 cursor-pointer flex items-center gap-1.5">
                  <span>✨</span>
                  <span>AI 검색</span>
                </label>
              </div>

              {/* 상태 필터 */}
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value as 'all' | 'ongoing' | 'deadline' })}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">전체</option>
                <option value="ongoing">진행중</option>
                <option value="deadline">마감임박</option>
              </select>

              {/* 지원분야 */}
              {filterOptions.categories && filterOptions.categories.length > 0 && (
                <select
                  value={filters.category || ''}
                  onChange={(e) => setFilters({ ...filters, category: e.target.value || undefined })}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">지원분야 전체</option>
                  {filterOptions.categories.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              )}

              {/* 지역 */}
              {filterOptions.regions && filterOptions.regions.length > 0 && (
                <select
                  value={filters.region || ''}
                  onChange={(e) => setFilters({ ...filters, region: e.target.value || undefined })}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">지역 전체</option>
                  {filterOptions.regions.map((region) => (
                    <option key={region} value={region}>{region}</option>
                  ))}
                </select>
              )}

              {/* 검색 영역 - ml-auto로 오른쪽 정렬 */}
              <div className="flex items-center gap-2 ml-auto">
                <div className="relative">
                  <Search className="absolute left-4 top-3.5 h-5 w-5 text-gray-400" />
                  <Input
                    type="text"
                    placeholder="검색어를 입력하세요"
                    className="pl-12 h-12 text-base w-[300px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={handleKeyPress}
                  />
                </div>

                <Button
                  onClick={useAISearch ? handleSemanticSearch : handleSearch}
                  className="bg-blue-600 hover:bg-blue-700 h-12 px-8"
                >
                  검색
                </Button>
              </div>

              {/* 정렬 드롭다운 (맨 오른쪽 끝) */}
              <select
                value={filters.sort || 'newest'}
                onChange={(e) => setFilters({ ...filters, sort: e.target.value as 'newest' | 'deadline' })}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="newest">최신순</option>
                <option value="deadline">마감순</option>
              </select>
            </div>
          </CardContent>
        </Card>
        </div>

        {/* 2열 레이아웃: 공고 리스트 + 최근 본 공고 */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6">
          {/* 왼쪽: 리스트 형식 공고 목록 */}
          <div>
            {loading ? (
              <div className="text-center py-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
                <p className="mt-4 text-gray-600">로딩 중...</p>
              </div>
            ) : error ? (
              <div className="text-center py-20">
                <p className="text-red-600">{error}</p>
              </div>
            ) : announcements.length === 0 ? (
              <div className="text-center py-20">
                <p className="text-gray-600">검색 결과가 없습니다.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {announcements.map((announcement) => {
                  const dday = calculateDday(announcement.end_date);
                  const isDeadlineSoon = dday >= 0 && dday <= 7;

                  return (
                    <div
                      key={announcement.id}
                      onClick={() => handleAnnouncementClick(announcement)}
                      className="bg-white border border-gray-200 rounded-lg p-5 hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
                    >
                      <div className="flex items-start gap-4">
                        {/* 왼쪽: 카테고리 배지 + D-Day */}
                        <div className="flex flex-col items-start gap-2 min-w-[100px]">
                          {announcement.category && (
                            <span className={`px-3 py-1 rounded text-xs font-semibold ${getCategoryColor(announcement.category)}`}>
                              {announcement.category}
                            </span>
                          )}
                          {announcement.status === 'ongoing' && (
                            <Badge className={`${isDeadlineSoon ? 'bg-red-500' : 'bg-blue-500'} text-white font-bold text-xs`}>
                              D-{dday}
                            </Badge>
                          )}
                        </div>

                        {/* 중앙: 제목 + 기관 */}
                        <div className="flex-1 min-w-0">
                          <h3 className="text-base font-bold text-gray-900 mb-1 truncate">
                            {announcement.title}
                          </h3>
                          <p className="text-sm text-gray-600 flex items-center gap-2">
                            <Building2 className="h-4 w-4" />
                            <span>{announcement.organization}</span>
                          </p>
                        </div>

                        {/* 오른쪽: 날짜 정보 + 북마크 */}
                        <div className="flex items-start gap-3">
                          <div className="flex flex-col items-end gap-1 min-w-[150px] text-sm text-gray-600">
                            <div className="flex items-center gap-1">
                              <Calendar className="h-4 w-4" />
                              <span>{new Date(announcement.start_date).toLocaleDateString('ko-KR')} ~ {new Date(announcement.end_date).toLocaleDateString('ko-KR')}</span>
                            </div>
                            <div className="text-xs text-gray-500">
                              마감: {new Date(announcement.end_date).toLocaleDateString('ko-KR')}
                            </div>
                          </div>
                          <div onClick={(e) => e.stopPropagation()}>
                            <BookmarkButton
                              announcementId={announcement.id}
                              announcementSource={announcement.source === 'K-Startup' ? 'kstartup' : 'bizinfo'}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 오른쪽: 최근 본 공고 사이드바 */}
          <div className="lg:sticky lg:top-[200px] h-fit">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Clock className="h-5 w-5" />
                  최근 본 공고
                </CardTitle>
              </CardHeader>
              <CardContent>
                {recentViews.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">
                    최근 본 공고가 없습니다
                  </p>
                ) : (
                  <div className="space-y-3">
                    {recentViews.slice(0, 4).map((item) => {
                      const dday = calculateDday(item.end_date);

                      return (
                        <div
                          key={item.id}
                          onClick={() => router.push(`/announcement/${item.id}`)}
                          className="p-3 border border-gray-200 rounded-lg hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
                        >
                          {item.category && (
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${getCategoryColor(item.category)} inline-block mb-2`}>
                              {item.category}
                            </span>
                          )}
                          {item.status === 'ongoing' && dday >= 0 && (
                            <Badge className={`${dday <= 7 ? 'bg-red-500' : 'bg-blue-500'} text-white font-bold text-xs ml-2`}>
                              D-{dday}
                            </Badge>
                          )}
                          <h4 className="text-sm font-bold text-gray-900 mb-1 line-clamp-2">
                            {item.title}
                          </h4>
                          <p className="text-xs text-gray-600 truncate">
                            {item.organization}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            마감: {new Date(item.end_date).toLocaleDateString('ko-KR')}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* 페이지네이션 */}
        {announcements.length > 0 && totalPages >= 1 && (
          <div className="mt-8 flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1 || loading}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            {Array.from({ length: Math.max(1, Math.min(5, totalPages)) }, (_, i) => {
              let pageNum;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (currentPage <= 3) {
                pageNum = i + 1;
              } else if (currentPage >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = currentPage - 2 + i;
              }

              return (
                <Button
                  key={pageNum}
                  variant={currentPage === pageNum ? 'default' : 'outline'}
                  onClick={() => handlePageChange(pageNum)}
                  disabled={loading}
                  className={currentPage === pageNum ? 'bg-blue-600 hover:bg-blue-700' : ''}
                >
                  {pageNum}
                </Button>
              );
            })}

            <Button
              variant="outline"
              size="icon"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages || loading}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </main>

      {/* Footer - K-Startup Style */}
      <footer className="bg-gray-800 text-white mt-auto">
        {/* 상단 푸터 - 링크 섹션 */}
        <div className="border-b border-gray-700">
          <div className="container mx-auto px-6 py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6 text-sm">
                <Link href="/privacy" className="hover:text-blue-400 transition-colors">
                  개인정보처리방침
                </Link>
                <span className="text-gray-600">|</span>
                <Link href="/terms" className="hover:text-blue-400 transition-colors">
                  이용약관
                </Link>
                <span className="text-gray-600">|</span>
                <Link href="/support" className="hover:text-blue-400 transition-colors">
                  고객센터
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* 하단 푸터 - 관련기관 링크 */}
        <div className="bg-gray-900">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6 text-xs text-gray-400">
                <Link href="https://www.mss.go.kr" target="_blank" className="hover:text-blue-400 transition-colors">
                  중소벤처기업부
                </Link>
                <span className="text-gray-600">|</span>
                <Link href="https://www.kised.or.kr" target="_blank" className="hover:text-blue-400 transition-colors">
                  창업진흥원
                </Link>
                <span className="text-gray-600">|</span>
                <Link href="https://www.kosmes.or.kr" target="_blank" className="hover:text-blue-400 transition-colors">
                  중소벤처기업진흥공단
                </Link>
                <span className="text-gray-600">|</span>
                <Link href="https://www.k-startup.go.kr" target="_blank" className="hover:text-blue-400 transition-colors">
                  K-Startup
                </Link>
                <span className="text-gray-600">|</span>
                <Link href="https://www.bizinfo.go.kr" target="_blank" className="hover:text-blue-400 transition-colors">
                  BizInfo
                </Link>
              </div>
              <div className="text-xs text-gray-500">
                © 2025 로튼. All rights reserved.
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
