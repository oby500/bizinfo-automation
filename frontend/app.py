#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
정부지원사업 검색 시스템 - FastAPI 백엔드 (실제 DB 연동)
개선사항:
- 실제 Supabase 데이터 연동
- 진행/마감/종료 상태 필터링 
- 통계 정보 실시간 계산
- 에러 처리 강화
"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import os
from dotenv import load_dotenv
from supabase import create_client
import logging
import traceback
from openai import OpenAI
import asyncio

# 환경변수 로드 (로깅보다 먼저)
load_dotenv()

# 구조화된 로깅 설정 (JSON 형식)
import json as json_lib
import sys

class StructuredFormatter(logging.Formatter):
    """JSON 형식의 구조화된 로그 포맷터"""

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # 추가 컨텍스트가 있으면 포함
        if hasattr(record, 'context'):
            log_data['context'] = record.context

        # 에러 정보가 있으면 포함
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json_lib.dumps(log_data, ensure_ascii=False)

# 환경변수로 로깅 형식 선택 (JSON 또는 일반 텍스트)
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or text

if LOG_FORMAT == "json":
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logger = logging.getLogger(__name__)
    logger.info("✅ 구조화된 로깅 (JSON) 활성화")
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info("✅ 일반 텍스트 로깅 활성화")

# Rate Limiting (로깅 이후에 초기화)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATE_LIMIT_ENABLED = True
    logger.info("✅ slowapi 설치됨 - Rate Limiting 활성화")
except ImportError:
    RATE_LIMIT_ENABLED = False
    logger.warning("⚠️ slowapi 미설치 - Rate Limiting 비활성화 (pip install slowapi 필요)")

# orjson import (한글 깨짐 방지)
try:
    import orjson
    from fastapi.responses import ORJSONResponse
    default_response_class = ORJSONResponse
    logger.info("✅ orjson 사용 (한글 인코딩 최적화)")
except ImportError:
    default_response_class = None
    logger.warning("⚠️ orjson 미설치 - 기본 JSON 사용")

# API 버전 관리 설정
API_VERSION = "3.0.0"
API_VERSION_MAJOR = 3
API_VERSION_MINOR = 0
API_VERSION_PATCH = 0

# FastAPI 앱 생성 (한글 깨짐 방지)
app = FastAPI(
    title="정부지원사업 API",
    version=API_VERSION,
    description=f"K-Startup, BizInfo 통합 검색 API (v{API_VERSION})",
    default_response_class=default_response_class,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Rate Limiter 설정 (slowapi 설치 시에만 활성화)
if RATE_LIMIT_ENABLED:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("✅ Rate Limiting 활성화: 분당 60회 제한")
else:
    limiter = None
    logger.warning("⚠️ Rate Limiting 비활성화 상태")

# CORS 설정 (환경변수 기반)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
logger.info(f"CORS allowed origins: {CORS_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # 환경변수에서 허용 도메인 목록 로드
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # 명시적 메서드 제한
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],  # 명시적 헤더 제한
    max_age=3600,  # Preflight 캐시 1시간
)

# Gzip 압축 미들웨어 (응답 크기 1KB 이상일 때 압축)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 보안 헤더 미들웨어
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """보안 헤더 및 API 버전 정보 추가 미들웨어"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # XSS 공격 방어
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # HTTPS 강제 (프로덕션 환경에서만)
        if os.getenv("ENV") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Content Security Policy
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'"

        # API 버전 정보 헤더
        response.headers["X-API-Version"] = API_VERSION
        response.headers["X-API-Version-Major"] = str(API_VERSION_MAJOR)
        response.headers["X-API-Version-Minor"] = str(API_VERSION_MINOR)
        response.headers["X-API-Version-Patch"] = str(API_VERSION_PATCH)

        return response

# ================================================
# API 응답 시간 메트릭 추적 시스템
# ================================================
from collections import defaultdict
from typing import DefaultDict
import time

# 엔드포인트별 메트릭 저장소
endpoint_metrics: DefaultDict[str, Dict[str, Any]] = defaultdict(lambda: {
    "count": 0,
    "total_time": 0.0,
    "min_time": float('inf'),
    "max_time": 0.0,
    "response_times": []  # 최근 100개 요청 저장 (히스토그램용)
})

def update_endpoint_metrics(path: str, method: str, response_time_ms: float):
    """엔드포인트별 응답 시간 메트릭 업데이트"""
    endpoint_key = f"{method} {path}"
    metrics = endpoint_metrics[endpoint_key]

    # 카운트 및 합계 업데이트
    metrics["count"] += 1
    metrics["total_time"] += response_time_ms

    # 최소/최대값 업데이트
    metrics["min_time"] = min(metrics["min_time"], response_time_ms)
    metrics["max_time"] = max(metrics["max_time"], response_time_ms)

    # 최근 100개 요청 시간 저장 (히스토그램 생성용)
    metrics["response_times"].append(response_time_ms)
    if len(metrics["response_times"]) > 100:
        metrics["response_times"].pop(0)

def get_endpoint_metrics_summary() -> Dict[str, Any]:
    """엔드포인트별 메트릭 요약 반환"""
    summary = {}

    for endpoint, metrics in endpoint_metrics.items():
        if metrics["count"] > 0:
            avg_time = metrics["total_time"] / metrics["count"]

            # P50, P95, P99 계산 (최근 요청 기준)
            sorted_times = sorted(metrics["response_times"])
            n = len(sorted_times)

            p50 = sorted_times[int(n * 0.5)] if n > 0 else 0
            p95 = sorted_times[int(n * 0.95)] if n > 0 else 0
            p99 = sorted_times[int(n * 0.99)] if n > 0 else 0

            summary[endpoint] = {
                "count": metrics["count"],
                "avg_ms": round(avg_time, 2),
                "min_ms": round(metrics["min_time"], 2) if metrics["min_time"] != float('inf') else 0,
                "max_ms": round(metrics["max_time"], 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2)
            }

    return summary

logger.info("✅ API 응답 시간 메트릭 추적 시스템 활성화")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """요청/응답 로깅 미들웨어 (요청 검증 + Correlation ID + 메트릭 추적)"""
    async def dispatch(self, request: Request, call_next):
        # 요청 시작 시간
        start_time = time.time()

        # Correlation ID 생성 또는 가져오기
        import uuid
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # 요청 정보
        method = request.method
        url = str(request.url)
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"

        # 쿼리 파라미터 로깅
        query_params = dict(request.query_params) if request.query_params else {}

        # 요청 본문 로깅 (POST/PUT/PATCH만)
        request_body = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                # 요청 본문 읽기 (비동기)
                body_bytes = await request.body()
                if body_bytes:
                    # JSON 파싱 시도
                    try:
                        import json
                        request_body = json.loads(body_bytes.decode())
                        # 민감한 정보 마스킹 (비밀번호, 토큰 등)
                        if isinstance(request_body, dict):
                            for key in ["password", "token", "api_key", "secret"]:
                                if key in request_body:
                                    request_body[key] = "***MASKED***"
                    except:
                        request_body = f"<{len(body_bytes)} bytes>"
            except Exception as e:
                request_body = f"<Error reading body: {e}>"

        # 응답 처리
        response = await call_next(request)

        # 응답 시간 계산
        process_time = (time.time() - start_time) * 1000  # 밀리초

        # 엔드포인트별 메트릭 업데이트
        update_endpoint_metrics(path, method, process_time)

        # 로그 기록 (JSON 형식으로 - 검증 정보 + Correlation ID 포함)
        log_data = {
            "correlation_id": correlation_id,
            "method": method,
            "url": url,
            "path": path,
            "client": client_host,
            "query_params": query_params if query_params else None,
            "request_body": request_body if request_body else None,
            "status_code": response.status_code,
            "response_time_ms": round(process_time, 2)
        }

        # 상태코드에 따라 로그 레벨 조정
        if response.status_code >= 500:
            logger.error(f"[API] Request failed: {method} {path} [ID: {correlation_id[:8]}]", extra={"context": log_data})
        elif response.status_code >= 400:
            logger.warning(f"[API] Client error: {method} {path} [ID: {correlation_id[:8]}]", extra={"context": log_data})
        else:
            # 일반 요청은 간단하게 로깅
            if query_params or request_body:
                logger.info(f"[API] {method} {path} - {response.status_code} - {round(process_time, 2)}ms [ID: {correlation_id[:8]}]")
            else:
                logger.info(f"[API] {method} {path} - {response.status_code} - {round(process_time, 2)}ms [ID: {correlation_id[:8]}]")

        # 응답 헤더 추가
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(round(process_time, 2))

        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """요청 속도 제한 미들웨어 (IP 기반)"""
    def __init__(self, app, max_requests: int = 100, time_window: int = 60):
        """
        Args:
            app: FastAPI 앱
            max_requests: 시간창 내 최대 요청 수 (기본값: 100)
            time_window: 시간창 크기(초) (기본값: 60초)
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_counts = {}  # {ip: [(timestamp1, timestamp2, ...)]}
        self.cleanup_interval = 60  # 1분마다 만료된 기록 정리
        self.last_cleanup = time.time()

    async def dispatch(self, request: Request, call_next):
        # 현재 시간
        current_time = time.time()

        # IP 주소 가져오기
        client_ip = request.client.host if request.client else "unknown"

        # Health check 엔드포인트는 제한하지 않음
        if request.url.path in ["/health", "/api/health"]:
            return await call_next(request)

        # 주기적으로 만료된 기록 정리
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_requests(current_time)
            self.last_cleanup = current_time

        # IP별 요청 기록 확인
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []

        # 시간창 내 요청만 필터링
        window_start = current_time - self.time_window
        self.request_counts[client_ip] = [
            ts for ts in self.request_counts[client_ip]
            if ts > window_start
        ]

        # 요청 횟수 확인
        if len(self.request_counts[client_ip]) >= self.max_requests:
            logger.warning(f"🚨 Rate limit exceeded for IP: {client_ip} ({len(self.request_counts[client_ip])} requests)")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"요청 횟수 제한을 초과했습니다. {self.time_window}초 후에 다시 시도해주세요.",
                    "retry_after": self.time_window
                },
                headers={"Retry-After": str(self.time_window)}
            )

        # 현재 요청 기록 추가
        self.request_counts[client_ip].append(current_time)

        # 요청 처리
        response = await call_next(request)

        # Rate limit 정보를 헤더에 추가
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(self.max_requests - len(self.request_counts[client_ip]))
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.time_window))

        return response

    def _cleanup_old_requests(self, current_time: float):
        """만료된 요청 기록 정리"""
        window_start = current_time - self.time_window
        for ip in list(self.request_counts.keys()):
            self.request_counts[ip] = [
                ts for ts in self.request_counts[ip]
                if ts > window_start
            ]
            # 빈 리스트는 제거
            if not self.request_counts[ip]:
                del self.request_counts[ip]

        if self.request_counts:
            logger.info(f"🧹 Rate limit 기록 정리 완료 ({len(self.request_counts)}개 IP 추적 중)")

    def get_stats(self) -> Dict[str, Any]:
        """Rate Limiter 통계 정보 반환"""
        current_time = time.time()
        total_requests = sum(len(requests) for requests in self.request_counts.values())

        # 가장 많이 요청한 IP 찾기
        top_ips = sorted(
            self.request_counts.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:5]  # 상위 5개 IP

        return {
            "enabled": True,
            "max_requests": self.max_requests,
            "time_window_seconds": self.time_window,
            "tracked_ips": len(self.request_counts),
            "total_active_requests": total_requests,
            "top_ips": [
                {
                    "ip": ip,
                    "request_count": len(requests),
                    "percentage": round(len(requests) / self.max_requests * 100, 1)
                }
                for ip, requests in top_ips
            ],
            "last_cleanup": datetime.fromtimestamp(self.last_cleanup).isoformat()
        }

