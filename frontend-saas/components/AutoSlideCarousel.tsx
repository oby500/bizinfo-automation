'use client';

import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

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

interface AutoSlideCarouselProps {
  announcements: Announcement[];
  onAnnouncementClick?: (announcement: Announcement) => void;
}

export default function AutoSlideCarousel({ announcements, onAnnouncementClick }: AutoSlideCarouselProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  const ITEMS_PER_VIEW = 6; // 한 화면에 6개씩 표시 (2행 × 3열)
  const AUTO_SLIDE_INTERVAL = 5000; // 5초마다 자동 슬라이드
  const COLS = 3; // 3열

  // D-Day 계산
  const calculateDday = (endDate: string) => {
    const today = new Date();
    const end = new Date(endDate);
    const diffTime = end.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  // 카테고리별 색상 (청색 + 회색 계열)
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

  // 자동 슬라이드 (5초마다 1페이지씩) - 왼쪽으로 부드럽게
  useEffect(() => {
    if (isHovered || announcements.length <= ITEMS_PER_VIEW) return;

    const interval = setInterval(() => {
      setCurrentIndex((prevIndex) => {
        const totalPages = Math.ceil(announcements.length / ITEMS_PER_VIEW);
        const nextIndex = prevIndex + 1;

        if (nextIndex >= totalPages) {
          return 0;
        }
        return nextIndex;
      });
    }, AUTO_SLIDE_INTERVAL);

    return () => clearInterval(interval);
  }, [isHovered, announcements.length, ITEMS_PER_VIEW]);

  // 이전 버튼
  const handlePrev = () => {
    setCurrentIndex((prevIndex) => {
      const totalPages = Math.ceil(announcements.length / ITEMS_PER_VIEW);
      if (prevIndex === 0) {
        return totalPages - 1;
      }
      return prevIndex - 1;
    });
  };

  // 다음 버튼
  const handleNext = () => {
    setCurrentIndex((prevIndex) => {
      const totalPages = Math.ceil(announcements.length / ITEMS_PER_VIEW);
      const nextIndex = prevIndex + 1;
      if (nextIndex >= totalPages) {
        return 0;
      }
      return nextIndex;
    });
  };

  if (announcements.length === 0) {
    return null;
  }

  // 총 페이지 수
  const totalPages = Math.ceil(announcements.length / ITEMS_PER_VIEW);

  return (
    <div
      className="relative mb-8"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* 캐러셀 헤더 */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">🔥 추천 공고</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">
            {currentIndex * ITEMS_PER_VIEW + 1} - {Math.min((currentIndex + 1) * ITEMS_PER_VIEW, announcements.length)} / {announcements.length}
          </span>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={handlePrev}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={handleNext}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* 캐러셀 콘텐츠 - 2행 × 3열 그리드 (왼쪽으로 슬라이드) */}
      <div className="overflow-hidden">
        <div
          className="flex transition-transform duration-700 ease-in-out"
          style={{
            transform: `translateX(-${currentIndex * 100}%)`
          }}
        >
          {Array.from({ length: totalPages }).map((_, pageIndex) => (
            <div
              key={pageIndex}
              className="grid grid-cols-3 grid-rows-2 gap-4 flex-shrink-0"
              style={{ width: '100%' }}
            >
              {announcements
                .slice(pageIndex * ITEMS_PER_VIEW, (pageIndex + 1) * ITEMS_PER_VIEW)
                .map((announcement) => (
                  <Card
                    key={announcement.id}
                    className="hover:shadow-lg transition-all border-2 hover:border-orange-300 cursor-pointer"
                    onClick={() => onAnnouncementClick?.(announcement)}
                  >
                    <CardContent className="p-4">
                      {/* 카테고리 + D-Day */}
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex flex-wrap gap-2">
                          {announcement.category && (
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${getCategoryColor(announcement.category)}`}>
                              {announcement.category}
                            </span>
                          )}
                        </div>

                        {announcement.status === 'ongoing' && (
                          <Badge className="bg-red-500 text-white font-bold text-xs">
                            D-{calculateDday(announcement.end_date)}
                          </Badge>
                        )}
                      </div>

                      {/* 제목 */}
                      <h3 className="text-sm font-bold text-gray-900 mb-2 line-clamp-2 min-h-[2.5rem]">
                        {announcement.title}
                      </h3>

                      {/* 기관 */}
                      <p className="text-xs text-gray-600 truncate">
                        {announcement.organization}
                      </p>

                      {/* 마감일 */}
                      <div className="mt-2 pt-2 border-t text-xs text-gray-500">
                        마감: {new Date(announcement.end_date).toLocaleDateString('ko-KR')}
                      </div>
                    </CardContent>
                  </Card>
                ))}
            </div>
          ))}
        </div>
      </div>

      {/* 진행 인디케이터 (점) */}
      <div className="flex justify-center gap-2 mt-4">
        {Array.from({ length: totalPages }).map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentIndex(index)}
            className={`h-2 rounded-full transition-all ${
              currentIndex === index
                ? 'w-8 bg-orange-500'
                : 'w-2 bg-gray-300 hover:bg-gray-400'
            }`}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
}
