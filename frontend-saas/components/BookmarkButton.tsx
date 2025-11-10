'use client';

import { useState } from 'react';
import { Heart } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface BookmarkButtonProps {
  announcementId: string;
  announcementSource: 'kstartup' | 'bizinfo';
  initialBookmarked?: boolean;
  bookmarkId?: string | null;
  onToggle?: (isBookmarked: boolean) => void;
  className?: string;
}

export function BookmarkButton({
  announcementId,
  announcementSource,
  initialBookmarked = false,
  bookmarkId: initialBookmarkId = null,
  onToggle,
  className = ''
}: BookmarkButtonProps) {
  const [isBookmarked, setIsBookmarked] = useState(initialBookmarked);
  const [bookmarkId, setBookmarkId] = useState(initialBookmarkId);
  const [isLoading, setIsLoading] = useState(false);

  const handleToggle = async () => {
    setIsLoading(true);
    try {
      if (isBookmarked && bookmarkId) {
        // 북마크 삭제
        const response = await fetch(`/api/bookmarks/${bookmarkId}`, {
          method: 'DELETE',
          headers: {
            'X-User-ID': 'temp-user-id', // TODO: 실제 세션에서 user_id 가져오기
          },
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || '북마크 삭제 실패');
        }

        setIsBookmarked(false);
        setBookmarkId(null);
        onToggle?.(false);
      } else {
        // 북마크 추가
        const response = await fetch(
          `/api/bookmarks?announcement_id=${announcementId}&announcement_source=${announcementSource}`,
          {
            method: 'POST',
            headers: {
              'X-User-ID': 'temp-user-id', // TODO: 실제 세션에서 user_id 가져오기
            },
          }
        );

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || '북마크 추가 실패');
        }

        const data = await response.json();
        setIsBookmarked(true);
        setBookmarkId(data.id);
        onToggle?.(true);
      }
    } catch (error) {
      console.error('Bookmark error:', error);
      alert(error instanceof Error ? error.message : '북마크 처리 중 오류가 발생했습니다');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleToggle}
      disabled={isLoading}
      className={`group relative ${className}`}
    >
      <Heart
        className={`h-5 w-5 transition-all ${
          isBookmarked
            ? 'fill-red-500 text-red-500'
            : 'text-gray-400 group-hover:text-red-500'
        } ${isLoading ? 'animate-pulse' : ''}`}
      />
      <span className="sr-only">
        {isBookmarked ? '북마크 해제' : '북마크 추가'}
      </span>
    </Button>
  );
}