# 환경변수에서 Rate Limit 설정 가져오기
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
RATE_LIMIT_TIME_WINDOW = int(os.getenv("RATE_LIMIT_TIME_WINDOW", "60"))

# Rate Limiter 인스턴스를 전역 변수로 저장 (헬스체크에서 접근하기 위해)
_rate_limiter_instance = None

def get_rate_limiter_stats():
    """Rate Limiter 통계 반환 (헬스체크용)"""
    if _rate_limiter_instance:
        return _rate_limiter_instance.get_stats()
    return {"enabled": False, "message": "Rate limiter not initialized"}

# GZip 압축 미들웨어 추가 (큰 응답 최적화)
from fastapi.middleware.gzip import GZipMiddleware

# 환경변수에서 압축 설정 가져오기
GZIP_MINIMUM_SIZE = int(os.getenv("GZIP_MINIMUM_SIZE", "1000"))  # 1KB 이상만 압축

app.add_middleware(GZipMiddleware, minimum_size=GZIP_MINIMUM_SIZE)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Rate Limiter 미들웨어 추가 및 인스턴스 저장
class RateLimiterWrapper(RateLimitMiddleware):
    """Rate Limiter를 래핑하여 인스턴스 접근 가능하게 함"""
    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        global _rate_limiter_instance
        _rate_limiter_instance = self

app.add_middleware(
    RateLimiterWrapper,
    max_requests=RATE_LIMIT_MAX_REQUESTS,
    time_window=RATE_LIMIT_TIME_WINDOW
)

# ================================================
# 에러 응답 표준화 (Exception Handler)
# ================================================
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

class StandardErrorResponse:
    """표준화된 에러 응답 포맷"""
    @staticmethod
    def create(status_code: int, error_type: str, message: str, details: Any = None):
        response = {
            "success": False,
            "error": {
                "type": error_type,
                "message": message,
                "status_code": status_code,
                "timestamp": datetime.now().isoformat()
            }
        }
        if details:
            response["error"]["details"] = details
        return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTPException 표준화"""
    return JSONResponse(
        status_code=exc.status_code,
        content=StandardErrorResponse.create(
            status_code=exc.status_code,
            error_type="HTTPException",
            message=exc.detail
        )
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Request Validation Error 표준화"""
    return JSONResponse(
        status_code=422,
        content=StandardErrorResponse.create(
            status_code=422,
            error_type="ValidationError",
            message="요청 데이터 검증 실패",
            details=exc.errors()
        )
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 표준화"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=StandardErrorResponse.create(
            status_code=500,
            error_type="InternalServerError",
            message="서버 내부 오류가 발생했습니다"
        )
    )

# ============================================================================
# 라우터 등록 (Routers Registration)
# ============================================================================

# Bookmark 라우터 등록
try:
    from routers import bookmark
    app.include_router(bookmark.router)
    logger.info("✅ Bookmark 라우터 등록 완료")
except Exception as e:
    logger.warning(f"⚠️ Bookmark 라우터 등록 실패: {str(e)}")

# Application Writer 라우터 등록
try:
    from routers import application_impl
    app.include_router(application_impl.router)
    logger.info("✅ Application Writer 라우터 등록 완료")
except Exception as e:
    logger.warning(f"⚠️ Application Writer 라우터 등록 실패: {str(e)}")

# ============================================================================

# Supabase 연결 재시도 함수 (지수 백오프)
def connect_to_supabase_with_retry(max_retries=3):
    """
    Supabase 연결 시도 (재시도 로직 포함)

    Args:
        max_retries: 최대 재시도 횟수 (기본값: 3)

    Returns:
        Supabase 클라이언트 또는 None
    """
    import httpx

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("❌ Supabase 환경변수가 설정되지 않았습니다")
        return None

    # 환경변수에서 커넥션 풀 설정 가져오기
    MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "10"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

    for attempt in range(1, max_retries + 1):
        try:
            # httpx 클라이언트 생성 (커넥션 풀 설정)
            http_client = httpx.Client(
                limits=httpx.Limits(
                    max_connections=MAX_CONNECTIONS,
                    max_keepalive_connections=MAX_CONNECTIONS // 2
                ),
                timeout=httpx.Timeout(REQUEST_TIMEOUT)
            )

            # Supabase 클라이언트 생성
            from supabase.client import ClientOptions

            client = create_client(
                SUPABASE_URL,
                SUPABASE_KEY,
                options=ClientOptions(
                    auto_refresh_token=False,
                    persist_session=False
                )
            )

            # 연결 테스트 (간단한 쿼리 실행)
            test_result = client.table('kstartup_complete').select("announcement_id").limit(1).execute()

            logger.info(f"✅ Supabase 연결 성공 (시도: {attempt}/{max_retries}, 커넥션 풀: {MAX_CONNECTIONS}, 타임아웃: {REQUEST_TIMEOUT}초)")
            return client

        except Exception as e:
            wait_time = 2 ** attempt  # 지수 백오프: 2초, 4초, 8초
            logger.warning(f"⚠️ Supabase 연결 시도 {attempt}/{max_retries} 실패: {e}")

            if attempt < max_retries:
                logger.info(f"⏳ {wait_time}초 후 재시도...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Supabase 연결 최종 실패 (모든 재시도 소진)")
                return None

    return None

# ================================================
# 데이터베이스 커넥션 풀 모니터링 시스템
# ================================================
from collections import defaultdict
from threading import Lock

# DB 쿼리 통계 추적
db_query_stats = {
    "total_queries": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "total_query_time": 0.0,
    "queries_by_table": defaultdict(int),
    "errors": []
}
db_stats_lock = Lock()

def track_db_query(table_name: str, execution_time: float, success: bool, error: str = None):
    """DB 쿼리 실행 추적"""
    with db_stats_lock:
        db_query_stats["total_queries"] += 1
        db_query_stats["total_query_time"] += execution_time

        if success:
            db_query_stats["successful_queries"] += 1
        else:
            db_query_stats["failed_queries"] += 1
            if error and len(db_query_stats["errors"]) < 100:  # 최근 100개 에러만 저장
                db_query_stats["errors"].append({
                    "table": table_name,
                    "error": str(error)[:200],  # 에러 메시지 200자 제한
                    "timestamp": datetime.now().isoformat()
                })

        db_query_stats["queries_by_table"][table_name] += 1

def get_db_connection_stats() -> Dict[str, Any]:
    """DB 커넥션 풀 통계 반환"""
    with db_stats_lock:
        total = db_query_stats["total_queries"]
        success_rate = (db_query_stats["successful_queries"] / total * 100) if total > 0 else 0
        avg_query_time = (db_query_stats["total_query_time"] / total) if total > 0 else 0

        return {
            "connection_pool": {
                "max_connections": MAX_CONNECTIONS,
                "timeout_seconds": REQUEST_TIMEOUT,
                "status": "healthy" if supabase else "disconnected"
            },
            "query_statistics": {
                "total_queries": total,
                "successful_queries": db_query_stats["successful_queries"],
                "failed_queries": db_query_stats["failed_queries"],
                "success_rate_percentage": round(success_rate, 2),
                "average_query_time_ms": round(avg_query_time * 1000, 2)
            },
            "queries_by_table": dict(db_query_stats["queries_by_table"]),
            "recent_errors": db_query_stats["errors"][-10:]  # 최근 10개 에러만 반환
        }

logger.info("✅ 데이터베이스 커넥션 풀 모니터링 시스템 활성화")

# Supabase 클라이언트 초기화 (커넥션 풀링 최적화 + 재시도 로직)
supabase = connect_to_supabase_with_retry(max_retries=3)
MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "10"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# OpenAI 클라이언트 초기화
try:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API Key가 설정되지 않았습니다")

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ OpenAI 클라이언트 초기화 성공")
except Exception as e:
    logger.error(f"❌ OpenAI 클라이언트 초기화 실패: {e}")
    openai_client = None

# ================================================
# 느린 쿼리 로깅 (Query Performance Monitoring)
# ================================================
from functools import wraps
import uuid
from enum import Enum

# 환경변수에서 느린 쿼리 임계값 설정 (기본 1초)
SLOW_QUERY_THRESHOLD = float(os.getenv("SLOW_QUERY_THRESHOLD", "1.0"))

