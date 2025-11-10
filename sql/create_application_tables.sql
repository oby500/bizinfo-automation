-- ============================================================================
-- 신청서 작성 시스템 데이터베이스 스키마
-- ============================================================================
-- 작성일: 2025-01-19
-- 참고: Development guide · MD.txt
-- 용도: Supabase PostgreSQL
-- ============================================================================

-- 1. users 테이블 (사용자)
-- 참고: Supabase Auth와 연동하여 사용
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- users 테이블 코멘트
COMMENT ON TABLE users IS '사용자 정보 (Supabase Auth 연동)';
COMMENT ON COLUMN users.id IS '사용자 고유 ID (UUID)';
COMMENT ON COLUMN users.email IS '이메일 (로그인 ID)';
COMMENT ON COLUMN users.name IS '사용자 이름';

-- ============================================================================

-- 2. modification_credits 테이블 (수정권 잔액)
CREATE TABLE IF NOT EXISTS modification_credits (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER DEFAULT 0 CHECK (balance >= 0),
    total_purchased INTEGER DEFAULT 0,
    total_used INTEGER DEFAULT 0,
    expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE modification_credits IS '수정권 잔액 관리';
COMMENT ON COLUMN modification_credits.balance IS '현재 보유 수정권 개수';
COMMENT ON COLUMN modification_credits.total_purchased IS '총 구매한 수정권';
COMMENT ON COLUMN modification_credits.total_used IS '총 사용한 수정권';
COMMENT ON COLUMN modification_credits.expires_at IS '수정권 만료일';

-- ============================================================================

-- 3. orders 테이블 (주문)
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tier TEXT NOT NULL CHECK (tier IN ('basic', 'standard', 'premium')),
    amount INTEGER NOT NULL CHECK (amount > 0),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'refunded')),
    payment_method TEXT,
    payment_key TEXT, -- PortOne 결제 키
    created_at TIMESTAMPTZ DEFAULT now(),
    paid_at TIMESTAMPTZ
);

COMMENT ON TABLE orders IS '결제 주문 정보';
COMMENT ON COLUMN orders.tier IS '선택한 티어 (basic/standard/premium)';
COMMENT ON COLUMN orders.amount IS '결제 금액 (원)';
COMMENT ON COLUMN orders.status IS '결제 상태';
COMMENT ON COLUMN orders.payment_key IS 'PortOne 결제 고유 키';

-- orders 인덱스
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);

-- ============================================================================

-- 4. applications 테이블 (신청서 프로젝트)
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    tier TEXT NOT NULL CHECK (tier IN ('basic', 'standard', 'premium')),

    -- 공고 정보
    announcement_id TEXT, -- PBLN_xxx or announcement_id
    announcement_source TEXT CHECK (announcement_source IN ('kstartup', 'bizinfo')),
    announcement_url TEXT,
    announcement_text TEXT,
    announcement_analysis JSONB, -- Claude 분석 결과

    -- 회사 정보 (Z)
    company_info JSONB, -- Z_COMPANY_INFO_SCHEMA.md 참고
    company_analysis JSONB, -- Claude 분석 결과

    -- 생성된 문서들
    documents JSONB, -- [{ style, content, version, word_count, tables }]

    -- AI 추천 (Standard, Premium)
    ai_recommendation JSONB, -- Claude 스타일 추천 결과

    -- 메타
    status TEXT DEFAULT 'processing' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    current_step TEXT, -- 'analyzing', 'generating', 'finalizing'
    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE applications IS '신청서 프로젝트 (메인 테이블)';
COMMENT ON COLUMN applications.tier IS '결제한 티어';
COMMENT ON COLUMN applications.announcement_analysis IS 'Claude Sonnet 4.5 공고 분석 결과';
COMMENT ON COLUMN applications.company_info IS 'Z (회사 정보) JSONB';
COMMENT ON COLUMN applications.company_analysis IS 'Claude Sonnet 4.5 회사 분석 결과';
COMMENT ON COLUMN applications.documents IS 'GPT-4o 생성 신청서들 (티어별 개수)';
COMMENT ON COLUMN applications.ai_recommendation IS 'Claude 스타일 추천 (Standard, Premium)';
COMMENT ON COLUMN applications.progress IS '생성 진행률 (0-100)';

-- applications 인덱스
CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_created ON applications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_announcement ON applications(announcement_id);

-- ============================================================================

-- 5. document_versions 테이블 (버전 관리)
CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version >= 1),
    style TEXT NOT NULL CHECK (style IN ('data', 'story', 'balanced', 'aggressive', 'conservative')),
    content TEXT NOT NULL,
    metadata JSONB, -- { word_count, tables, sections, ... }
    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(application_id, version, style)
);

COMMENT ON TABLE document_versions IS '신청서 버전 관리';
COMMENT ON COLUMN document_versions.version IS '버전 번호 (1부터 시작)';
COMMENT ON COLUMN document_versions.style IS '작성 스타일';
COMMENT ON COLUMN document_versions.content IS '신청서 전체 텍스트';
COMMENT ON COLUMN document_versions.metadata IS '글자 수, 표 개수 등 메타데이터';

