#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
북마크 API 라우터
- POST /api/bookmarks - 북마크 추가
- DELETE /api/bookmarks/{bookmark_id} - 북마크 삭제
- GET /api/bookmarks - 북마크 목록 조회 (페이지네이션)
- GET /api/bookmarks/check/{announcement_id} - 북마크 여부 확인
"""

from fastapi import APIRouter, HTTPException, Request, Query
from typing import Optional
import logging
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter(
    prefix="/api/bookmarks",
    tags=["Bookmarks"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

# Supabase 클라이언트 초기화
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ Supabase 환경변수가 설정되지 않았습니다")
    supabase: Optional[Client] = None
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase 클라이언트 초기화 완료 (Bookmarks)")
    except Exception as e:
        logger.error(f"❌ Supabase 클라이언트 초기화 실패: {str(e)}")
        supabase = None

# Rate Limiter (slowapi 사용)
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMIT_ENABLED = True
    logger.info("✅ Rate Limiting 활성화 (Bookmarks)")
except ImportError:
    limiter = None
    RATE_LIMIT_ENABLED = False
    logger.warning("⚠️ slowapi 미설치 - Rate Limiting 비활성화")


# ============================================================================
# Helper Functions
# ============================================================================

def extract_user_id_from_request(request: Request) -> str:
    """
    요청에서 user_id 추출

    현재 구현: 임시로 헤더에서 X-User-ID 추출
    TODO: NextAuth.js JWT 토큰 파싱으로 대체 필요

    Args:
        request: FastAPI Request 객체

    Returns:
        str: 사용자 ID

    Raises:
        HTTPException: 인증 정보가 없을 경우 401
    """
    # 방법 1: 헤더에서 X-User-ID 추출 (임시)
    user_id = request.headers.get("X-User-ID")

    # 방법 2: JWT 토큰에서 추출 (TODO: NextAuth.js 통합 시 구현)
    # authorization = request.headers.get("Authorization")
    # if authorization and authorization.startswith("Bearer "):
    #     token = authorization.split(" ")[1]
    #     # JWT 디코딩 로직 추가

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="인증이 필요합니다. X-User-ID 헤더를 제공해주세요."
        )

    return user_id


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("")
async def add_bookmark(
    request: Request,
    announcement_id: str = Query(..., description="공고 ID (예: KS_175399, PBLN_000000000116027)"),
    announcement_source: str = Query(..., description="공고 출처 (kstartup 또는 bizinfo)")
):
    """
    북마크 추가

    - **announcement_id**: 공고 ID (KS_ 또는 PBLN_ 접두사 포함)
    - **announcement_source**: 공고 출처 (kstartup 또는 bizinfo)

    Returns:
        북마크 정보 (id, user_id, announcement_id, announcement_source, created_at)
    """
    # Rate Limiting 적용
    if RATE_LIMIT_ENABLED and limiter:
        limiter.limit("60/minute")(add_bookmark)

    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

        # 사용자 ID 추출
        user_id = extract_user_id_from_request(request)

        # 입력 검증
        if announcement_source not in ["kstartup", "bizinfo"]:
            raise HTTPException(
                status_code=400,
                detail="announcement_source는 'kstartup' 또는 'bizinfo'여야 합니다"
            )

        # 북마크 추가
        result = supabase.table("bookmarks").insert({
            "user_id": user_id,
            "announcement_id": announcement_id,
            "announcement_source": announcement_source
        }).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="북마크 추가 실패")

        logger.info(f"✅ 북마크 추가 성공: user_id={user_id}, announcement_id={announcement_id}")

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)

        # 중복 키 에러 처리
        if "duplicate key" in error_message.lower() or "unique constraint" in error_message.lower():
            raise HTTPException(
                status_code=409,
                detail="이미 북마크된 공고입니다"
            )

        logger.error(f"❌ 북마크 추가 실패: {error_message}")
        raise HTTPException(status_code=500, detail=f"북마크 추가 중 오류 발생: {error_message}")


@router.delete("/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    request: Request
):
    """
    북마크 삭제

    - **bookmark_id**: 삭제할 북마크 ID

    Returns:
        삭제 결과 메시지
    """
    # Rate Limiting 적용
    if RATE_LIMIT_ENABLED and limiter:
        limiter.limit("60/minute")(delete_bookmark)

    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

        # 사용자 ID 추출
        user_id = extract_user_id_from_request(request)

        # 북마크 삭제 (RLS 정책으로 자동으로 user_id 검증)
        result = supabase.table("bookmarks").delete().eq(
            "id", bookmark_id
        ).eq("user_id", user_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="북마크를 찾을 수 없습니다 (이미 삭제되었거나 권한이 없습니다)"
            )

        logger.info(f"✅ 북마크 삭제 성공: bookmark_id={bookmark_id}, user_id={user_id}")

        return {
            "message": "북마크가 삭제되었습니다",
            "deleted_id": bookmark_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 북마크 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"북마크 삭제 중 오류 발생: {str(e)}")


@router.get("")
async def get_bookmarks(
    request: Request,
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기 (1-100)")
):
    """
    사용자 북마크 목록 조회 (페이지네이션)

    - **page**: 페이지 번호 (1부터 시작)
    - **page_size**: 페이지 크기 (1-100, 기본값 20)

    Returns:
        북마크 목록 및 페이지 정보
    """
    # Rate Limiting 적용
    if RATE_LIMIT_ENABLED and limiter:
        limiter.limit("60/minute")(get_bookmarks)

    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

        # 사용자 ID 추출
        user_id = extract_user_id_from_request(request)

        # 전체 개수 조회
        count_result = supabase.table("bookmarks").select(
            "id",
            count="exact"
        ).eq("user_id", user_id).execute()

        total = count_result.count if hasattr(count_result, 'count') else 0

        # 페이지네이션 계산
        offset = (page - 1) * page_size

        # 북마크 목록 조회 (최신순)
        result = supabase.table("bookmarks").select(
            "*"
        ).eq("user_id", user_id).order(
            "created_at", desc=True
        ).range(offset, offset + page_size - 1).execute()

        bookmarks = result.data if result.data else []

        logger.info(f"✅ 북마크 목록 조회 성공: user_id={user_id}, total={total}, page={page}")

        return {
            "bookmarks": bookmarks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 북마크 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"북마크 목록 조회 중 오류 발생: {str(e)}")


@router.get("/check/{announcement_id}")
async def check_bookmark(
    announcement_id: str,
    announcement_source: str = Query(..., description="공고 출처 (kstartup 또는 bizinfo)"),
    request: Request = None
):
    """
    특정 공고의 북마크 여부 확인

    - **announcement_id**: 공고 ID
    - **announcement_source**: 공고 출처 (kstartup 또는 bizinfo)

    Returns:
        북마크 여부 및 북마크 ID (있을 경우)
    """
    # Rate Limiting 적용
    if RATE_LIMIT_ENABLED and limiter:
        limiter.limit("60/minute")(check_bookmark)

    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="데이터베이스 연결 실패")

        # 사용자 ID 추출
        user_id = extract_user_id_from_request(request)

        # 북마크 확인
        result = supabase.table("bookmarks").select(
            "id, created_at"
        ).eq("user_id", user_id).eq(
            "announcement_id", announcement_id
        ).eq(
            "announcement_source", announcement_source
        ).execute()

        is_bookmarked = result.data and len(result.data) > 0
        bookmark_data = result.data[0] if is_bookmarked else None

        return {
            "is_bookmarked": is_bookmarked,
            "bookmark_id": bookmark_data["id"] if bookmark_data else None,
            "created_at": bookmark_data["created_at"] if bookmark_data else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 북마크 확인 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"북마크 확인 중 오류 발생: {str(e)}")