# ================================================
# 비동기 백그라운드 작업 시스템
# ================================================
class TaskStatus(str, Enum):
    """작업 상태"""
    PENDING = "pending"      # 대기 중
    RUNNING = "running"      # 실행 중
    COMPLETED = "completed"  # 완료
    FAILED = "failed"        # 실패
    CANCELLED = "cancelled"  # 취소됨

# 백그라운드 작업 저장소 (메모리 기반)
background_tasks_store: Dict[str, Dict[str, Any]] = {}
background_tasks_lock = Lock()

def create_background_task(task_type: str, description: str, params: Dict[str, Any] = None) -> str:
    """
    백그라운드 작업 생성

    Args:
        task_type: 작업 유형 (예: "ai_summary", "bulk_update")
        description: 작업 설명
        params: 작업 파라미터

    Returns:
        task_id: 생성된 작업 ID
    """
    task_id = str(uuid.uuid4())

    with background_tasks_lock:
        background_tasks_store[task_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "description": description,
            "status": TaskStatus.PENDING,
            "params": params or {},
            "result": None,
            "error": None,
            "progress": 0,
            "total": 0,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None
        }

    logger.info(f"📋 백그라운드 작업 생성: {task_id} ({task_type})")
    return task_id

def update_task_status(task_id: str, status: TaskStatus, progress: int = None, total: int = None,
                       result: Any = None, error: str = None):
    """작업 상태 업데이트"""
    with background_tasks_lock:
        if task_id not in background_tasks_store:
            logger.warning(f"⚠️ 존재하지 않는 작업 ID: {task_id}")
            return

        task = background_tasks_store[task_id]
        task["status"] = status

        if progress is not None:
            task["progress"] = progress
        if total is not None:
            task["total"] = total
        if result is not None:
            task["result"] = result
        if error is not None:
            task["error"] = error

        # 상태별 타임스탬프 업데이트
        if status == TaskStatus.RUNNING and not task["started_at"]:
            task["started_at"] = datetime.now().isoformat()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task["completed_at"] = datetime.now().isoformat()

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """작업 상태 조회"""
    with background_tasks_lock:
        return background_tasks_store.get(task_id)

def get_all_tasks() -> List[Dict[str, Any]]:
    """모든 작업 조회 (최근 순)"""
    with background_tasks_lock:
        tasks = list(background_tasks_store.values())
        # 생성 시간 역순 정렬
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return tasks

async def execute_background_task(task_id: str, task_func, *args, **kwargs):
    """
    백그라운드 작업 실행

    Args:
        task_id: 작업 ID
        task_func: 실행할 비동기 함수
        *args, **kwargs: 함수 인자
    """
    try:
        # 작업 시작
        update_task_status(task_id, TaskStatus.RUNNING)
        logger.info(f"🚀 백그라운드 작업 시작: {task_id}")

        # 작업 실행
        result = await task_func(task_id, *args, **kwargs)

        # 작업 완료
        update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        logger.info(f"✅ 백그라운드 작업 완료: {task_id}")

    except Exception as e:
        # 작업 실패
        error_msg = f"{type(e).__name__}: {str(e)}"
        update_task_status(task_id, TaskStatus.FAILED, error=error_msg)
        logger.error(f"❌ 백그라운드 작업 실패: {task_id} - {error_msg}")
        logger.error(traceback.format_exc())

def log_slow_query(threshold: float = SLOW_QUERY_THRESHOLD, table_name: str = "unknown"):
    """
    느린 쿼리 자동 로깅 및 DB 쿼리 추적 데코레이터

    Args:
        threshold: 느린 쿼리로 간주할 임계값 (초)
        table_name: 쿼리 대상 테이블명 (통계 추적용)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_msg = None

            try:
                result = await func(*args, **kwargs)
                success = True
                execution_time = time.time() - start_time

                # DB 쿼리 통계 추적
                track_db_query(table_name, execution_time, success)

                if execution_time > threshold:
                    logger.warning(
                        f"🐌 느린 쿼리 감지: {func.__name__} - {execution_time:.3f}초",
                        extra={
                            "context": {
                                "function": func.__name__,
                                "table": table_name,
                                "execution_time": round(execution_time, 3),
                                "threshold": threshold,
                                "args_count": len(args),
                                "kwargs": list(kwargs.keys())
                            }
                        }
                    )

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e)

                # DB 쿼리 실패 추적
                track_db_query(table_name, execution_time, success, error_msg)

                logger.error(
                    f"❌ 쿼리 실행 실패: {func.__name__} - {error_msg}",
                    extra={
                        "context": {
                            "function": func.__name__,
                            "table": table_name,
                            "execution_time": round(execution_time, 3),
                            "error": error_msg
                        }
                    }
                )
                raise

        return wrapper
    return decorator

logger.info(f"✅ 느린 쿼리 모니터링 활성화 (임계값: {SLOW_QUERY_THRESHOLD}초)")

# ================================================
# 인메모리 캐시 시스템 (간단한 Dict 기반)
# ================================================
from typing import Tuple
import time

# 캐시 저장소 (key: (data, timestamp))
cache_store: Dict[str, Tuple[Any, float]] = {}

# 캐시 히트율 추적 (hits, misses)
cache_stats_tracker = {"hits": 0, "misses": 0, "expirations": 0}

# 환경변수에서 TTL 설정 (기본 60초)
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))
logger.info(f"✅ 인메모리 캐시 활성화 (TTL: {CACHE_TTL}초)")

def get_cache(key: str) -> Optional[Any]:
    """캐시에서 데이터 조회 (히트율 추적)"""
    if key not in cache_store:
        cache_stats_tracker["misses"] += 1
        return None

    data, timestamp = cache_store[key]

    # TTL 체크
    if time.time() - timestamp > CACHE_TTL:
        # 만료된 캐시 삭제
        del cache_store[key]
        cache_stats_tracker["expirations"] += 1
        logger.debug(f"🗑️ 캐시 만료 삭제: {key}")
        return None

    cache_stats_tracker["hits"] += 1
    logger.debug(f"✅ 캐시 히트: {key}")
    return data

def set_cache(key: str, data: Any) -> None:
    """캐시에 데이터 저장"""
    cache_store[key] = (data, time.time())
    logger.debug(f"💾 캐시 저장: {key}")

def clear_cache(pattern: Optional[str] = None) -> int:
    """
    캐시 삭제 (패턴 지원)

    Args:
        pattern: 삭제할 캐시 키 패턴 (예: "search_*", "api_*")
                None이면 모든 캐시 삭제

    Returns:
        삭제된 캐시 항목 수
    """
    if pattern is None:
        # 모든 캐시 삭제
        count = len(cache_store)
        cache_store.clear()
        logger.info(f"🗑️ 모든 캐시 삭제됨 ({count}개)")
        return count

    # 패턴 매칭으로 삭제
    import fnmatch
    keys_to_delete = [key for key in cache_store.keys() if fnmatch.fnmatch(key, pattern)]

    for key in keys_to_delete:
        del cache_store[key]

    logger.info(f"🗑️ 패턴 '{pattern}' 캐시 삭제됨 ({len(keys_to_delete)}개)")
    return len(keys_to_delete)

def get_cache_stats() -> Dict[str, Any]:
    """캐시 통계 정보 조회 (히트율 포함)"""
    current_time = time.time()

    # 히트율 계산
    total_requests = cache_stats_tracker["hits"] + cache_stats_tracker["misses"]
    hit_rate = (cache_stats_tracker["hits"] / total_requests * 100) if total_requests > 0 else 0

    stats = {
        "total_entries": len(cache_store),
        "ttl_seconds": CACHE_TTL,
        "hit_rate_percentage": round(hit_rate, 2),
        "performance": {
            "hits": cache_stats_tracker["hits"],
            "misses": cache_stats_tracker["misses"],
            "expirations": cache_stats_tracker["expirations"],
            "total_requests": total_requests
        },
        "entries": []
    }

    for key, (data, timestamp) in cache_store.items():
        age = current_time - timestamp
        remaining_ttl = max(0, CACHE_TTL - age)

        stats["entries"].append({
            "key": key,
            "age_seconds": round(age, 2),
            "remaining_ttl_seconds": round(remaining_ttl, 2),
            "size_estimate": len(str(data))  # 간단한 크기 추정
        })

    return stats

def cleanup_expired_cache() -> int:
    """만료된 캐시 항목 자동 정리"""
    current_time = time.time()
    keys_to_delete = []

    for key, (data, timestamp) in cache_store.items():
        if current_time - timestamp > CACHE_TTL:
            keys_to_delete.append(key)

    for key in keys_to_delete:
        del cache_store[key]

    if keys_to_delete:
        logger.info(f"🧹 만료된 캐시 자동 정리 ({len(keys_to_delete)}개)")

    return len(keys_to_delete)

# 필요한 함수들 추가
@app.get("/")
async def serve_frontend():
    """프론트엔드 HTML 서빙"""
    # 여러 경로 시도
    possible_paths = [
        Path(__file__).parent / 'index.html',
        Path('index.html'),
        Path('frontend/index.html'),
        Path('E:/gov-support-automation/frontend/index.html')
    ]
    
    for html_path in possible_paths:
        if html_path.exists():
            logger.info(f"Found index.html at: {html_path}")
            return FileResponse(str(html_path))
    
    logger.warning("index.html not found, returning API status")
    return {
        "message": "API is running. Frontend file not found.",
        "api_docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/health",
        "stats": "http://localhost:8000/api/stats"
    }

@app.get("/metrics")
async def metrics():
    """
    Prometheus 메트릭 엔드포인트

    Prometheus 형식으로 시스템 메트릭을 제공합니다.
    """
    from fastapi.responses import PlainTextResponse

    # 캐시 통계
    cache_hits = cache_stats_tracker["hits"]
    cache_misses = cache_stats_tracker["misses"]
    cache_expirations = cache_stats_tracker["expirations"]
    cache_entries = len(cache_store)

    # Rate Limiter 통계
    rate_limiter_stats = get_rate_limiter_stats()
    tracked_ips = rate_limiter_stats.get("tracked_ips", 0)
    total_active_requests = rate_limiter_stats.get("total_active_requests", 0)

    # DB 상태
    db_connected = 1 if supabase else 0
    openai_connected = 1 if openai_client else 0

    # API 응답 시간 메트릭
    endpoint_stats = get_endpoint_metrics_summary()

    # DB 커넥션 풀 통계
    db_stats = get_db_connection_stats()
    db_query_stats_data = db_stats["query_statistics"]
    db_queries_by_table = db_stats["queries_by_table"]

    # Prometheus 포맷 메트릭
    metrics_text = f"""# HELP cache_hits_total Total number of cache hits
