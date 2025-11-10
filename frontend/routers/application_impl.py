# routers/application_impl.py
"""
신청서 작성 API 라우터 (완전 구현)

담당 엔드포인트:
- POST /api/application/analyze - 공고 분석 (Claude Sonnet 4.5)
- POST /api/application/analyze-company - 회사 분석 (Claude Sonnet 4.5)
- POST /api/application/compose - 신청서 생성 (GPT-4o)
- GET /api/application/status/{id} - 진행 상태 조회
- GET /api/application/download/{id} - 다운로드
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime, timedelta
import uuid
import os

# Supabase 클라이언트
from supabase import create_client, Client

# AI 서비스
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.ai.claude_service import ClaudeService
from services.ai.openai_service import OpenAIService
from models.application import (
    AnalyzeAnnouncementRequest,
    AnalyzeAnnouncementResponse,
    AnalyzeCompanyRequest,
    AnalyzeCompanyResponse,
    ComposeApplicationRequest,
    ComposeApplicationResponse,
    ApplicationStatusResponse,
    DownloadApplicationResponse,
    TierEnum,
    StyleEnum,
    ApplicationStatusEnum
)

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter(
    prefix="/api/application",
    tags=["Application"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

# Supabase 클라이언트 초기화
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# AI 서비스 초기화
try:
    claude_service = ClaudeService()
    openai_service = OpenAIService()
    logger.info("AI services initialized successfully")
except Exception as e:
    logger.warning(f"AI services initialization failed: {str(e)}")
    claude_service = None
    openai_service = None


# ============================================================================
# Helper Functions
# ============================================================================

def get_announcement_data(announcement_id: str, source: str) -> Dict[str, Any]:
    """
    Supabase에서 공고 데이터 조회 (Y)

    Args:
        announcement_id: 공고 ID
        source: "kstartup" or "bizinfo"

    Returns:
        {
            "full_text": "...",
            "parsed_info": {...},
            "simple_summary": "...",
            "detailed_summary": "..."
        }
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # 테이블 선택
    table_name = "kstartup_complete" if source == "kstartup" else "bizinfo_complete"

    # 데이터 조회
    result = supabase.table(table_name).select(
        "full_text, parsed_info, simple_summary, detailed_summary"
    ).eq("announcement_id" if source == "kstartup" else "pblanc_id", announcement_id).execute()

    if not result.data or len(result.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Announcement not found: {announcement_id} (source: {source})"
        )

    return result.data[0]


def check_analysis_cache(announcement_id: str, source: str) -> Optional[Dict[str, Any]]:
    """분석 캐시 조회"""
    if not supabase:
        return None

    try:
        result = supabase.table("analysis_cache").select("analysis, expires_at").eq(
            "announcement_id", announcement_id
        ).eq(
            "announcement_source", source
        ).execute()

        if result.data and len(result.data) > 0:
            cache = result.data[0]
            # 만료 확인
            if cache.get("expires_at"):
                expires_at = datetime.fromisoformat(cache["expires_at"].replace("Z", "+00:00"))
                if expires_at > datetime.now():
                    logger.info(f"Cache hit for {announcement_id}")
                    return cache["analysis"]

        return None

    except Exception as e:
        logger.error(f"Cache check failed: {str(e)}")
        return None


