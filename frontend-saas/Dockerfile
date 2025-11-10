# ================================================
# Next.js 15 SaaS Frontend Dockerfile (Multi-Stage Build)
# ================================================
# Stage 1: Dependencies 설치
FROM node:20-alpine AS deps

# pnpm 설치
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# 의존성 파일 복사 (캐싱 최적화)
COPY package.json pnpm-lock.yaml* ./

# 의존성 설치 (프로덕션 전용)
RUN pnpm install --frozen-lockfile --prod=false

# ================================================
# Stage 2: Builder (빌드 단계)
# ================================================
FROM node:20-alpine AS builder

# pnpm 설치
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# 의존성 복사
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 환경변수 설정 (빌드 시점)
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Next.js 빌드
RUN pnpm build

# ================================================
# Stage 3: Runner (실행 단계)
# ================================================
FROM node:20-alpine AS runner

# pnpm 설치
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# 보안을 위한 non-root 사용자 생성
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# 환경변수 설정
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# 필수 파일만 복사
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# non-root 사용자로 전환
USER nextjs

# 포트 노출
EXPOSE 3000

# Health check 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# 애플리케이션 실행
CMD ["node", "server.js"]