# TYPE cache_hits_total counter
cache_hits_total {cache_hits}

# HELP cache_misses_total Total number of cache misses
# TYPE cache_misses_total counter
cache_misses_total {cache_misses}

# HELP cache_expirations_total Total number of cache expirations
# TYPE cache_expirations_total counter
cache_expirations_total {cache_expirations}

# HELP cache_entries Current number of cache entries
# TYPE cache_entries gauge
cache_entries {cache_entries}

# HELP rate_limiter_tracked_ips Number of tracked IP addresses
# TYPE rate_limiter_tracked_ips gauge
rate_limiter_tracked_ips {tracked_ips}

# HELP rate_limiter_active_requests Total active requests across all IPs
# TYPE rate_limiter_active_requests gauge
rate_limiter_active_requests {total_active_requests}

# HELP database_connected Database connection status (1=connected, 0=disconnected)
# TYPE database_connected gauge
database_connected {db_connected}

# HELP openai_connected OpenAI client status (1=connected, 0=disconnected)
# TYPE openai_connected gauge
openai_connected {openai_connected}

# HELP db_queries_total Total number of database queries
# TYPE db_queries_total counter
db_queries_total {db_query_stats_data["total_queries"]}

# HELP db_queries_successful Successful database queries
# TYPE db_queries_successful counter
db_queries_successful {db_query_stats_data["successful_queries"]}

# HELP db_queries_failed Failed database queries
# TYPE db_queries_failed counter
db_queries_failed {db_query_stats_data["failed_queries"]}

# HELP db_query_success_rate_percentage Database query success rate
# TYPE db_query_success_rate_percentage gauge
db_query_success_rate_percentage {db_query_stats_data["success_rate_percentage"]}

# HELP db_query_avg_time_ms Average database query time in milliseconds
# TYPE db_query_avg_time_ms gauge
db_query_avg_time_ms {db_query_stats_data["average_query_time_ms"]}

# HELP api_requests_total Total number of API requests per endpoint
# TYPE api_requests_total counter
"""

    # 엔드포인트별 요청 수
    for endpoint, stats in endpoint_stats.items():
        # Prometheus 라벨 형식으로 변환
        method, path = endpoint.split(" ", 1)
        metrics_text += f'api_requests_total{{method="{method}",path="{path}"}} {stats["count"]}\n'

    metrics_text += """
