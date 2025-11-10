-- =====================================================
-- 즐겨찾기(Bookmarks) 테이블 생성
-- =====================================================
-- 작성일: 2025-11-10
-- 목적: 사용자별 공고 북마크 기능 구현
-- RLS: 사용자는 자신의 북마크만 조회/추가/삭제 가능
-- =====================================================

-- 1. 테이블 생성
CREATE TABLE IF NOT EXISTS bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    announcement_id TEXT NOT NULL,
    announcement_source TEXT NOT NULL CHECK (announcement_source IN ('kstartup', 'bizinfo')),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- 중복 북마크 방지 (동일 사용자가 같은 공고를 중복으로 북마크할 수 없음)
    UNIQUE(user_id, announcement_id, announcement_source)
);

-- 2. RLS (Row Level Security) 활성화
ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;

-- 3. RLS 정책 생성

-- 정책 1: 사용자는 자신의 북마크만 조회 가능
CREATE POLICY "Users can view own bookmarks"
ON bookmarks FOR SELECT
USING (auth.uid() = user_id);

-- 정책 2: 사용자는 자신의 북마크만 추가 가능
CREATE POLICY "Users can insert own bookmarks"
ON bookmarks FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- 정책 3: 사용자는 자신의 북마크만 삭제 가능
CREATE POLICY "Users can delete own bookmarks"
ON bookmarks FOR DELETE
USING (auth.uid() = user_id);

-- 4. 인덱스 생성 (성능 최적화)

-- 사용자별 북마크 조회 최적화
CREATE INDEX idx_bookmarks_user_id ON bookmarks(user_id);

-- 공고별 북마크 여부 확인 최적화
CREATE INDEX idx_bookmarks_announcement ON bookmarks(announcement_id, announcement_source);

-- 최신 북마크 조회 최적화 (생성일 내림차순)
CREATE INDEX idx_bookmarks_created_at ON bookmarks(created_at DESC);

-- 복합 인덱스: 사용자별 최신 북마크 조회 최적화
CREATE INDEX idx_bookmarks_user_created ON bookmarks(user_id, created_at DESC);

-- 5. 테이블 주석
COMMENT ON TABLE bookmarks IS '사용자 공고 북마크 테이블 (K-Startup, BizInfo 통합)';
COMMENT ON COLUMN bookmarks.id IS '북마크 고유 ID';
COMMENT ON COLUMN bookmarks.user_id IS '사용자 ID (auth.users 참조)';
COMMENT ON COLUMN bookmarks.announcement_id IS '공고 ID (KS_175399, PBLN_000000000116027 등)';
COMMENT ON COLUMN bookmarks.announcement_source IS '공고 출처 (kstartup 또는 bizinfo)';
COMMENT ON COLUMN bookmarks.created_at IS '북마크 생성 시각';

-- =====================================================
-- 실행 방법:
-- 1. Supabase Dashboard 접속
-- 2. SQL Editor 열기
-- 3. 이 파일 내용 복사하여 붙여넣기
-- 4. Run 버튼 클릭
--
-- 검증 방법:
-- SELECT * FROM bookmarks LIMIT 5;
-- SELECT tablename, policyname FROM pg_policies WHERE tablename = 'bookmarks';
-- =====================================================