def save_analysis_cache(announcement_id: str, source: str, analysis: Dict[str, Any]):
    """분석 결과 캐시 저장 (7일 만료)"""
    if not supabase:
        return

    try:
        expires_at = datetime.now() + timedelta(days=7)

        supabase.table("analysis_cache").upsert({
            "announcement_id": announcement_id,
            "announcement_source": source,
            "analysis": analysis,
            "expires_at": expires_at.isoformat()
        }, on_conflict="announcement_id,announcement_source").execute()

        logger.info(f"Analysis cached for {announcement_id} (expires: {expires_at})")

    except Exception as e:
        logger.error(f"Cache save failed: {str(e)}")


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/analyze", response_model=AnalyzeAnnouncementResponse)
async def analyze_announcement(request: AnalyzeAnnouncementRequest) -> AnalyzeAnnouncementResponse:
    """
    공고문 분석 (Claude Sonnet 4.5)

    Y (공고문) = full_text + parsed_info 를 분석하여:
    - 자격요건
    - 평가기준
    - 심사위원 프로파일
    - 핵심키워드
    - 경쟁강도
    - 작성전략
    """
    try:
        if not claude_service:
            raise HTTPException(status_code=500, detail="Claude service not available")

        announcement_id = request.announcement_id
        source = request.source
        force_refresh = request.force_refresh

        logger.info(f"Analyzing announcement: {announcement_id} (source: {source}, force: {force_refresh})")

        # 캐시 확인 (force_refresh가 아닐 때)
        if not force_refresh:
            cached_analysis = check_analysis_cache(announcement_id, source)
            if cached_analysis:
                return AnalyzeAnnouncementResponse(
                    analysis_id=str(uuid.uuid4()),
                    announcement_id=announcement_id,
                    analysis=cached_analysis,
                    created_at=datetime.now()
                )

        # Supabase에서 Y 데이터 조회
        announcement_data = get_announcement_data(announcement_id, source)

        # Claude로 분석
        analysis = claude_service.analyze_announcement(
            full_text=announcement_data["full_text"],
            parsed_info=announcement_data["parsed_info"],
            simple_summary=announcement_data.get("simple_summary"),
            detailed_summary=announcement_data.get("detailed_summary")
        )

        # 캐시 저장
        save_analysis_cache(announcement_id, source, analysis)

        return AnalyzeAnnouncementResponse(
            analysis_id=str(uuid.uuid4()),
            announcement_id=announcement_id,
            analysis=analysis,
            created_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze announcement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-company", response_model=AnalyzeCompanyResponse)
async def analyze_company(request: AnalyzeCompanyRequest) -> AnalyzeCompanyResponse:
    """
    회사 정보 분석 (Claude Sonnet 4.5)

    Z (회사 정보) + 공고 분석 결과를 매칭하여:
    - 강점분석
    - 약점분석
    - 차별화포인트
    - 리스크체크
    - 최종전략
    """
    try:
        if not claude_service:
            raise HTTPException(status_code=500, detail="Claude service not available")

        logger.info("Analyzing company against announcement requirements")

        # Claude로 회사 분석
        company_analysis = claude_service.analyze_company(
            announcement_analysis=request.announcement_analysis,
            company_info=request.company_info.dict()
        )

        return AnalyzeCompanyResponse(
            analysis_id=str(uuid.uuid4()),
            company_analysis=company_analysis,
            created_at=datetime.now()
        )

    except Exception as e:
        logger.error(f"Failed to analyze company: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compose", response_model=ComposeApplicationResponse)
async def compose_application(
    request: ComposeApplicationRequest,
    background_tasks: BackgroundTasks
) -> ComposeApplicationResponse:
    """
    신청서 생성 (GPT-4o)

    공고 분석 + 회사 분석 결과를 기반으로 선택한 스타일의 신청서 생성
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")
        if not openai_service or not claude_service:
            raise HTTPException(status_code=500, detail="AI services not available")

        logger.info(f"Creating application (style: {request.style}, tier: {request.tier})")

        # 신청서 ID 생성
        application_id = str(uuid.uuid4())

        # applications 테이블에 레코드 생성 (status: processing)
        supabase.table("applications").insert({
            "id": application_id,
            "user_id": request.user_id,
            "tier": request.tier,
            "announcement_analysis": request.announcement_analysis,
            "company_info": request.company_analysis.get("company_info"),  # Z 정보 저장
            "company_analysis": request.company_analysis,
            "status": "processing",
            "progress": 0,
            "current_step": "initializing"
        }).execute()

        # 백그라운드 작업으로 신청서 생성 실행
        background_tasks.add_task(
            generate_application_background,
            application_id=application_id,
            announcement_analysis=request.announcement_analysis,
            company_analysis=request.company_analysis,
            style=request.style,
            tier=request.tier
        )

        return ComposeApplicationResponse(
            application_id=application_id,
            status=ApplicationStatusEnum.processing,
            message="신청서 생성이 시작되었습니다. 1-4분 소요됩니다."
        )

    except Exception as e:
        logger.error(f"Failed to compose application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{application_id}", response_model=ApplicationStatusResponse)
async def get_application_status(application_id: str) -> ApplicationStatusResponse:
    """신청서 생성 진행 상태 조회"""
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        logger.info(f"Checking status for application: {application_id}")

        # applications 테이블에서 조회
        result = supabase.table("applications").select(
            "status, progress, current_step, documents, error_message"
        ).eq("id", application_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Application not found: {application_id}")

        app = result.data[0]

        return ApplicationStatusResponse(
            application_id=application_id,
            status=app["status"],
            progress=app["progress"],
            current_step=app.get("current_step"),
            documents=app.get("documents"),
            error=app.get("error_message")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get application status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{application_id}", response_model=DownloadApplicationResponse)
async def download_application(
    application_id: str,
    format: str = "docx"
) -> DownloadApplicationResponse:
    """
    신청서 다운로드

    TODO: python-docx로 DOCX 변환, Supabase Storage 업로드
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        logger.info(f"Downloading application {application_id} as {format}")

        # applications 테이블에서 조회
        result = supabase.table("applications").select("documents, status").eq(
            "id", application_id
        ).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Application not found: {application_id}")

        app = result.data[0]

        if app["status"] != "completed":
            raise HTTPException(status_code=400, detail="Application not completed yet")

        # TODO: 실제 문서 변환 및 다운로드 URL 생성
        # 1. documents JSONB에서 선택한 스타일 추출
        # 2. python-docx로 DOCX 파일 생성
        # 3. Supabase Storage에 업로드
        # 4. 서명된 URL 생성 (24시간 유효)

        # 임시 응답
        return DownloadApplicationResponse(
            download_url="#",
            filename=f"신청서_{datetime.now().strftime('%Y-%m-%d')}.{format}",
            expires_at=datetime.now() + timedelta(hours=24)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Background Task
# ============================================================================

async def generate_application_background(
    application_id: str,
    announcement_analysis: Dict[str, Any],
    company_analysis: Dict[str, Any],
    style: str,
    tier: str
):
    """
    백그라운드에서 신청서 생성 실행

    1. 티어별 AI 추천 (Standard, Premium)
    2. GPT-4o 호출하여 신청서 생성
    3. 티어별 문서 개수 생성
    4. applications 테이블 업데이트
    """
    try:
        logger.info(f"Background task started for application {application_id}")

        # Progress 업데이트
        supabase.table("applications").update({
            "progress": 10,
            "current_step": "analyzing"
        }).eq("id", application_id).execute()

        # Step 1: AI 스타일 추천 (Standard, Premium만)
        ai_recommendation = None
        if tier in ["standard", "premium"]:
            logger.info("Generating AI style recommendation...")
            ai_recommendation = claude_service.recommend_style(
                announcement_analysis=announcement_analysis,
                company_analysis=company_analysis
            )

            supabase.table("applications").update({
                "progress": 30,
                "ai_recommendation": ai_recommendation
            }).eq("id", application_id).execute()

        # Step 2: 신청서 생성
        logger.info(f"Generating applications for tier: {tier}")

        supabase.table("applications").update({
            "progress": 40,
            "current_step": "generating"
        }).eq("id", application_id).execute()

        # 티어별 생성
        recommended_style = ai_recommendation.get("recommended_style") if ai_recommendation else None

        documents = openai_service.generate_tier_applications(
            announcement_analysis=announcement_analysis,
            company_analysis=company_analysis,
            tier=tier,
            recommended_style=recommended_style
        )

        supabase.table("applications").update({
            "progress": 90,
            "current_step": "finalizing"
        }).eq("id", application_id).execute()

        # Step 3: 완료 업데이트
        supabase.table("applications").update({
            "status": "completed",
            "progress": 100,
            "documents": documents,
            "updated_at": datetime.now().isoformat()
        }).eq("id", application_id).execute()

        logger.info(f"Application {application_id} generation completed successfully")

    except Exception as e:
        logger.error(f"Background task failed for application {application_id}: {str(e)}")

        # 실패 상태로 업데이트
        supabase.table("applications").update({
            "status": "failed",
            "error_message": str(e),
            "updated_at": datetime.now().isoformat()
        }).eq("id", application_id).execute()