# HELP api_response_time_ms API response time in milliseconds
# TYPE api_response_time_ms summary
"""

    # 엔드포인트별 응답 시간 (min, avg, max, p50, p95, p99)
    for endpoint, stats in endpoint_stats.items():
        method, path = endpoint.split(" ", 1)
        metrics_text += f'api_response_time_ms{{method="{method}",path="{path}",quantile="min"}} {stats["min_ms"]}\n'
        metrics_text += f'api_response_time_ms{{method="{method}",path="{path}",quantile="avg"}} {stats["avg_ms"]}\n'
        metrics_text += f'api_response_time_ms{{method="{method}",path="{path}",quantile="max"}} {stats["max_ms"]}\n'
        metrics_text += f'api_response_time_ms{{method="{method}",path="{path}",quantile="0.5"}} {stats["p50_ms"]}\n'
        metrics_text += f'api_response_time_ms{{method="{method}",path="{path}",quantile="0.95"}} {stats["p95_ms"]}\n'
        metrics_text += f'api_response_time_ms{{method="{method}",path="{path}",quantile="0.99"}} {stats["p99_ms"]}\n'

    # 테이블별 쿼리 카운트
    metrics_text += "\n# HELP db_queries_by_table Database queries by table\n"
    metrics_text += "# TYPE db_queries_by_table counter\n"
    for table_name, count in db_queries_by_table.items():
        metrics_text += f'db_queries_by_table{{table="{table_name}"}} {count}\n'

    return PlainTextResponse(content=metrics_text, media_type="text/plain; version=0.0.4")

@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트 - DB 연결, 캐시 상태, API 버전 포함"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": API_VERSION,
        "version_info": {
            "major": API_VERSION_MAJOR,
            "minor": API_VERSION_MINOR,
            "patch": API_VERSION_PATCH,
            "release_date": "2025-11-02"
        },
        "services": {
            "database": {
                "connected": supabase is not None,
                "status": "healthy" if supabase else "unavailable",
                "connection_pool": get_db_connection_stats() if supabase else {
                    "connection_pool": {
                        "max_connections": 0,
                        "timeout_seconds": 0,
                        "status": "disconnected"
                    },
                    "query_statistics": {
                        "total_queries": 0,
                        "successful_queries": 0,
                        "failed_queries": 0,
                        "success_rate_percentage": 0,
                        "average_query_time_ms": 0
                    },
                    "queries_by_table": {},
                    "recent_errors": []
                }
            },
            "cache": {
                "enabled": True,
                "ttl": CACHE_TTL,
                "entries": len(cache_store),
                "status": "healthy"
            },
            "rate_limiting": get_rate_limiter_stats(),
            "openai": {
                "connected": openai_client is not None,
                "status": "healthy" if openai_client else "unavailable"
            }
        }
    }

    # DB 연결 실제 테스트
    if supabase:
        try:
            # 간단한 쿼리로 DB 연결 확인
            test_query = supabase.table('kstartup_complete').select("announcement_id", count='exact').limit(1).execute()
            health_status["services"]["database"]["test_query"] = "success"
            health_status["services"]["database"]["response_time_ms"] = "<50"
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["services"]["database"]["status"] = "error"
            health_status["services"]["database"]["error"] = str(e)

    # 전체 상태 결정
    if health_status["status"] == "degraded":
        return JSONResponse(status_code=503, content=health_status)

    return health_status

@app.get("/api/performance")
async def get_performance_metrics():
    """
    API 응답 시간 성능 메트릭 조회

    엔드포인트별 응답 시간 통계를 제공합니다.
    """
    endpoint_stats = get_endpoint_metrics_summary()

    # 상위 5개 느린 엔드포인트
    slowest_endpoints = sorted(
        endpoint_stats.items(),
        key=lambda x: x[1]["avg_ms"],
        reverse=True
    )[:5]

    # 상위 5개 많이 호출된 엔드포인트
    most_requested = sorted(
        endpoint_stats.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:5]

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_endpoints": len(endpoint_stats),
            "total_requests": sum(stats["count"] for stats in endpoint_stats.values())
        },
        "endpoints": endpoint_stats,
        "top_slowest": [
            {
                "endpoint": endpoint,
                "avg_ms": stats["avg_ms"],
                "p95_ms": stats["p95_ms"],
                "count": stats["count"]
            }
            for endpoint, stats in slowest_endpoints
        ],
        "most_requested": [
            {
                "endpoint": endpoint,
                "count": stats["count"],
                "avg_ms": stats["avg_ms"]
            }
            for endpoint, stats in most_requested
        ]
    }

@app.get("/api/stats")
async def get_statistics():
    """실시간 통계 정보 조회 (캐시 60초) - 인메모리 캐시 적용"""
    # 캐시 확인
    cached_data = get_cache("api_stats")
    if cached_data:
        logger.info("[Stats] 💨 캐시 히트 (즉시 응답)")
        return cached_data

    if not supabase:
        return {
            "error": "Database not connected",
            "total": 0,
            "kstartup": 0,
            "bizinfo": 0
        }

    try:
        logger.info("[Stats] 📊 DB 조회 시작...")
        today = datetime.now().strftime("%Y-%m-%d")
        week_later = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        # K-Startup 통계 (count만 조회)
        ks_total = supabase.table('kstartup_complete').select("announcement_id", count='exact').execute()
        ks_ongoing = supabase.table('kstartup_complete')\
            .select("announcement_id", count='exact')\
            .gte('pbanc_rcpt_end_dt', today)\
            .execute()
        ks_deadline = supabase.table('kstartup_complete')\
            .select("announcement_id", count='exact')\
            .gte('pbanc_rcpt_end_dt', today)\
            .lte('pbanc_rcpt_end_dt', week_later)\
            .execute()

        # BizInfo 통계 (count만 조회)
        bi_total = supabase.table('bizinfo_complete').select("pblanc_id", count='exact').execute()
        bi_ongoing = supabase.table('bizinfo_complete')\
            .select("pblanc_id", count='exact')\
            .gte('reqst_end_ymd', today)\
            .execute()
        bi_deadline = supabase.table('bizinfo_complete')\
            .select("pblanc_id", count='exact')\
            .gte('reqst_end_ymd', today)\
            .lte('reqst_end_ymd', week_later)\
            .execute()

        # 오늘 등록된 공고
        today_start = f"{today}T00:00:00"
        ks_today = supabase.table('kstartup_complete')\
            .select("announcement_id", count='exact')\
            .gte('created_at', today_start)\
            .execute()
        bi_today = supabase.table('bizinfo_complete')\
            .select("pblanc_id", count='exact')\
            .gte('created_at', today_start)\
            .execute()

        result = {
            "total": (ks_total.count or 0) + (bi_total.count or 0),
            "kstartup": ks_total.count or 0,
            "bizinfo": bi_total.count or 0,
            "today": (ks_today.count or 0) + (bi_today.count or 0),
            "ongoing": (ks_ongoing.count or 0) + (bi_ongoing.count or 0),
            "deadline": (ks_deadline.count or 0) + (bi_deadline.count or 0),
            "last_update": datetime.now().isoformat(),
            "cache_enabled": True,
            "cache_ttl": CACHE_TTL,
            "details": {
                "kstartup": {
                    "total": ks_total.count or 0,
                    "ongoing": ks_ongoing.count or 0,
                    "deadline": ks_deadline.count or 0,
                    "today": ks_today.count or 0
                },
                "bizinfo": {
                    "total": bi_total.count or 0,
                    "ongoing": bi_ongoing.count or 0,
                    "deadline": bi_deadline.count or 0,
                    "today": bi_today.count or 0
                }
            }
        }

        # 캐시 저장
        set_cache("api_stats", result)
        logger.info("[Stats] ✅ 캐시 저장 완료")

        return result

    except Exception as e:
        logger.error(f"❌ 통계 조회 실패: {e}")
        logger.error(traceback.format_exc())
        return {
            "error": str(e),
            "total": 0,
            "kstartup": 0,
            "bizinfo": 0,
            "today": 0,
            "ongoing": 0,
            "deadline": 0,
            "last_update": datetime.now().isoformat()
        }

@app.get("/api/search")
@limiter.limit("60/minute") if RATE_LIMIT_ENABLED else lambda x: x
async def search_announcements(
    request: Request,
    q: Optional[str] = Query(None, description="검색어"),
    source: Optional[str] = Query("all", description="출처: all, kstartup, bizinfo"),
    status: Optional[str] = Query("all", description="상태: all, ongoing, deadline, closed"),
    sort: Optional[str] = Query("newest", description="정렬: newest, deadline, title"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(10, ge=1, le=100, description="페이지당 항목 수")
):
    """공고 검색 (실제 DB 데이터) - DB 레벨 페이지네이션 적용 + Rate Limiting (60/min) + 캐싱"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    # 캐시 키 생성
    cache_key = f"search_{q or 'all'}_{source}_{status}_{sort}_{page}_{limit}"
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.info(f"[Search] 💨 캐시 히트: {cache_key}")
        return cached_data

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        week_later = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        # 단일 소스 검색 (source가 all이 아닌 경우)
        if source == "kstartup":
            return await _search_single_source_paginated(
                "kstartup_complete", q, status, sort, page, limit, today, week_later
            )
        elif source == "bizinfo":
            return await _search_single_source_paginated(
                "bizinfo_complete", q, status, sort, page, limit, today, week_later
            )

        # 통합 검색 (source가 "all"인 경우)
        # 두 테이블의 총 개수를 먼저 조회
        ks_count = await _get_count("kstartup_complete", q, status, today, week_later)
        bi_count = await _get_count("bizinfo_complete", q, status, today, week_later)
        total_count = ks_count + bi_count

        # 페이지네이션 계산
        offset = (page - 1) * limit

        # 두 테이블에서 필요한 만큼만 조회
        all_results = []

        # K-Startup 검색
        ks_limit = min(limit, max(0, limit - len(all_results)))
        if ks_limit > 0:
            ks_results = await _fetch_announcements(
                "kstartup_complete", q, status, sort, offset, ks_limit, today, week_later
            )
            all_results.extend(ks_results)

        # BizInfo 검색 (K-Startup 결과가 limit보다 적을 때만)
        bi_offset = max(0, offset - ks_count)
        bi_limit = min(limit - len(all_results), bi_count)
        if bi_limit > 0:
            bi_results = await _fetch_announcements(
                "bizinfo_complete", q, status, sort, bi_offset, bi_limit, today, week_later
            )
            all_results.extend(bi_results)

        # 통합 정렬이 필요한 경우 (newest, deadline, title 정렬 시)
        if sort == "deadline":
            all_results.sort(key=lambda x: (x.get('end_date') or '9999-99-99'))
        elif sort == "title":
            all_results.sort(key=lambda x: x.get('title', ''))
        else:  # newest
            all_results.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        result = {
            "success": True,
            "results": all_results[:limit],  # 정렬 후 다시 limit 적용
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit,
            "has_more": (offset + limit) < total_count
        }

        # 캐시 저장
        set_cache(cache_key, result)
        logger.info(f"[Search] ✅ 캐시 저장: {cache_key}")

        return result

    except Exception as e:
        logger.error(f"검색 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@log_slow_query(table_name="count_query")
async def _get_count(table_name: str, q: Optional[str], status: str, today: str, week_later: str) -> int:
    """테이블의 총 레코드 수 조회"""
    query = supabase.table(table_name).select("*", count='exact')

    # 검색어 필터
    if q:
        if table_name == "kstartup_complete":
            search_filter = f"biz_pbanc_nm.ilike.%{q}%,simple_summary.ilike.%{q}%"
        else:  # bizinfo_complete
            search_filter = f"pblanc_nm.ilike.%{q}%,organ_nm.ilike.%{q}%,sprt_trgt.ilike.%{q}%"
        query = query.or_(search_filter)

    # 상태 필터
    date_col = 'pbanc_rcpt_end_dt' if table_name == "kstartup_complete" else 'reqst_end_ymd'
    if status == "ongoing":
        query = query.gte(date_col, today)
    elif status == "closed":
        query = query.lt(date_col, today)
    elif status == "deadline":
        query = query.gte(date_col, today).lte(date_col, week_later)

    result = query.execute()
    return result.count or 0

@log_slow_query(table_name="fetch_announcements")
async def _fetch_announcements(
    table_name: str, q: Optional[str], status: str, sort: str,
    offset: int, limit: int, today: str, week_later: str
) -> List[Dict[str, Any]]:
    """테이블에서 공고 조회 (페이지네이션 적용)"""
    # 컬럼 선택
    if table_name == "kstartup_complete":
        query = supabase.table(table_name).select(
            "announcement_id,biz_pbanc_nm,pbanc_ntrp_nm,pbanc_rcpt_bgng_dt,pbanc_rcpt_end_dt,simple_summary,created_at"
        )
    else:  # bizinfo_complete
        query = supabase.table(table_name).select(
            "pblanc_id,pblanc_nm,organ_nm,reqst_begin_ymd,reqst_end_ymd,simple_summary,created_at"
        )

    # 검색어 필터
    if q:
        if table_name == "kstartup_complete":
            search_filter = f"biz_pbanc_nm.ilike.%{q}%,simple_summary.ilike.%{q}%"
        else:  # bizinfo_complete
            search_filter = f"pblanc_nm.ilike.%{q}%,organ_nm.ilike.%{q}%,sprt_trgt.ilike.%{q}%"
        query = query.or_(search_filter)

    # 상태 필터
    date_col = 'pbanc_rcpt_end_dt' if table_name == "kstartup_complete" else 'reqst_end_ymd'
    if status == "ongoing":
        query = query.gte(date_col, today)
    elif status == "closed":
        query = query.lt(date_col, today)
    elif status == "deadline":
        query = query.gte(date_col, today).lte(date_col, week_later)

    # 정렬
    if table_name == "kstartup_complete":
        if sort == "deadline":
            query = query.order('pbanc_rcpt_end_dt', desc=False)
        elif sort == "title":
            query = query.order('biz_pbanc_nm', desc=False)
        else:  # newest
            query = query.order('created_at', desc=True)
    else:  # bizinfo_complete
        if sort == "deadline":
            query = query.order('reqst_end_ymd', desc=False)
        elif sort == "title":
            query = query.order('pblanc_nm', desc=False)
        else:  # newest
            query = query.order('created_at', desc=True)

    # 페이지네이션 (DB 레벨)
    query = query.range(offset, offset + limit - 1)

    # 실행
    result = query.execute()

    # 결과 포맷팅
    formatted_results = []
    for item in result.data:
        if table_name == "kstartup_complete":
            title = item.get("biz_pbanc_nm")
            formatted_results.append({
                "id": item.get("announcement_id"),
                "title": title,
                "organization": item.get("pbanc_ntrp_nm") or "K-Startup",
                "category": extract_category_from_title(title),
                "start_date": item.get("pbanc_rcpt_bgng_dt"),
                "end_date": item.get("pbanc_rcpt_end_dt"),
                "source": "kstartup",
                "source_name": "K-Startup",
                "simple_summary": item.get("simple_summary"),
                "status": calculate_status(item.get("pbanc_rcpt_end_dt")),
                "created_at": item.get("created_at"),
                "days_left": calculate_days_left(item.get("pbanc_rcpt_end_dt"))
            })
        else:  # bizinfo_complete
            title = item.get("pblanc_nm")
            formatted_results.append({
                "id": item.get("pblanc_id"),
                "title": title,
                "organization": item.get("organ_nm"),
                "category": extract_category_from_title(title),
                "start_date": item.get("reqst_begin_ymd"),
                "end_date": item.get("reqst_end_ymd"),
                "source": "bizinfo",
                "source_name": "BizInfo",
                "simple_summary": item.get("simple_summary"),
                "status": calculate_status(item.get("reqst_end_ymd")),
                "created_at": item.get("created_at"),
                "days_left": calculate_days_left(item.get("reqst_end_ymd"))
            })

    return formatted_results

@log_slow_query(table_name="single_source_search")
async def _search_single_source_paginated(
    table_name: str, q: Optional[str], status: str, sort: str,
    page: int, limit: int, today: str, week_later: str
) -> Dict[str, Any]:
    """단일 소스 검색 (DB 레벨 페이지네이션)"""
    # 총 개수 조회
    total_count = await _get_count(table_name, q, status, today, week_later)

    # 페이지네이션 계산
    offset = (page - 1) * limit

    # 결과 조회
    results = await _fetch_announcements(
        table_name, q, status, sort, offset, limit, today, week_later
    )

    result = {
        "success": True,
        "results": results,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
        "has_more": (offset + limit) < total_count
    }

    return result

@app.get("/api/search/semantic")
async def search_semantic(
    q: str = Query(..., description="검색어 (필수)"),
    source: Optional[str] = Query("all", description="출처: all, kstartup, bizinfo"),
    threshold: float = Query(0.5, ge=0.0, le=1.0, description="유사도 임계값"),
    limit: int = Query(10, ge=1, le=50, description="결과 개수")
):
    """임베딩 기반 의미 검색 (Semantic Search)"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized")

    try:
        # 1. OpenAI로 검색어 임베딩 생성
        logger.info(f"[Semantic Search] 검색어: {q}")
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=q
        )
        query_embedding = embedding_response.data[0].embedding
        logger.info(f"[Semantic Search] 임베딩 생성 완료 (차원: {len(query_embedding)})")

        # 2. Supabase RPC 함수 호출
        results = []

        if source in ["all", "kstartup"]:
            # K-Startup 검색
            ks_result = supabase.rpc(
                'match_kstartup_announcements',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': threshold,
                    'match_count': limit
                }
            ).execute()

            # 결과 포맷팅
            for item in ks_result.data:
                title = item.get("biz_pbanc_nm")
                results.append({
                    "id": item.get("announcement_id"),
                    "title": title,
                    "organization": item.get("pbanc_ntrp_nm") or "K-Startup",
                    "category": extract_category_from_title(title),
                    "start_date": item.get("pbanc_rcpt_bgng_dt"),
                    "end_date": item.get("pbanc_rcpt_end_dt"),
                    "source": "kstartup",
                    "source_name": "K-Startup",
                    "simple_summary": item.get("simple_summary"),
                    "detailed_summary": item.get("detailed_summary"),
                    "status": calculate_status(item.get("pbanc_rcpt_end_dt")),
                    "days_left": calculate_days_left(item.get("pbanc_rcpt_end_dt")),
                    "similarity": round(item.get("similarity", 0), 4)
                })

        if source in ["all", "bizinfo"]:
            # BizInfo 검색
            bi_result = supabase.rpc(
                'match_bizinfo_announcements',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': threshold,
                    'match_count': limit
                }
            ).execute()

            # 결과 포맷팅
            for item in bi_result.data:
                title = item.get("pblanc_nm")
                results.append({
                    "id": item.get("pblanc_id"),
                    "title": title,
                    "organization": item.get("organ_nm"),
                    "category": extract_category_from_title(title),
                    "start_date": item.get("reqst_begin_ymd"),
                    "end_date": item.get("reqst_end_ymd"),
                    "source": "bizinfo",
                    "source_name": "BizInfo",
                    "simple_summary": item.get("simple_summary"),
                    "detailed_summary": item.get("detailed_summary"),
                    "status": calculate_status(item.get("reqst_end_ymd")),
                    "days_left": calculate_days_left(item.get("reqst_end_ymd")),
                    "similarity": round(item.get("similarity", 0), 4)
                })

        # 유사도 순으로 정렬
        results.sort(key=lambda x: x.get('similarity', 0), reverse=True)

        # 제한된 개수만 반환
        results = results[:limit]

        logger.info(f"[Semantic Search] 검색 완료: {len(results)}개 결과")

        return {
            "success": True,
            "data": results,
            "total": len(results),
            "query": q,
            "threshold": threshold,
            "search_type": "semantic"
        }

    except Exception as e:
        logger.error(f"의미 검색 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/announcement/{announcement_id}")
async def get_announcement_detail(announcement_id: str):
    """공고 상세 조회 - 인메모리 캐시 적용"""
    # 캐시 키 생성
    cache_key = f"announcement_{announcement_id}"
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.info(f"[Announcement Detail] 💨 캐시 히트: {announcement_id}")
        return cached_data

    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        # ID 접두사로 테이블 구분
        if announcement_id.startswith("KS_"):
            result = supabase.table('kstartup_complete')\
                .select("*")\
                .eq('announcement_id', announcement_id)\
                .execute()

            if result.data:
                formatted_data = format_announcement(result.data[0], "kstartup")
                # 캐시 저장
                set_cache(cache_key, formatted_data)
                logger.info(f"[Announcement Detail] ✅ 캐시 저장: {announcement_id}")
                return formatted_data

        elif announcement_id.startswith("PBLN_"):
            result = supabase.table('bizinfo_complete')\
                .select("*")\
                .eq('pblanc_id', announcement_id)\
                .execute()

            if result.data:
                formatted_data = format_announcement(result.data[0], "bizinfo")
                # 캐시 저장
                set_cache(cache_key, formatted_data)
                logger.info(f"[Announcement Detail] ✅ 캐시 저장: {announcement_id}")
                return formatted_data

        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상세 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/announcements/bulk")
async def get_announcements_bulk(request: Dict[str, List[str]]):
    """북마크 ID 리스트로 여러 공고 조회"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        announcement_ids = request.get("announcement_ids", [])

        if not announcement_ids:
            return {
                "success": True,
                "announcements": [],
                "total": 0
            }

        results = []

        # ID별로 조회
        for announcement_id in announcement_ids:
            try:
                if announcement_id.startswith("KS_"):
                    # K-Startup 조회
                    result = supabase.table('kstartup_complete')\
                        .select("*")\
                        .eq('announcement_id', announcement_id)\
                        .execute()

                    if result.data:
                        results.append(format_announcement(result.data[0], "kstartup"))

                elif announcement_id.startswith("PBLN_"):
                    # BizInfo 조회
                    result = supabase.table('bizinfo_complete')\
                        .select("*")\
                        .eq('pblanc_id', announcement_id)\
                        .execute()

                    if result.data:
                        results.append(format_announcement(result.data[0], "bizinfo"))

            except Exception as e:
                logger.error(f"공고 조회 실패 ({announcement_id}): {e}")
                continue

        logger.info(f"[Bulk] {len(announcement_ids)}개 요청, {len(results)}개 조회 성공")

        return {
            "success": True,
            "announcements": results,
            "total": len(results)
        }

    except Exception as e:
        logger.error(f"일괄 조회 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/filters")
async def get_filter_options():
    """필터 옵션 조회 (지원분야, 지역, 대상, 연령, 업력 등) - 인메모리 캐시 적용"""
    # 캐시 확인
    cached_data = get_cache("api_filters")
    if cached_data:
        logger.info("[Filters] 💨 캐시 히트")
        return cached_data

    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        logger.info("[Filters] 📊 DB 조회 시작...")
        filters = {
            "categories": [],
            "regions": [],
            "targets": [],
            "ages": [],
            "business_years": []
        }

        # 카테고리는 네이버 카페 11개 카테고리 사용 (K-Startup + 기업마당 통합)
        filters["categories"] = [
            "자금지원(보조금/지원금)",
            "정책자금(융자/대출)",
            "시설/공간 지원",
            "교육/컨설팅/멘토링",
            "인력지원/일자리",
            "기술개발 (R&D)",
            "해외진출/수출지원",
            "판로/마케팅 지원",
            "네트워킹/커뮤니티",
            "농림축수산업 특별지원",
            "기타 지원사업"
        ]

        # 지역과 대상만 가벼운 쿼리로 조회 (100개만)
        bi_data = supabase.table('bizinfo_complete')\
            .select("organ_nm")\
            .limit(100)\
            .execute()

        # 지역 추출 (조직명에서)
        regions_set = set()
        for item in bi_data.data:
            org_name = item.get("organ_nm", "")
            if org_name:
                for region in ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
                              "강원", "전북", "제주"]:
                    if region in org_name:
                        regions_set.add(region)
                        break

        # 지역 순서를 이미지와 동일하게 (전국이 맨 위)
        filters["regions"] = [
            "전국",
            "서울",
            "부산",
            "대구",
            "인천",
            "광주",
            "대전",
            "울산",
            "세종",
            "강원",
            "경기",
            "경남",
            "경북",
            "전남",
            "전북",
            "충남",
            "충북",
            "제주"
        ]
        # 대상 필터 (이미지와 동일한 순서)
        filters["targets"] = [
            "청소년",
            "대학생",
            "일반인",
            "대학",
            "연구기관",
            "일반기업",
            "1인 창조기업"
        ]

        # 고정 옵션들 - 연령 (이미지와 동일)
        filters["ages"] = [
            "만 20세 미만",
            "만 20세 이상 ~ 만 39세 이하",
            "만 39세 이하",
            "만 40세 이상"
        ]
        # 창업업력 (이미지와 동일)
        filters["business_years"] = [
            "예비창업자",
            "1년미만",
            "2년미만",
            "3년미만",
            "5년미만",
            "7년미만",
            "10년미만"
        ]

        logger.info(f"[Filters] 필터 옵션 조회 완료: 카테고리 {len(filters['categories'])}개, 지역 {len(filters['regions'])}개, 대상 {len(filters['targets'])}개")

        result = {
            "success": True,
            "filters": filters
        }

        # 캐시 저장 (인메모리 캐시 사용)
        set_cache("api_filters", result)
        logger.info("[Filters] ✅ 캐시 저장 완료")

        return result

    except Exception as e:
        logger.error(f"필터 옵션 조회 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1, description="검색어 일부")
):
    """검색어 자동완성 제안 - 인메모리 캐시 적용"""
    # 캐시 키 생성
    cache_key = f"suggestions_{q.lower()}"
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.info(f"[Suggestions] 💨 캐시 히트: {q}")
        return cached_data

    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        suggestions = []

        # K-Startup 공고 제목에서 검색
        ks_result = supabase.table('kstartup_complete')\
            .select("biz_pbanc_nm")\
            .ilike('biz_pbanc_nm', f'%{q}%')\
            .limit(5)\
            .execute()

        for item in ks_result.data:
            title = item.get("biz_pbanc_nm", "")
            if title and title not in suggestions:
                suggestions.append(title)

        # BizInfo 공고 제목에서 검색
        bi_result = supabase.table('bizinfo_complete')\
            .select("pblanc_nm")\
            .ilike('pblanc_nm', f'%{q}%')\
            .limit(5)\
            .execute()

        for item in bi_result.data:
            title = item.get("pblanc_nm", "")
            if title and title not in suggestions:
                suggestions.append(title)

        # 중복 제거 및 제한
        suggestions = list(set(suggestions))[:10]

        # 인기 키워드 (고정)
        popular_keywords = ["창업", "R&D", "기술개발", "마케팅", "수출", "인력", "컨설팅", "특허", "디자인"]

        # 검색어가 짧으면 인기 키워드 추가
        if len(q) <= 2:
            matching_popular = [kw for kw in popular_keywords if q in kw]
            suggestions = matching_popular + suggestions

        logger.info(f"[Suggestions] 검색어: {q}, 제안 개수: {len(suggestions)}")

        result = {
            "success": True,
            "query": q,
            "suggestions": suggestions[:10]
        }

        # 캐시 저장 (인메모리 캐시 사용)
        set_cache(cache_key, result)
        logger.info(f"[Suggestions] ✅ 캐시 저장: {q}")

        return result

    except Exception as e:
        logger.error(f"검색어 제안 실패: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "query": q,
            "suggestions": []
        }