-- document_versions 인덱스
CREATE INDEX IF NOT EXISTS idx_document_versions_app ON document_versions(application_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_created ON document_versions(created_at DESC);

-- ============================================================================

-- 6. modifications 테이블 (수정 히스토리)
CREATE TABLE IF NOT EXISTS modifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    document_id UUID REFERENCES document_versions(id) ON DELETE SET NULL,
    instruction TEXT NOT NULL, -- 사용자 수정 요청 내용
    before_content TEXT,
    after_content TEXT,
    cost DECIMAL(10,4), -- USD
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE modifications IS '신청서 수정 히스토리';
COMMENT ON COLUMN modifications.instruction IS '사용자가 요청한 수정 내용';
COMMENT ON COLUMN modifications.before_content IS '수정 전 내용';
COMMENT ON COLUMN modifications.after_content IS '수정 후 내용';
COMMENT ON COLUMN modifications.cost IS 'AI 수정 비용 (USD)';
COMMENT ON COLUMN modifications.tokens_used IS '사용된 토큰 수';

-- modifications 인덱스
CREATE INDEX IF NOT EXISTS idx_modifications_app ON modifications(application_id);
CREATE INDEX IF NOT EXISTS idx_modifications_user ON modifications(user_id);
CREATE INDEX IF NOT EXISTS idx_modifications_created ON modifications(created_at DESC);

-- ============================================================================

-- 7. analysis_cache 테이블 (공고 분석 캐시)
-- 동일한 공고는 재분석하지 않고 캐시 사용
CREATE TABLE IF NOT EXISTS analysis_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    announcement_id TEXT NOT NULL,
    announcement_source TEXT NOT NULL CHECK (announcement_source IN ('kstartup', 'bizinfo')),
    analysis JSONB NOT NULL, -- Claude 분석 결과
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ, -- 캐시 만료일 (예: 7일 후)

    UNIQUE(announcement_id, announcement_source)
);

COMMENT ON TABLE analysis_cache IS '공고 분석 결과 캐시 (비용 절감)';
COMMENT ON COLUMN analysis_cache.announcement_id IS '공고 ID (PBLN_xxx or announcement_id)';
COMMENT ON COLUMN analysis_cache.expires_at IS '캐시 만료일 (일반적으로 7일)';

-- analysis_cache 인덱스
CREATE INDEX IF NOT EXISTS idx_analysis_cache_announcement ON analysis_cache(announcement_id, announcement_source);
CREATE INDEX IF NOT EXISTS idx_analysis_cache_expires ON analysis_cache(expires_at);

-- ============================================================================

-- 8. updated_at 자동 업데이트 트리거 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- users 테이블 트리거
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- modification_credits 테이블 트리거
DROP TRIGGER IF EXISTS update_modification_credits_updated_at ON modification_credits;
CREATE TRIGGER update_modification_credits_updated_at
    BEFORE UPDATE ON modification_credits
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- applications 테이블 트리거
DROP TRIGGER IF EXISTS update_applications_updated_at ON applications;
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================

-- 9. Row Level Security (RLS) 설정
-- Supabase에서 사용자별 데이터 접근 제어

-- users 테이블 RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
    ON users FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON users FOR UPDATE
    USING (auth.uid() = id);

-- modification_credits 테이블 RLS
ALTER TABLE modification_credits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own credits"
    ON modification_credits FOR SELECT
    USING (auth.uid() = user_id);

-- orders 테이블 RLS
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own orders"
    ON orders FOR SELECT
    USING (auth.uid() = user_id);

-- applications 테이블 RLS
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own applications"
    ON applications FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own applications"
    ON applications FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own applications"
    ON applications FOR UPDATE
    USING (auth.uid() = user_id);

-- document_versions 테이블 RLS
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own document versions"
    ON document_versions FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM applications
            WHERE applications.id = document_versions.application_id
            AND applications.user_id = auth.uid()
        )
    );

-- modifications 테이블 RLS
ALTER TABLE modifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own modifications"
    ON modifications FOR SELECT
    USING (auth.uid() = user_id);

-- analysis_cache는 RLS 불필요 (공용 캐시)

-- ============================================================================

-- 10. 초기 데이터 (개발/테스트용)
-- 프로덕션에서는 주석 처리 또는 제거

-- 테스트 사용자 생성 예시 (Supabase Auth에서 생성해야 함)
-- INSERT INTO users (id, email, name) VALUES
--     ('00000000-0000-0000-0000-000000000001', 'test@example.com', '테스트 사용자')
-- ON CONFLICT (id) DO NOTHING;

-- ============================================================================

-- 완료 메시지
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE '신청서 작성 시스템 테이블 생성 완료!';
    RAISE NOTICE '============================================';
    RAISE NOTICE '생성된 테이블:';
    RAISE NOTICE '  1. users (사용자)';
    RAISE NOTICE '  2. modification_credits (수정권)';
    RAISE NOTICE '  3. orders (주문)';
    RAISE NOTICE '  4. applications (신청서 프로젝트)';
    RAISE NOTICE '  5. document_versions (버전 관리)';
    RAISE NOTICE '  6. modifications (수정 히스토리)';
    RAISE NOTICE '  7. analysis_cache (분석 캐시)';
    RAISE NOTICE '============================================';
    RAISE NOTICE '트리거: updated_at 자동 업데이트';
    RAISE NOTICE 'RLS: Row Level Security 활성화';
    RAISE NOTICE '============================================';
END $$;
