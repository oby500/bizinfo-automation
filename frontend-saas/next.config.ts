import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: false,  // API 중복 호출 방지 (개발 모드 최적화)
  typescript: {
    ignoreBuildErrors: true,
  },
  experimental: {
    ppr: true,
    clientSegmentCache: true,
    nodeMiddleware: true
  }
};

export default nextConfig;