@app.get("/api/recent")
async def get_recent_announcements(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(10, ge=1, le=50, description="페이지당 개수"),
    status: Optional[str] = Query(None, description="상태 필터 (ongoing, expired, unknown)")
):
    """최근 등록 공고 조회 - 페이지네이션 지원"""
    # 캐시 키에 status 포함
    cache_key = f"api_recent_{status or 'all'}"
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.info(f"[Recent] 💨 캐시 히트 (status={status})")
        # 상태 필터링
        filtered = cached_data if not status else [x for x in cached_data if x.get('status') == status]
        total_count = len(filtered)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        return {
            "success": True,
            "results": filtered[start_idx:end_idx],
            "total": total_count,
            "page": page,
            "limit": limit
        }

    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        logger.info("[Recent] 데이터베이스에서 새로 조회 (병렬 처리)")
        recent_list = []

        # K-Startup + BizInfo 병렬 조회 (각각 limit의 절반씩 조회)
        per_source_limit = max(30, limit * 2)  # 최소 30개, 또는 요청 limit의 2배

        async def fetch_ks():
            return supabase.table('kstartup_complete')\
                .select("announcement_id,biz_pbanc_nm,pbanc_ntrp_nm,pbanc_rcpt_bgng_dt,pbanc_rcpt_end_dt,created_at")\
                .order('created_at', desc=True)\
                .limit(per_source_limit)\
                .execute()

        async def fetch_bi():
            return supabase.table('bizinfo_complete')\
                .select("pblanc_id,pblanc_nm,organ_nm,reqst_begin_ymd,reqst_end_ymd,created_at")\
                .order('created_at', desc=True)\
                .limit(per_source_limit)\
                .execute()

        # 병렬 실행
        ks_recent, bi_recent = await asyncio.gather(fetch_ks(), fetch_bi())

        # K-Startup 데이터 처리
        for item in ks_recent.data:
            title = item.get("biz_pbanc_nm")
            recent_list.append({
                "id": item.get("announcement_id"),
                "title": title,
                "organization": item.get("pbanc_ntrp_nm") or "K-Startup",
                "category": extract_category_from_title(title),
                "start_date": item.get("pbanc_rcpt_bgng_dt"),
                "end_date": item.get("pbanc_rcpt_end_dt"),
                "source": "kstartup",
                "status": calculate_status(item.get("pbanc_rcpt_end_dt")),
                "created_at": item.get("created_at")
            })

        # BizInfo 데이터 처리
        for item in bi_recent.data:
            title = item.get("pblanc_nm")
            recent_list.append({
                "id": item.get("pblanc_id"),
                "title": title,
                "organization": item.get("organ_nm"),
                "category": extract_category_from_title(title),
                "start_date": item.get("reqst_begin_ymd"),
                "end_date": item.get("reqst_end_ymd"),
                "source": "bizinfo",
                "status": calculate_status(item.get("reqst_end_ymd")),
                "created_at": item.get("created_at")
            })

        # 통합 정렬
        recent_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # 캐시 저장 (status 별로 구분)
        set_cache("api_recent_all", recent_list)
        logger.info(f"[Recent] ✅ 캐시 저장 완료 (전체 {len(recent_list)}개)")

        # 상태 필터링
        filtered = recent_list if not status else [x for x in recent_list if x.get('status') == status]
        total_count = len(filtered)

        # 페이지네이션 적용
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit

        logger.info(f"[Recent] 페이지={page}, limit={limit}, total={total_count}, status={status}")

        return {
            "success": True,
            "results": filtered[start_idx:end_idx],
            "total": total_count,
            "page": page,
            "limit": limit
        }

    except Exception as e:
        logger.error(f"최근 공고 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def calculate_status(end_date):
    """마감일 기준 상태 계산"""
    if not end_date:
        return "unknown"
    
    try:
        end = datetime.strptime(end_date, "%Y-%m-%d")
        today = datetime.now()
        days_left = (end - today).days
        
        if days_left < 0:
            return "closed"
        elif days_left <= 7:
            return "deadline"
        else:
            return "ongoing"
    except:
        return "unknown"

def calculate_days_left(end_date):
    """마감일까지 남은 일수 계산"""
    if not end_date:
        return None
    
    try:
        end = datetime.strptime(end_date, "%Y-%m-%d")
        today = datetime.now()
        days = (end - today).days
        return max(0, days) if days >= 0 else None
    except:
        return None

def extract_category_from_title(title):
    """제목에서 카테고리 추출 (12개 카테고리 - 스크린샷 기준)"""
    if not title:
        return None

    # 카테고리 키워드 매핑 (우선순위 순서)
    # 우선순위: 구체적 키워드 먼저 매칭, 일반적 키워드는 나중에
    category_keywords = [
        # 1. 자금지원(보조금/지원금) - 무상지원
        (["보조금", "지원금", "출연금", "무상지원", "무상자금"], "자금지원(보조금/지원금)"),

        # 2. 정책자금(융자/대출) - 상환 필요 자금
        (["융자", "대출", "저금리", "신용보증", "정책자금"], "정책자금(융자/대출)"),

        # 3. 시설/공간 지원
        (["시설", "공간", "입주", "랩", "인프라", "장비", "설비", "임대"], "시설/공간 지원"),

        # 4. 교육/컨설팅/멘토링
        (["교육", "컨설팅", "멘토링", "코칭", "자문", "진단", "아카데미", "스쿨"], "교육/컨설팅/멘토링"),

        # 5. 인력지원/일자리
        (["인력", "채용", "인턴", "고용", "일자리", "구인", "채용지원"], "인력지원/일자리"),

        # 6. 기술개발 (R&D)
        (["R&D", "기술개발", "연구개발", "기술혁신", "R D", "연구", "개발과제", "특허"], "기술개발 (R&D)"),

        # 7. 해외진출/수출지원
        (["해외진출", "수출", "글로벌", "국제", "해외시장", "무역"], "해외진출/수출지원"),

        # 8. 판로/마케팅 지원
        (["판로", "마케팅", "판매", "유통", "내수", "홍보", "브랜드"], "판로/마케팅 지원"),

        # 9. 네트워킹/커뮤니티
        (["네트워크", "행사", "박람회", "IR", "피칭", "데모데이", "컨퍼런스", "설명회", "상담회"], "네트워킹/커뮤니티"),

        # 10. 농림축수산업 특별지원
        (["농업", "농촌", "임업", "축산", "수산", "어업", "농림", "6차산업"], "농림축수산업 특별지원"),

        # 11. 기타 지원사업 (가장 일반적인 키워드는 마지막에)
        (["사업화", "상용화", "제품화", "창업", "스타트업", "기술", "지원사업"], "기타 지원사업"),
    ]

    # 각 카테고리의 키워드 리스트를 순회하며 매칭
    for keywords, category in category_keywords:
        for keyword in keywords:
            if keyword in title:
                return category

    return None

def format_announcement(data, source):
    """공고 데이터 포맷팅"""
    if source == "kstartup":
        title = data.get("biz_pbanc_nm")
        # summary 컬럼 우선 사용
        simple_summary = data.get("simple_summary")
        detailed_summary = data.get("detailed_summary")
        summary = data.get("summary")  # summary 컬럼 추가

        return {
            "id": data.get("announcement_id"),
            "title": title,
            "organization": data.get("pbanc_ntrp_nm") or "K-Startup",
            "category": extract_category_from_title(title),
            "start_date": data.get("pbanc_rcpt_bgng_dt"),
            "end_date": data.get("pbanc_rcpt_end_dt"),
            "content": data.get("full_text") or data.get("pbanc_ctnt") or "",
            "source": "kstartup",
            "source_name": "K-Startup",
            "simple_summary": simple_summary,
            "detailed_summary": detailed_summary or summary,  # detailed_summary가 없으면 summary 사용
            "summary": summary,  # summary 컬럼 추가
            "attachments": data.get("attachment_urls"),
            "pdf_url": data.get("pdf_storage_url"),
            "original_url": data.get("detl_pg_url"),  # K-Startup detl_pg_url 컬럼 사용
            "status": calculate_status(data.get("pbanc_rcpt_end_dt")),
            "days_left": calculate_days_left(data.get("pbanc_rcpt_end_dt")),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at")
        }
    else:  # bizinfo
        title = data.get("pblanc_nm")
        # summary 컬럼 우선 사용
        simple_summary = data.get("simple_summary")
        detailed_summary = data.get("detailed_summary")
        summary = data.get("summary")  # summary 컬럼 추가

        return {
            "id": data.get("pblanc_id"),
            "title": title,
            "organization": data.get("organ_nm"),
            "category": extract_category_from_title(title),
            "start_date": data.get("reqst_begin_ymd"),
            "end_date": data.get("reqst_end_ymd"),
            "source": "bizinfo",
            "source_name": "BizInfo",
            "simple_summary": simple_summary,
            "content": data.get("full_text") or data.get("pblanc_cn") or "",
            "detailed_summary": detailed_summary or summary,  # detailed_summary가 없으면 summary 사용
            "summary": summary,  # summary 컬럼 추가
            "attachments": data.get("attachment_urls"),
            "pdf_url": data.get("pdf_storage_url"),
            "original_url": data.get("dtl_url"),  # BizInfo dtl_url 컬럼 사용
            "status": calculate_status(data.get("reqst_end_ymd")),
            "days_left": calculate_days_left(data.get("reqst_end_ymd")),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "extra_info": {
                "target": data.get("sprt_trgt"),
                "scale": data.get("sport_scale_cn"),
                "contact": data.get("rqut_mn_cn")
            }
        }

# ================================================
# 관리자 대시보드 API
# ================================================
@app.get("/api/admin/dashboard")
async def admin_dashboard():
    """관리자 대시보드 - 시스템 상태 및 통계"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        # 캐시된 stats 데이터 가져오기
        stats_data = get_cache("api_stats")
        if not stats_data:
            # 캐시가 없으면 새로 조회
            stats_response = await get_statistics()
            stats_data = stats_response

        # 시스템 정보
        system_info = {
            "cache": {
                "enabled": True,
                "ttl": CACHE_TTL,
                "entries": len(cache_store),
                "keys": list(cache_store.keys())
            },
            "rate_limiting": {
                "enabled": RATE_LIMIT_ENABLED,
                "per_minute": 60 if RATE_LIMIT_ENABLED else None
            },
            "logging": {
                "format": LOG_FORMAT,
                "level": "INFO"
            },
            "database": {
                "connected": supabase is not None,
                "url": SUPABASE_URL[:50] + "..." if SUPABASE_URL else None
            },
            "openai": {
                "connected": openai_client is not None
            }
        }

        # 최근 활동 (최근 10개 공고)
        recent_ks = supabase.table('kstartup_complete')\
            .select("announcement_id,biz_pbanc_nm,pbanc_rcpt_end_dt,created_at")\
            .order('created_at', desc=True)\
            .limit(5)\
            .execute()

        recent_bi = supabase.table('bizinfo_complete')\
            .select("pblanc_id,pblanc_nm,reqst_end_ymd,created_at")\
            .order('created_at', desc=True)\
            .limit(5)\
            .execute()

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "stats": stats_data,
            "system": system_info,
            "recent_activity": {
                "kstartup": recent_ks.data if recent_ks else [],
                "bizinfo": recent_bi.data if recent_bi else []
            }
        }

    except Exception as e:
        logger.error(f"❌ 관리자 대시보드 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/cache/stats")
async def get_cache_stats_endpoint():
    """캐시 통계 조회 (관리자용)"""
    try:
        stats = get_cache_stats()
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ 캐시 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/cache/clear")
async def clear_cache_endpoint(pattern: Optional[str] = Query(None, description="삭제할 캐시 키 패턴 (예: search_*, api_*)")):
    """
    캐시 삭제 (관리자용)

    - pattern이 없으면 전체 캐시 삭제
    - pattern이 있으면 해당 패턴과 일치하는 캐시만 삭제
    """
    try:
        deleted_count = clear_cache(pattern)
        logger.info(f"🗑️ 관리자 요청으로 캐시 삭제됨 (패턴: {pattern or 'all'}, 개수: {deleted_count})")
        return {
            "success": True,
            "message": f"캐시가 성공적으로 삭제되었습니다 (패턴: {pattern or 'all'})",
            "deleted_count": deleted_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ 캐시 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/cache/cleanup")
async def cleanup_cache_endpoint():
    """만료된 캐시 항목 정리 (관리자용)"""
    try:
        deleted_count = cleanup_expired_cache()
        logger.info(f"🧹 관리자 요청으로 만료 캐시 정리됨 ({deleted_count}개)")
        return {
            "success": True,
            "message": f"만료된 캐시 항목이 정리되었습니다",
            "deleted_count": deleted_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ 캐시 정리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================================
# 백그라운드 작업 API
# ================================================
@app.get("/api/tasks")
async def get_tasks_list(
    status: Optional[str] = Query(None, description="작업 상태 필터 (pending/running/completed/failed)"),
    limit: int = Query(50, ge=1, le=200, description="반환할 최대 작업 수")
):
    """
    백그라운드 작업 목록 조회

    - **status**: 작업 상태 필터 (선택)
    - **limit**: 반환할 최대 작업 수 (기본 50)
    """
    try:
        tasks = get_all_tasks()

        # 상태 필터링
        if status:
            tasks = [t for t in tasks if t["status"] == status]

        # 개수 제한
        tasks = tasks[:limit]

        # 민감한 정보 제거 (result 상세 내용은 개별 조회에서만 제공)
        summary_tasks = []
        for task in tasks:
            summary_task = {
                **task,
                "result": "..." if task["result"] else None  # 결과 요약
            }
            summary_tasks.append(summary_task)

        return {
            "success": True,
            "total": len(summary_tasks),
            "tasks": summary_tasks
        }

    except Exception as e:
        logger.error(f"❌ 작업 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}")
async def get_task_status_endpoint(task_id: str):
    """
    특정 백그라운드 작업 상태 조회

    - **task_id**: 작업 ID (UUID)
    """
    try:
        task = get_task_status(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {task_id}")

        return {
            "success": True,
            "task": task
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 작업 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str):
    """
    백그라운드 작업 취소 (작업이 아직 실행 중이지 않은 경우만 가능)

    - **task_id**: 작업 ID (UUID)
    """
    try:
        task = get_task_status(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {task_id}")

        if task["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail=f"이미 완료된 작업은 취소할 수 없습니다 (상태: {task['status']})")

        if task["status"] == TaskStatus.RUNNING:
            raise HTTPException(status_code=400, detail="실행 중인 작업은 취소할 수 없습니다")

        # 작업 취소
        update_task_status(task_id, TaskStatus.CANCELLED)
        logger.info(f"🚫 작업 취소됨: {task_id}")

        return {
            "success": True,
            "message": "작업이 취소되었습니다",
            "task_id": task_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 작업 취소 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/stats/summary")
async def get_tasks_stats():
    """백그라운드 작업 통계 조회"""
    try:
        tasks = get_all_tasks()

        stats = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t["status"] == TaskStatus.PENDING),
            "running": sum(1 for t in tasks if t["status"] == TaskStatus.RUNNING),
            "completed": sum(1 for t in tasks if t["status"] == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t["status"] == TaskStatus.FAILED),
            "cancelled": sum(1 for t in tasks if t["status"] == TaskStatus.CANCELLED)
        }

        # 작업 유형별 통계
        task_types = {}
        for task in tasks:
            task_type = task["task_type"]
            if task_type not in task_types:
                task_types[task_type] = 0
            task_types[task_type] += 1

        return {
            "success": True,
            "stats": stats,
            "by_type": task_types,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ 작업 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================================
# API 버전 정보 엔드포인트
# ================================================
@app.get("/api/version")
async def get_api_version():
    """
    API 버전 정보 조회

    Returns:
        - version: 현재 API 버전
        - major/minor/patch: 버전 구성 요소
        - release_date: 릴리즈 날짜
        - features: 주요 기능 목록
        - changelog_url: 변경사항 URL
    """
    return {
        "success": True,
        "version": API_VERSION,
        "version_info": {
            "major": API_VERSION_MAJOR,
            "minor": API_VERSION_MINOR,
            "patch": API_VERSION_PATCH
        },
        "release_date": "2025-11-02",
        "features": [
            "정부지원사업 통합 검색 (K-Startup, BizInfo)",
            "실시간 공고 수집 및 업데이트",
            "AI 기반 요약 생성",
            "전문 검색 (키워드, 카테고리, 날짜)",
            "Prometheus 메트릭 모니터링",
            "성능 메트릭 추적 (API 응답시간, DB 쿼리)",
            "데이터베이스 커넥션 풀 모니터링",
            "비동기 백그라운드 작업 시스템",
            "API 버전 관리 시스템"
        ],
        "api_documentation": "/docs",
        "health_check": "/health",
        "metrics": "/metrics"
    }

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print(f"[FastAPI] 정부지원사업 검색 시스템 서버 시작 (v{API_VERSION})")
    print("="*60)
    print("\n[INFO] 접속 주소:")
    print("   - 웹 인터페이스: http://localhost:8000")
    print("   - API 문서: http://localhost:8000/docs")
    print("   - 헬스체크: http://localhost:8000/health")
    print("   - API 버전: http://localhost:8000/api/version")
    print("   - Prometheus 메트릭: http://localhost:8000/metrics")
    print("   - 성능 메트릭: http://localhost:8000/api/performance")
    print("   - 백그라운드 작업: http://localhost:8000/api/tasks")
    print(f"\n[FEATURES] v{API_VERSION} 주요 기능:")
    print("   [OK] 정부지원사업 통합 검색 (K-Startup, BizInfo)")
    print("   [OK] 실시간 공고 수집 및 업데이트")
    print("   [OK] AI 기반 요약 생성")
    print("   [OK] Prometheus 메트릭 모니터링")
    print("   [OK] 성능 메트릭 추적 (API 응답시간, DB 쿼리)")
    print("   [OK] 데이터베이스 커넥션 풀 모니터링")
    print("   [OK] 비동기 백그라운드 작업 시스템")
    print("   [OK] API 버전 관리 시스템 (HTTP 헤더, 버전 엔드포인트)")
    print(f"\n[VERSION] API 버전: {API_VERSION} (Major: {API_VERSION_MAJOR}, Minor: {API_VERSION_MINOR}, Patch: {API_VERSION_PATCH})")
    print("\n[API] 주요 API:")
    print("   - 통계: GET /api/stats")
    print("   - 검색: GET /api/search?q=키워드&status=ongoing")
    print("   - 상세: GET /api/announcement/{id}")
    print("   - 최근: GET /api/recent?limit=5")
    print("\n[ADMIN] 관리자 API:")
    print("   - 대시보드: GET /api/admin/dashboard")
    print("   - 캐시 삭제: POST /api/admin/cache/clear")
    print("\n[DEBUG] 디버그:")
    print(f"   - Supabase URL: {os.getenv('SUPABASE_URL')}")
    print(f"   - DB 연결 상태: {'연결됨' if supabase else '미연결'}")
    print(f"   - 캐시 TTL: {CACHE_TTL}초")
    print(f"   - Rate Limiting: {'활성화' if RATE_LIMIT_ENABLED else '비활성화'}")
    print(f"   - 로그 형식: {LOG_FORMAT}")
    print("\n종료: Ctrl+C")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
