# routers/application_impl.py
"""
신청서 작성 API 라우터 (완전 구현)

담당 엔드포인트:
- POST /api/application/analyze - 공고 분석 (Claude Sonnet 4.5)
- POST /api/application/analyze-company - 회사 분석 (Claude Sonnet 4.5)
- POST /api/application/compose - 신청서 생성 (GPT-4o)
- GET /api/application/status/{id} - 진행 상태 조회
- GET /api/application/download/{id} - 다운로드
- GET /api/application/revision-credits - 수정권 잔액 조회
- POST /api/application/revise - 신청서 수정 요청
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Body
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
    ApplicationStatusEnum,
    RevisionRequest,
    RevisionResponse,
    RevisionCreditsBalance,
    PurchaseRevisionRequest,
    PurchaseRevisionResponse,
    FeedbackReviseRequest,
    FeedbackReviseResponse,
    ApplicationContentModel,
    ApplicationSection
)

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter(
    prefix="/api/application-writer",
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

def get_selected_task_info(announcement_id: str, task_number: int) -> Optional[Dict[str, Any]]:
    """
    Writing Analysis 결과에서 선택한 과제 정보 추출

    Args:
        announcement_id: 공고 ID
        task_number: 선택한 과제 번호

    Returns:
        {
            "task_number": 1,
            "task_name": "AI 기반 솔루션 개발",
            "description": "...",
            "required_info": [...],
            "evaluation_points": [...]
        }
        또는 None (과제를 찾지 못한 경우)
    """
    if not supabase:
        logger.error("[get_selected_task_info] Supabase not configured")
        return None

    try:
        logger.info(f"[get_selected_task_info] Fetching task info for announcement_id={announcement_id}, task_number={task_number}")

        # Supabase에서 writing_analysis 결과 조회
        # 먼저 kstartup_complete 테이블 시도
        result = supabase.table("kstartup_complete").select(
            "writing_analysis"
        ).eq("announcement_id", announcement_id).execute()

        # kstartup_complete에 없으면 bizinfo_complete 시도
        if not result.data or len(result.data) == 0:
            result = supabase.table("bizinfo_complete").select(
                "writing_analysis"
            ).eq("pblanc_id", announcement_id).execute()

        if not result.data or len(result.data) == 0:
            logger.warning(f"⚠️ No writing analysis found for {announcement_id}")
            return None

        # writing_analysis JSONB 파싱
        writing_analysis = result.data[0].get("writing_analysis")

        if not writing_analysis:
            logger.warning(f"⚠️ writing_analysis field is empty for {announcement_id}")
            return None

        # 실제 데이터 구조 확인: tasks.task_list
        tasks_data = writing_analysis.get("tasks", {})

        if not tasks_data or not isinstance(tasks_data, dict):
            logger.warning(f"⚠️ No 'tasks' field found in writing_analysis for {announcement_id}")
            return None

        task_list = tasks_data.get("task_list", [])

        if not task_list or not isinstance(task_list, list):
            logger.warning(f"⚠️ No 'task_list' found in writing_analysis for {announcement_id}")
            return None

        # 선택한 과제 찾기
        for task in task_list:
            if task.get("task_number") == task_number:
                logger.info(f"✅ Found task {task_number}: {task.get('task_name')}")
                return task

        logger.warning(f"⚠️ Task {task_number} not found in analysis (total tasks: {len(task_list)})")
        return None

    except Exception as e:
        logger.error(f"❌ Error fetching task info: {str(e)}")
        return None


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
    logger.info(f"[get_announcement_data] START: announcement_id={announcement_id}, source={source}")

    if not supabase:
        logger.error("[get_announcement_data] Supabase not configured")
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # 테이블 선택
    table_name = "kstartup_complete" if source == "kstartup" else "bizinfo_complete"
    logger.info(f"[get_announcement_data] Using table: {table_name}")

    # 데이터 조회
    try:
        result = supabase.table(table_name).select(
            "full_text, parsed_info, simple_summary, detailed_summary"
        ).eq("announcement_id" if source == "kstartup" else "pblanc_id", announcement_id).execute()

        logger.info(f"[get_announcement_data] Supabase query executed, result.data length: {len(result.data) if result.data else 0}")

    except Exception as e:
        logger.error(f"[get_announcement_data] Supabase query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

    if not result.data or len(result.data) == 0:
        logger.warning(f"[get_announcement_data] Announcement not found: {announcement_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Announcement not found: {announcement_id} (source: {source})"
        )

    data = result.data[0]
    logger.info(f"[get_announcement_data] SUCCESS: full_text length={len(data.get('full_text', ''))}, parsed_info type={type(data.get('parsed_info'))}")

    return data


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
                from datetime import timezone
                expires_at = datetime.fromisoformat(cache["expires_at"].replace("Z", "+00:00"))
                now_utc = datetime.now(timezone.utc)  # UTC 타임존 추가
                if expires_at > now_utc:
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
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)  # UTC로 통일

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
    print("=" * 80)
    print("DEBUG: analyze_announcement endpoint called!")
    print(f"DEBUG: announcement_id={request.announcement_id}, source={request.source}")
    print("=" * 80)
    try:
        logger.info(f"[analyze_announcement] === API ENDPOINT START ===")

        if not claude_service:
            logger.error("[analyze_announcement] Claude service not available")
            raise HTTPException(status_code=500, detail="Claude service not available")

        announcement_id = request.announcement_id
        source = request.source
        force_refresh = request.force_refresh

        logger.info(f"[analyze_announcement] Request: announcement_id={announcement_id}, source={source}, force_refresh={force_refresh}")

        # 캐시 확인 (force_refresh가 아닐 때)
        if not force_refresh:
            logger.info("[analyze_announcement] Checking cache...")
            cached_analysis = check_analysis_cache(announcement_id, source)
            if cached_analysis:
                logger.info("[analyze_announcement] Cache hit! Returning cached analysis")
                return AnalyzeAnnouncementResponse(
                    analysis_id=str(uuid.uuid4()),
                    announcement_id=announcement_id,
                    analysis=cached_analysis,
                    created_at=datetime.now()
                )
            logger.info("[analyze_announcement] Cache miss, proceeding with analysis")

        # Supabase에서 Y 데이터 조회
        logger.info("[analyze_announcement] Calling get_announcement_data()...")
        announcement_data = get_announcement_data(announcement_id, source)
        logger.info(f"[analyze_announcement] Got announcement_data: full_text length={len(announcement_data.get('full_text', ''))}, parsed_info keys={list(announcement_data.get('parsed_info', {}).keys()) if isinstance(announcement_data.get('parsed_info'), dict) else 'N/A'}")

        # Claude로 분석
        logger.info("[analyze_announcement] Calling claude_service.analyze_announcement()...")
        analysis = claude_service.analyze_announcement(
            full_text=announcement_data["full_text"],
            parsed_info=announcement_data["parsed_info"],
            simple_summary=announcement_data.get("simple_summary"),
            detailed_summary=announcement_data.get("detailed_summary")
        )
        logger.info("[analyze_announcement] Claude analysis completed successfully")

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


@router.post("/profile-questions")
async def generate_profile_questions(request: Dict[str, Any] = Body(...)):
    """
    회사 정보 수집을 위한 AI 질문 생성 (과제 선택 정보 반영)

    프론트엔드에서 전달받은 정보:
    - announcement_id: 공고 ID
    - announcement_source: 공고 출처 (kstartup/bizinfo)
    - selectedTaskNumber: 선택한 과제 번호 (optional)
    - requiredInfoList: 필수 정보 목록 (optional)

    Returns:
        선택한 과제에 최적화된 질문 목록
    """
    try:
        if not claude_service:
            raise HTTPException(status_code=500, detail="Claude service not available")

        announcement_id = request.get("announcement_id")
        announcement_source = request.get("announcement_source")
        selected_task_number = request.get("selectedTaskNumber")
        required_info_list = request.get("requiredInfoList", [])

        logger.info(f"[profile-questions] announcement_id={announcement_id}, task={selected_task_number}")

        # 선택한 과제 정보 가져오기
        task_info = None
        if selected_task_number:
            task_info = get_selected_task_info(announcement_id, selected_task_number)
            if task_info:
                logger.info(f"✅ Found task info: {task_info.get('task_name')}")
            else:
                logger.warning(f"⚠️ Task {selected_task_number} not found for {announcement_id}")

        # AI 질문 생성 (선택한 과제 정보 반영)
        questions = claude_service.generate_profile_questions(
            announcement_id=announcement_id,
            announcement_source=announcement_source,
            task_info=task_info,
            required_info_list=required_info_list
        )

        return {
            "questions": questions,
            "task_number": selected_task_number,
            "task_name": task_info.get("task_name") if task_info else None
        }

    except Exception as e:
        logger.error(f"Failed to generate profile questions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile-chat")
async def profile_chat(request: Dict[str, Any] = Body(...)):
    """
    회사 정보 수집 대화형 챗봇 (과제 선택 정보 반영)

    Args:
        - announcement_id: 공고 ID
        - announcement_source: 공고 출처
        - message: 사용자 메시지
        - conversation_history: 대화 기록
        - selectedTaskNumber: 선택한 과제 번호 (optional)
        - requiredInfoList: 필수 정보 목록 (optional)

    Returns:
        AI 응답 메시지
    """
    try:
        if not claude_service:
            raise HTTPException(status_code=500, detail="Claude service not available")

        announcement_id = request.get("announcement_id")
        announcement_source = request.get("announcement_source")
        user_message = request.get("user_message") or request.get("message")
        conversation_history = request.get("conversation_history", [])
        selected_task_number = request.get("selectedTaskNumber")
        required_info_list = request.get("requiredInfoList", [])

        logger.info(f"[profile-chat] announcement_id={announcement_id}, task={selected_task_number}")
        logger.info(f"[profile-chat] user_message: {user_message[:50] if user_message else 'None'}...")

        # 선택한 과제 정보 가져오기
        task_info = None
        if selected_task_number:
            task_info = get_selected_task_info(announcement_id, selected_task_number)
            if task_info:
                logger.info(f"✅ Task context: {task_info.get('task_name')}")

        # AI 챗봇 응답 생성 (과제 정보를 시스템 프롬프트에 포함)
        chat_result = claude_service.profile_chat(
            announcement_id=announcement_id,
            announcement_source=announcement_source,
            user_message=user_message,
            conversation_history=conversation_history,
            task_info=task_info,
            required_info_list=required_info_list
        )

        # chat_result가 dict인지 str인지 확인 (하위 호환성)
        if isinstance(chat_result, dict):
            ai_response = chat_result.get("ai_response", "")
            completion_percentage = chat_result.get("completion_percentage", 0)
            extracted_data = chat_result.get("extracted_data", {})
        else:
            ai_response = chat_result
            completion_percentage = 0
            extracted_data = {}

        logger.info(f"[profile-chat] completion_percentage: {completion_percentage}%")

        return {
            "message": ai_response,
            "ai_response": ai_response,  # 프론트엔드 호환성 추가
            "task_number": selected_task_number,
            "task_name": task_info.get("task_name") if task_info else None,
            "completion_percentage": completion_percentage,
            "extracted_data": extracted_data
        }

    except Exception as e:
        logger.error(f"Failed in profile chat: {str(e)}")
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

        # company_info를 dict로 변환 (Union[CompanyInfo, Dict] 처리)
        if isinstance(request.company_info, dict):
            company_info_dict = request.company_info
        else:
            company_info_dict = request.company_info.dict()

        # Claude로 회사 분석
        company_analysis = claude_service.analyze_company(
            announcement_analysis=request.announcement_analysis,
            company_info=company_info_dict
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
    결제 후 에러 발생 시 추가 결제 없이 재시도 가능
    """
    import time
    start_time = time.time()

    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")
        if not openai_service or not claude_service:
            raise HTTPException(status_code=500, detail="AI services not available")

        logger.info(f"[PERF] START compose_application (order_id: {request.order_id})")

        # 1. 주문(결제) 검증
        t1 = time.time()
        order_result = supabase.table("orders").select("*").eq("id", request.order_id).execute()
        logger.info(f"[PERF] Order query took {time.time() - t1:.3f}s")

        if not order_result.data or len(order_result.data) == 0:
            raise HTTPException(status_code=404, detail=f"주문을 찾을 수 없습니다: {request.order_id}")

        order = order_result.data[0]

        # 결제 완료 상태가 아니면 거부
        if order["status"] != "paid":
            raise HTTPException(
                status_code=400,
                detail=f"결제가 완료되지 않았습니다. 현재 상태: {order['status']}"
            )

        # 사용자 ID 일치 확인
        if order["user_id"] != request.user_id:
            raise HTTPException(status_code=403, detail="본인의 주문이 아닙니다")

        # 2. 동일 order_id로 이미 성공한 신청서가 있는지 확인
        t2 = time.time()
        existing_apps = supabase.table("applications").select("*").eq(
            "order_id", request.order_id
        ).eq("status", "completed").execute()
        logger.info(f"[PERF] Existing app query took {time.time() - t2:.3f}s")

        if existing_apps.data and len(existing_apps.data) > 0:
            # 이미 성공한 신청서가 있으면 중복 생성 방지
            existing_app = existing_apps.data[0]
            logger.warning(f"Order {request.order_id} already has completed application: {existing_app['id']}")
            return ComposeApplicationResponse(
                application_id=existing_app["id"],
                status=ApplicationStatusEnum.completed,
                message="이미 생성된 신청서가 있습니다. 추가 결제 없이 기존 신청서를 이용하실 수 있습니다."
            )

        # 3. 실패한 신청서가 있다면 재시도 허용
        t3 = time.time()
        failed_apps = supabase.table("applications").select("*").eq(
            "order_id", request.order_id
        ).eq("status", "failed").execute()
        logger.info(f"[PERF] Failed app query took {time.time() - t3:.3f}s")

        if failed_apps.data and len(failed_apps.data) > 0:
            logger.info(f"Retrying failed application for order {request.order_id}")

        # 4. 신청서 ID 생성
        application_id = str(uuid.uuid4())

        # 5. applications 테이블에 레코드 생성 (status: processing)
        t4 = time.time()
        supabase.table("applications").insert({
            "id": application_id,
            "user_id": request.user_id,
            "order_id": request.order_id,  # 결제 정보 연결
            "tier": request.tier,
            "announcement_analysis": request.announcement_analysis,
            "company_info": request.company_info,  # Z 정보 저장
            "company_analysis": request.company_analysis,
            "status": "processing",
            "progress": 0,
            "current_step": "initializing"
        }).execute()
        logger.info(f"[PERF] Application insert took {time.time() - t4:.3f}s")

        # 6. 백그라운드 작업으로 신청서 생성 실행
        t5 = time.time()
        background_tasks.add_task(
            generate_application_background,
            application_id=application_id,
            announcement_analysis=request.announcement_analysis,
            company_analysis=request.company_analysis,
            style=request.style,
            tier=request.tier
        )
        logger.info(f"[PERF] Background task registration took {time.time() - t5:.3f}s")
        logger.info(f"[PERF] TOTAL compose_application took {time.time() - start_time:.3f}s")

        return ComposeApplicationResponse(
            application_id=application_id,
            status=ApplicationStatusEnum.processing,
            message="신청서 생성이 시작되었습니다. 1-4분 소요됩니다."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compose application: {str(e)}")
        logger.error(f"[PERF] Failed after {time.time() - start_time:.3f}s")
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


@router.get("/revision-credits", response_model=RevisionCreditsBalance)
async def get_revision_credits(user_id: str) -> RevisionCreditsBalance:
    """
    수정권 잔액 조회

    Args:
        user_id: 사용자 ID

    Returns:
        티어 수정권, 구매 수정권, 전체 수정권 잔액
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        logger.info(f"Checking revision credits for user: {user_id}")

        # revision_credits 테이블에서 수정권 잔액 조회 (티어 정보 포함)
        result = supabase.table("revision_credits").select(
            "current_tier, tier_granted_at, tier_credits_available, purchased_credits_available, total_available"
        ).eq("user_id", user_id).execute()

        # 레코드가 없으면 기본값으로 초기화 (basic 티어, 0개)
        if not result.data or len(result.data) == 0:
            logger.info(f"No revision credits record found for user {user_id}, returning zero balance")
            return RevisionCreditsBalance(
                current_tier="basic",
                tier_granted_at=datetime.now(),
                tier_credits_available=0,
                purchased_credits_available=0,
                total_available=0
            )

        # 레코드가 있으면 실제 값 반환
        credits = result.data[0]
        return RevisionCreditsBalance(
            current_tier=credits["current_tier"],
            tier_granted_at=datetime.fromisoformat(credits["tier_granted_at"]),
            tier_credits_available=credits["tier_credits_available"],
            purchased_credits_available=credits["purchased_credits_available"],
            total_available=credits["total_available"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get revision credits: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-applications")
async def get_user_applications(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    status_filter: str | None = None
):
    """
    사용자별 신청서 목록 조회

    Args:
        user_id: 사용자 ID
        limit: 조회 개수 (기본 20개)
        offset: 시작 위치 (페이지네이션)
        status_filter: 상태 필터 (completed, failed, processing 등)

    Returns:
        신청서 목록 (프론트엔드 형식으로 변환)
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        logger.info(f"[user-applications] 조회 시작: user_id={user_id}, limit={limit}, offset={offset}")

        # 기본 쿼리
        query = supabase.table("applications").select(
            "id, announcement_id, announcement_source, "
            "tier, status, created_at, updated_at, documents, announcement_analysis"
        ).eq("user_id", user_id).order("created_at", desc=True)

        # 상태 필터 적용
        if status_filter:
            query = query.eq("status", status_filter)

        # 페이지네이션
        query = query.range(offset, offset + limit - 1)

        response = query.execute()

        # 프론트엔드 형식으로 변환
        formatted_applications = []
        for app in response.data:
            # announcement_title 추출 (여러 소스에서 시도)
            announcement_title = "지원사업 공고"

            # 1. announcement_analysis에서 title 추출 시도
            if app.get("announcement_analysis"):
                analysis = app["announcement_analysis"]
                if isinstance(analysis, dict):
                    announcement_title = analysis.get("title") or analysis.get("announcement_title") or announcement_title

            # 2. 아직 기본값이면 DB에서 공고 제목 조회
            if announcement_title == "지원사업 공고" and app.get("announcement_id"):
                try:
                    source = app.get("announcement_source", "kstartup")
                    table_name = "kstartup_complete" if source == "kstartup" else "bizinfo_complete"
                    id_column = "announcement_id" if source == "kstartup" else "pblanc_id"

                    title_result = supabase.table(table_name).select("pblancNm, pblanc_nm, title").eq(
                        id_column, app["announcement_id"]
                    ).limit(1).execute()

                    if title_result.data and len(title_result.data) > 0:
                        row = title_result.data[0]
                        announcement_title = row.get("pblancNm") or row.get("pblanc_nm") or row.get("title") or announcement_title
                except Exception as title_err:
                    logger.warning(f"[user-applications] 공고 제목 조회 실패: {title_err}")

            # documents를 Array 형식으로 변환
            documents_array = []
            docs = app.get("documents")
            if docs:
                if isinstance(docs, dict):
                    # documents가 dict인 경우 (예: {"upgraded": {...}, "data": {...}})
                    # 가장 좋은 문서 선택 (upgraded > premium_a > data > balanced > story)
                    priority_keys = ["upgraded", "premium_a", "premium_b", "data", "balanced", "story", "aggressive", "conservative"]
                    selected_doc = None
                    for key in priority_keys:
                        if key in docs and docs[key]:
                            selected_doc = docs[key]
                            break

                    if selected_doc and isinstance(selected_doc, dict):
                        # documents 구조: {"_metadata": {...}, "사업명": "...", "기대 효과": {...}, ...}
                        # _metadata를 제외한 모든 키가 섹션
                        for section_name, section_content in selected_doc.items():
                            if section_name == "_metadata":
                                continue  # 메타데이터는 스킵

                            # section_content를 문자열로 변환
                            if isinstance(section_content, str):
                                content_str = section_content
                            elif isinstance(section_content, dict):
                                # 중첩 dict인 경우 (예: {"기대 효과": {"직접 효과": "...", "간접 효과": "..."}})
                                content_parts = []
                                for sub_key, sub_value in section_content.items():
                                    if isinstance(sub_value, str):
                                        content_parts.append(f"[{sub_key}]\n{sub_value}")
                                    elif isinstance(sub_value, dict):
                                        # 더 깊은 중첩
                                        sub_parts = []
                                        for k, v in sub_value.items():
                                            if isinstance(v, str):
                                                sub_parts.append(f"- {k}: {v}")
                                            elif isinstance(v, list):
                                                sub_parts.append(f"- {k}:")
                                                for item in v:
                                                    if isinstance(item, dict):
                                                        for ik, iv in item.items():
                                                            sub_parts.append(f"  • {ik}: {iv}")
                                                    else:
                                                        sub_parts.append(f"  • {item}")
                                            else:
                                                sub_parts.append(f"- {k}: {v}")
                                        content_parts.append(f"[{sub_key}]\n" + "\n".join(sub_parts))
                                    elif isinstance(sub_value, list):
                                        list_items = []
                                        for item in sub_value:
                                            if isinstance(item, dict):
                                                item_strs = [f"{k}: {v}" for k, v in item.items()]
                                                list_items.append(" | ".join(item_strs))
                                            else:
                                                list_items.append(str(item))
                                        content_parts.append(f"[{sub_key}]\n" + "\n".join([f"• {i}" for i in list_items]))
                                    else:
                                        content_parts.append(f"[{sub_key}]\n{sub_value}")
                                content_str = "\n\n".join(content_parts)
                            elif isinstance(section_content, list):
                                content_str = "\n".join([str(item) for item in section_content])
                            else:
                                content_str = str(section_content) if section_content else ""

                            if content_str:  # 빈 내용은 스킵
                                documents_array.append({
                                    "section_name": section_name,
                                    "content": content_str
                                })
                elif isinstance(docs, list):
                    # documents가 이미 Array인 경우
                    for doc in docs:
                        if isinstance(doc, dict):
                            documents_array.append({
                                "section_name": doc.get("section_name") or doc.get("title") or "섹션",
                                "content": doc.get("content") or ""
                            })

            formatted_app = {
                "application_id": app["id"],
                "announcement_id": app.get("announcement_id") or "",
                "announcement_source": app.get("announcement_source") or "kstartup",
                "announcement_title": announcement_title,
                "tier": app.get("tier") or "basic",
                "status": app.get("status") or "processing",
                "created_at": app.get("created_at"),
                "completed_at": app.get("updated_at") if app.get("status") == "completed" else None,
                "documents": documents_array
            }
            formatted_applications.append(formatted_app)

        logger.info(f"[user-applications] 조회 완료: {len(formatted_applications)}건")

        return {
            "applications": formatted_applications,
            "total": len(formatted_applications),
            "limit": limit,
            "offset": offset
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user applications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revise", response_model=RevisionResponse)
async def revise_application(
    request: RevisionRequest,
    background_tasks: BackgroundTasks
) -> RevisionResponse:
    """
    신청서 수정 요청

    Args:
        request: 수정 요청 (application_id, revision_type, instructions, sections)

    Returns:
        수정 성공 여부, 사용한 수정권, 남은 수정권
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")
        if not openai_service:
            raise HTTPException(status_code=500, detail="OpenAI service not available")

        logger.info(f"Revision request for application {request.application_id}")
        logger.info(f"Revision type: {request.revision_type}")

        # 1. 신청서 조회
        result = supabase.table("applications").select(
            "user_id, documents, status, tier"
        ).eq("id", request.application_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Application not found: {request.application_id}"
            )

        app = result.data[0]
        user_id = app["user_id"]

        if app["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail="Application not completed yet"
            )

        # 2. 수정권 사용 (use_revision_credit RPC 함수 호출)
        logger.info(f"Calling use_revision_credit for user: {user_id}")

        try:
            # Supabase RPC로 수정권 사용 함수 호출
            credit_result = supabase.rpc('use_revision_credit', {
                'p_user_id': user_id,
                'p_application_id': request.application_id,
                'p_revision_type': request.revision_type,
                'p_instructions': request.instructions,
                'p_sections': request.sections
            }).execute()

            if not credit_result.data or len(credit_result.data) == 0:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to use revision credit"
                )

            credit_info = credit_result.data[0]

            # 수정권 부족
            if not credit_info["success"]:
                logger.warning(f"Insufficient credits for user: {user_id}")
                return RevisionResponse(
                    success=False,
                    credits_used=0,
                    credit_type="tier",
                    remaining_credits=0,
                    error=credit_info["error_message"],
                    message="수정권 구매 후 다시 시도해주세요."
                )

            revision_usage_id = credit_info["revision_usage_id"]
            credit_type = credit_info["credit_type"]
            remaining_credits = credit_info["remaining_credits"]

            logger.info(f"Credit used successfully: {credit_type}, remaining: {remaining_credits}")

        except Exception as e:
            logger.error(f"Failed to use revision credit: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Credit deduction failed: {str(e)}")

        # 3. 백그라운드 태스크로 수정 작업 실행
        background_tasks.add_task(
            process_revision_background,
            application_id=request.application_id,
            revision_usage_id=revision_usage_id,
            revision_type=request.revision_type,
            instructions=request.instructions,
            sections=request.sections,
            documents=app["documents"],
            tier=app["tier"]
        )

        logger.info(f"Revision background task created: {revision_usage_id}")

        return RevisionResponse(
            success=True,
            revision_id=revision_usage_id,
            credits_used=1,
            credit_type=credit_type,
            remaining_credits=remaining_credits,
            estimated_time="3-5분",
            message="수정 요청이 접수되었습니다. 3-5분 후 결과를 확인하실 수 있습니다."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revise application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purchase-revision-credits", response_model=PurchaseRevisionResponse)
async def purchase_revision_credits(request: PurchaseRevisionRequest) -> PurchaseRevisionResponse:
    """
    수정권 구매 (PortOne 결제 완료 후 호출)

    Args:
        request: 구매 요청 (user_id, quantity, payment_id, order_id)

    Returns:
        구매 성공 여부, 추가된 수정권, 총 잔액
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        logger.info(f"Processing revision credit purchase for user: {request.user_id}")
        logger.info(f"Quantity: {request.quantity}, Order ID: {request.order_id}")

        # 가격 검증
        price_map = {
            1: 500,
            5: 2000,
            10: 3500
        }

        if request.quantity not in price_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid quantity: {request.quantity}. Must be 1, 5, or 10."
            )

        expected_price = price_map[request.quantity]

        # 1. revision_purchases 테이블에 구매 내역 저장
        expires_at = (datetime.now() + timedelta(days=365)).isoformat()

        purchase_record = {
            "id": str(uuid.uuid4()),
            "user_id": request.user_id,
            "quantity": request.quantity,
            "unit_price": expected_price,
            "total_price": expected_price,
            "payment_id": request.payment_id,
            "order_id": request.order_id,
            "payment_status": "completed",
            "credits_added": request.quantity,
            "expires_at": expires_at
        }

        supabase.table("revision_purchases").insert(purchase_record).execute()
        logger.info(f"Purchase record created: {purchase_record['id']}")

        # 2. revision_credits 테이블 업데이트 (구매 수정권 추가)
        # 기존 레코드 조회
        credits_result = supabase.table("revision_credits").select(
            "purchased_credits_total, purchased_credits_used"
        ).eq("user_id", request.user_id).execute()

        if not credits_result.data or len(credits_result.data) == 0:
            # 레코드가 없으면 새로 생성
            supabase.table("revision_credits").insert({
                "id": str(uuid.uuid4()),
                "user_id": request.user_id,
                "tier_credits_total": 0,
                "tier_credits_used": 0,
                "purchased_credits_total": request.quantity,
                "purchased_credits_used": 0
            }).execute()

            new_total = request.quantity
            logger.info(f"New revision_credits record created for user: {request.user_id}")
        else:
            # 기존 레코드 업데이트
            current_credits = credits_result.data[0]
            new_total = current_credits["purchased_credits_total"] + request.quantity

            supabase.table("revision_credits").update({
                "purchased_credits_total": new_total
            }).eq("user_id", request.user_id).execute()

            logger.info(f"Revision credits updated: {current_credits['purchased_credits_total']} → {new_total}")

        # 3. 최종 잔액 조회
        final_balance = supabase.table("revision_credits").select(
            "total_available"
        ).eq("user_id", request.user_id).execute()

        total_balance = final_balance.data[0]["total_available"] if final_balance.data else request.quantity

        logger.info(f"Purchase completed. Total balance: {total_balance}")

        return PurchaseRevisionResponse(
            success=True,
            credits_added=request.quantity,
            total_balance=total_balance,
            expires_at=datetime.fromisoformat(expires_at),
            message=f"수정권 {request.quantity}개가 성공적으로 추가되었습니다. (유효기간: 1년)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to purchase revision credits: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revision-history")
async def get_revision_history(user_id: str, limit: int = 20):
    """
    수정권 사용 내역 조회

    Args:
        user_id: 사용자 ID
        limit: 조회할 개수 (기본값: 20)

    Returns:
        수정 요청 목록
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        logger.info(f"Fetching revision history for user: {user_id}")

        # revision_usage 테이블에서 조회 (최신순)
        result = supabase.table("revision_usage").select(
            "id, application_id, revision_type, instructions, credit_type, status, created_at, completed_at, error_message"
        ).eq("user_id", user_id).order(
            "created_at", desc=True
        ).limit(limit).execute()

        revisions = result.data if result.data else []
        logger.info(f"Found {len(revisions)} revision records")

        return {
            "revisions": revisions,
            "count": len(revisions)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get revision history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Background Task
# ============================================================================

def generate_application_background(
    application_id: str,
    announcement_analysis: Dict[str, Any],
    company_analysis: Dict[str, Any],
    style: str,
    tier: str
):
    """
    백그라운드에서 신청서 생성 실행 (2025-11-12 최종 확정)

    워크플로우:
    - Basic: GPT-4o 1개 생성
    - Standard: GPT-4o 3개 생성 → Claude 분석 → GPT-4o 업그레이드 1개
    - Premium: GPT-4o 5개 생성 → Claude 분석 → GPT-4o 프리미엄 A/B 2개

    NOTE: 동기 함수로 변경 - FastAPI BackgroundTasks는 동기 함수를 완전히 백그라운드에서 실행
    """
    try:
        logger.info(f"Background task started for application {application_id} (tier: {tier})")

        # Progress 업데이트
        supabase.table("applications").update({
            "progress": 10,
            "current_step": "preparing"
        }).eq("id", application_id).execute()

        # Step 1: 기본 신청서 생성 (티어별 개수)
        logger.info(f"Step 1: Generating base applications for tier: {tier}")

        supabase.table("applications").update({
            "progress": 20,
            "current_step": "generating_base"
        }).eq("id", application_id).execute()

        # 기본 신청서 생성 (Basic: 1개, Standard: 3개, Premium: 5개)
        base_documents = openai_service.generate_tier_applications(
            announcement_analysis=announcement_analysis,
            company_analysis=company_analysis,
            tier=tier,
            recommended_style=None,  # 기본 생성에서는 사용 안 함
            claude_service=None  # Step 1에서는 필요 없음
        )

        supabase.table("applications").update({
            "progress": 50,
            "documents": base_documents  # 중간 저장 (기본 신청서)
        }).eq("id", application_id).execute()

        # Step 2: Claude 분석 + GPT-4o 업그레이드/프리미엄 생성 (Standard, Premium만)
        final_documents = base_documents

        if tier == "standard":
            logger.info("Step 2 (Standard): Claude analysis → GPT-4o upgrade")

            supabase.table("applications").update({
                "progress": 60,
                "current_step": "claude_analysis"
            }).eq("id", application_id).execute()

            # Claude가 3개 분석 → 1개 업그레이드 전략 도출
            applications_list = [base_documents[style] for style in ["data", "story", "balanced"]]
            claude_analysis = claude_service.analyze_applications_for_upgrade(
                applications=applications_list,
                announcement_analysis=announcement_analysis,
                company_analysis=company_analysis
            )

            supabase.table("applications").update({
                "progress": 75,
                "current_step": "generating_upgraded"
            }).eq("id", application_id).execute()

            # GPT-4o가 업그레이드 신청서 생성
            best_idx = claude_analysis["best_application_index"]
            best_app = applications_list[best_idx]
            upgrade_prompt = claude_analysis["upgrade_prompt"]

            upgraded_app = openai_service.generate_upgraded_application(
                base_application=best_app,
                upgrade_prompt=upgrade_prompt,
                announcement_analysis=announcement_analysis,
                company_analysis=company_analysis
            )

            # 최종 문서 = 기본 3개 + 업그레이드 1개
            final_documents["upgraded"] = upgraded_app

            logger.info("Standard tier: 4 applications generated (3 base + 1 upgraded)")

        elif tier == "premium":
            logger.info("Step 2 (Premium): Claude analysis → GPT-4o premium A/B")

            supabase.table("applications").update({
                "progress": 60,
                "current_step": "claude_analysis"
            }).eq("id", application_id).execute()

            # Claude가 5개 분석 → A/B 프리미엄 전략 도출
            applications_list = [
                base_documents[style]
                for style in ["data", "story", "balanced", "aggressive", "conservative"]
            ]
            claude_analysis = claude_service.analyze_applications_for_premium(
                applications=applications_list,
                announcement_analysis=announcement_analysis,
                company_analysis=company_analysis
            )

            supabase.table("applications").update({
                "progress": 75,
                "current_step": "generating_premium"
            }).eq("id", application_id).execute()

            # GPT-4o가 프리미엄 A/B 신청서 생성
            premium_a_prompt = claude_analysis["premium_a_strategy"]["upgrade_prompt"]
            premium_b_prompt = claude_analysis["premium_b_strategy"]["upgrade_prompt"]

            premium_apps = openai_service.generate_premium_applications(
                base_applications=applications_list,
                premium_a_prompt=premium_a_prompt,
                premium_b_prompt=premium_b_prompt,
                announcement_analysis=announcement_analysis,
                company_analysis=company_analysis
            )

            # 최종 문서 = 기본 5개 + 프리미엄 A/B 2개
            final_documents["premium_a"] = premium_apps["premium_a"]
            final_documents["premium_b"] = premium_apps["premium_b"]

            logger.info("Premium tier: 7 applications generated (5 base + 2 premium A/B)")

        else:  # basic
            logger.info("Basic tier: 1 application generated (no AI analysis)")

        # Step 3: 완료 업데이트
        supabase.table("applications").update({
            "progress": 90,
            "current_step": "finalizing"
        }).eq("id", application_id).execute()

        supabase.table("applications").update({
            "status": "completed",
            "progress": 100,
            "documents": final_documents,
            "updated_at": datetime.now().isoformat()
        }).eq("id", application_id).execute()

        logger.info(f"Application {application_id} generation completed successfully")
        logger.info(f"Final document count: {len(final_documents)}")

    except Exception as e:
        logger.error(f"Background task failed for application {application_id}: {str(e)}")

        # 실패 상태로 업데이트
        supabase.table("applications").update({
            "status": "failed",
            "error_message": str(e),
            "updated_at": datetime.now().isoformat()
        }).eq("id", application_id).execute()


@router.post("/compose-sync", response_model=Dict[str, Any])
async def compose_application_sync(
    request: ComposeApplicationRequest
):
    """
    동기 신청서 생성 엔드포인트 (테스트/개발 전용)

    프로덕션 /compose와 동일한 로직이지만, 백그라운드 처리 없이 즉시 결과 반환
    주문 검증은 생략하여 테스트 시 유연하게 사용 가능

    주의: 프로덕션 환경에서는 /compose 사용 권장 (비동기 처리로 UX 향상)
    """
    try:
        logger.info(f"=== Sync Application Generation Started ===")
        logger.info(f"Tier: {request.tier}, Style: {request.style}, User: {request.user_id}")

        # 1. OpenAI/Claude 서비스 초기화
        openai_service = OpenAIService()
        claude_service = ClaudeService()

        # 2. GPT-4o 기본 신청서 5개 생성
        logger.info("Step 1: GPT-4o generating 5 base applications")
        base_documents = {}

        for style in ["data", "story", "balanced", "aggressive", "conservative"]:
            app = openai_service.generate_application(
                announcement_analysis=request.announcement_analysis,
                company_analysis=request.company_analysis,
                style=style
            )
            base_documents[style] = app

        logger.info(f"Base documents generated: {len(base_documents)}")

        # 3. 최종 결과 문서
        final_documents = base_documents.copy()

        # 4. Tier별 추가 처리
        if request.tier == "standard":
            logger.info("Step 2 (Standard): Claude analysis → GPT-4o upgrade")

            # Claude가 3개 스타일 분석 후 업그레이드 전략 도출
            # balanced 스타일을 업그레이드 베이스로 사용 (가장 균형잡힌 스타일)
            base_style_for_upgrade = "balanced"
            selected_app = base_documents[base_style_for_upgrade]
            applications_for_analysis = [
                base_documents[style] for style in ["data", "story", "balanced"]
            ]
            claude_result = claude_service.analyze_applications_for_upgrade(
                applications=applications_for_analysis,
                announcement_analysis=request.announcement_analysis,
                company_analysis=request.company_analysis
            )
            upgrade_prompt = claude_result.get("upgrade_prompt", "")

            # GPT-4o가 업그레이드 버전 생성
            upgraded_app = openai_service.generate_upgraded_application(
                base_application=selected_app,
                upgrade_prompt=upgrade_prompt,
                announcement_analysis=request.announcement_analysis,
                company_analysis=request.company_analysis
            )

            final_documents["upgraded"] = upgraded_app
            logger.info("Standard tier: 4 applications (3 base + 1 upgraded)")

        elif request.tier == "premium":
            logger.info("Step 2 (Premium): Claude analysis → GPT-4o premium A/B")

            # Claude가 5개 전체 분석 → A/B 전략 도출
            applications_list = [
                base_documents[style]
                for style in ["data", "story", "balanced", "aggressive", "conservative"]
            ]
            claude_analysis = claude_service.analyze_applications_for_premium(
                applications=applications_list,
                announcement_analysis=request.announcement_analysis,
                company_analysis=request.company_analysis
            )

            # GPT-4o가 프리미엄 A/B 생성
            premium_a_prompt = claude_analysis["premium_a_strategy"]["upgrade_prompt"]
            premium_b_prompt = claude_analysis["premium_b_strategy"]["upgrade_prompt"]

            premium_apps = openai_service.generate_premium_applications(
                base_applications=applications_list,
                premium_a_prompt=premium_a_prompt,
                premium_b_prompt=premium_b_prompt,
                announcement_analysis=request.announcement_analysis,
                company_analysis=request.company_analysis
            )

            final_documents["premium_a"] = premium_apps["premium_a"]
            final_documents["premium_b"] = premium_apps["premium_b"]
            logger.info("Premium tier: 7 applications (5 base + 2 premium A/B)")

        else:  # basic
            logger.info("Basic tier: 1 application (no AI analysis)")

        # 5. 결과 반환
        logger.info(f"=== Sync Generation Completed: {len(final_documents)} documents ===")

        return {
            "success": True,
            "message": "신청서 생성 완료 (동기)",
            "documents": final_documents,
            "tier": request.tier,
            "style": request.style,
            "document_count": len(final_documents)
        }

    except Exception as e:
        logger.error(f"Sync generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"신청서 생성 실패: {str(e)}"
        )


async def process_revision_background(
    application_id: str,
    revision_usage_id: str,
    revision_type: str,
    instructions: str,
    sections: Optional[list[str]],
    documents: Dict[str, Any],
    tier: str
):
    """
    백그라운드에서 신청서 수정 처리

    Args:
        application_id: 신청서 ID
        revision_usage_id: 수정 사용 내역 ID (revision_usage 테이블)
        revision_type: 수정 유형
        instructions: 수정 지시사항
        sections: 수정할 섹션 목록 (선택)
        documents: 현재 신청서 문서들
        tier: 티어 (basic/standard/premium)
    """
    try:
        logger.info(f"Starting revision background task: {revision_usage_id}")
        logger.info(f"Revision type: {revision_type}")

        # 1. revision_usage 상태 업데이트 (processing → completed)
        supabase.table("revision_usage").update({
            "status": "processing"
        }).eq("id", revision_usage_id).execute()

        # 2. GPT-4o로 수정 요청 처리 (₩130/revision)
        logger.info("Processing revision with GPT-4o...")

        # revision_type별 프롬프트 생성
        revision_prompts = {
            "typo": "다음 신청서에서 오타와 맞춤법 오류를 수정해주세요.",
            "expression": "다음 신청서의 표현을 더 전문적이고 설득력 있게 개선해주세요.",
            "section_rewrite": f"다음 신청서의 {', '.join(sections) if sections else '전체'} 섹션을 재작성해주세요.",
            "style_change": "다음 신청서의 전체적인 스타일을 변경해주세요.",
            "full_restructure": "다음 신청서를 전체적으로 재구성하고 개선해주세요."
        }

        base_prompt = revision_prompts.get(revision_type, "다음 신청서를 수정해주세요.")
        full_prompt = f"{base_prompt}\n\n사용자 요청사항:\n{instructions}\n\n원본 신청서:\n{json.dumps(documents, ensure_ascii=False)}"

        # GPT-4o 수정 요청 (openai_service에 revise_application 메서드 추가 필요)
        revised_content = openai_service.revise_application(
            original_documents=documents,
            revision_type=revision_type,
            instructions=instructions,
            sections=sections
        )

        # 3. document_versions 테이블에 저장
        logger.info("Saving revised version to document_versions...")

        # 현재 버전 번호 조회
        version_result = supabase.table("document_versions").select("version").eq(
            "application_id", application_id
        ).order("version", desc=True).limit(1).execute()

        next_version = 1
        if version_result.data and len(version_result.data) > 0:
            next_version = version_result.data[0]["version"] + 1

        # 새 버전 저장
        supabase.table("document_versions").insert({
            "id": str(uuid.uuid4()),
            "application_id": application_id,
            "user_id": supabase.table("applications").select("user_id").eq(
                "id", application_id
            ).execute().data[0]["user_id"],
            "version": next_version,
            "is_original": False,
            "style": tier,
            "content": json.dumps(revised_content, ensure_ascii=False),
            "revision_type": revision_type,
            "revision_instructions": instructions,
            "metadata": {
                "revision_usage_id": revision_usage_id,
                "sections": sections,
                "content_length": len(json.dumps(revised_content, ensure_ascii=False))
            }
        }).execute()

        # 4. revision_usage 상태 업데이트 (processing → completed)
        supabase.table("revision_usage").update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "revision_id": str(uuid.uuid4()),  # document_versions의 ID
            "ai_cost_krw": 130  # GPT-4o 수정 비용 ₩130/회
        }).eq("id", revision_usage_id).execute()

        logger.info(f"Revision completed successfully: {revision_usage_id}")
        logger.info(f"New version: {next_version}")

    except Exception as e:
        logger.error(f"Revision background task failed for {revision_usage_id}: {str(e)}")

        # 실패 상태로 업데이트
        supabase.table("revision_usage").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", revision_usage_id).execute()


@router.post("/payment-complete")
async def handle_payment_complete(
    payment_id: str,
    user_id: str,
    tier: str,
    amount: int,
    announcement_id: str
):
    """
    결제 완료 처리 (PortOne Webhook → FastAPI)

    Args:
        payment_id: PortOne 결제 ID
        user_id: 사용자 ID
        tier: 선택한 티어 (basic, standard, premium)
        amount: 결제 금액 (원)
        announcement_id: 공고 ID

    Returns:
        성공 여부, 생성된 수정권 정보
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        logger.info(f"Processing payment completion for user {user_id}, tier {tier}")

        # 1. 티어별 수정권 개수 결정
        tier_credits_map = {
            "basic": 2,
            "standard": 3,
            "premium": 4
        }

        tier_credits = tier_credits_map.get(tier, 0)

        if tier_credits == 0:
            raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")

        # 2. revision_credits 테이블에 레코드 생성 또는 업데이트
        # 기존 레코드 확인
        existing_credits = supabase.table("revision_credits").select("*").eq(
            "user_id", user_id
        ).execute()

        if not existing_credits.data or len(existing_credits.data) == 0:
            # 새 레코드 생성
            logger.info(f"Creating new revision_credits record for user {user_id}")
            supabase.table("revision_credits").insert({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "current_tier": tier,
                "tier_granted_at": datetime.now().isoformat(),
                "tier_credits_total": tier_credits,
                "tier_credits_used": 0,
                "purchased_credits_total": 0,
                "purchased_credits_used": 0
            }).execute()
        else:
            # 기존 레코드 업데이트 (티어 변경 시)
            logger.info(f"Updating existing revision_credits for user {user_id}")
            current_record = existing_credits.data[0]

            # 티어 업그레이드인 경우에만 수정권 갱신
            # (다운그레이드 방지 - 현재 티어보다 높은 티어로만 변경 가능)
            tier_priority = {"basic": 1, "standard": 2, "premium": 3}
            current_tier_priority = tier_priority.get(current_record.get("current_tier"), 0)
            new_tier_priority = tier_priority.get(tier, 0)

            if new_tier_priority >= current_tier_priority:
                supabase.table("revision_credits").update({
                    "current_tier": tier,
                    "tier_granted_at": datetime.now().isoformat(),
                    "tier_credits_total": tier_credits,
                    "tier_credits_used": 0  # 신규 결제 시 사용 횟수 리셋
                }).eq("user_id", user_id).execute()
                logger.info(f"Tier upgraded from {current_record.get('current_tier')} to {tier}")
            else:
                logger.warning(f"Tier downgrade attempted ({current_record.get('current_tier')} -> {tier}), keeping current tier")

        # 3. 최종 잔액 조회
        final_balance = supabase.table("revision_credits").select(
            "current_tier, tier_credits_available, purchased_credits_available, total_available"
        ).eq("user_id", user_id).execute()

        balance_info = final_balance.data[0] if final_balance.data else {
            "current_tier": tier,
            "tier_credits_available": tier_credits,
            "purchased_credits_available": 0,
            "total_available": tier_credits
        }

        logger.info(f"Payment completed successfully. User {user_id} now has {balance_info['total_available']} revision credits")

        return {
            "success": True,
            "message": f"{tier} 티어 결제가 완료되었습니다. 수정권 {tier_credits}개가 부여되었습니다.",
            "credits": {
                "tier_credits": tier_credits,
                "total_available": balance_info["total_available"]
            },
            "tier": tier,
            "payment_id": payment_id,
            "announcement_id": announcement_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process payment completion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get-profile")
async def get_user_profile(user_id: Optional[int] = 10):
    """
    저장된 사용자 프로필 조회

    Returns:
        - success: bool
        - has_profile: bool
        - profile: dict (회사 정보)
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        # user_profiles 테이블에서 조회
        result = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()

        if not result.data or len(result.data) == 0:
            return {
                "success": True,
                "has_profile": False,
                "profile": None
            }

        profile = result.data[0]

        return {
            "success": True,
            "has_profile": True,
            "profile": {
                "company_name": profile.get("company_name"),
                "business_field": profile.get("industry"),
                "founding_year": profile.get("establishment_year"),
                "employee_count": profile.get("employee_count"),
                "revenue": profile.get("annual_revenue"),
                "main_products": profile.get("main_products"),
                "target_goal": profile.get("target_goal"),
                "technology": profile.get("technology"),
                "past_support": profile.get("past_support"),
                "additional_info": profile.get("additional_info"),
                "business_registration_number": profile.get("business_number")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 피드백 기반 실시간 수정 API
# ============================================================================

@router.post("/revise-with-feedback", response_model=FeedbackReviseResponse)
async def revise_with_feedback(request: FeedbackReviseRequest) -> FeedbackReviseResponse:
    """
    피드백 기반 신청서 수정

    사용자가 제출한 피드백을 반영하여 신청서를 수정합니다.
    수정권 차감 없이 실시간으로 수정됩니다 (티어별 수정 횟수 내에서).

    Args:
        request: 피드백 수정 요청 (current_content, feedback, tier 등)

    Returns:
        수정된 신청서 컨텐츠
    """
    try:
        if not openai_service:
            raise HTTPException(status_code=500, detail="OpenAI service not available")

        logger.info(f"[FeedbackRevise] 수정 요청: {request.announcement_id}")
        logger.info(f"[FeedbackRevise] 피드백: {request.feedback[:100]}...")
        logger.info(f"[FeedbackRevise] 수정 횟수: {request.revision_number}")

        # 현재 컨텐츠를 텍스트로 변환
        current_text = ""
        for section in request.current_content.sections:
            current_text += f"## {section.title}\n\n{section.content}\n\n---\n\n"

        # 피드백 반영 프롬프트
        revision_prompt = f"""당신은 정부지원사업 신청서 전문 작성자입니다.

아래 신청서를 사용자의 피드백에 맞게 수정해주세요.

## 현재 신청서

{current_text}

## 사용자 피드백

{request.feedback}

## 수정 지침

1. 사용자의 피드백을 정확히 반영하세요.
2. 피드백에서 언급한 부분만 수정하고, 나머지는 유지하세요.
3. 전체적인 일관성을 유지하세요.
4. 정부지원사업 신청서의 전문적인 톤을 유지하세요.

## 출력 형식

다음 JSON 형식으로 반환하세요:

```json
{{
  "sections": [
    {{"title": "섹션 제목", "content": "수정된 내용"}},
    ...
  ],
  "changes_summary": "주요 수정 사항 요약 (2-3문장)"
}}
```

반드시 유효한 JSON만 출력하세요.
"""

        # OpenAI API 호출
        try:
            revised_result = await openai_service.generate_application_async(
                prompt=revision_prompt,
                tier=request.tier,
                style="balanced"
            )

            # JSON 파싱
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', revised_result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 코드 블록 없이 JSON이 직접 반환된 경우
                json_str = revised_result.strip()

            revised_data = json.loads(json_str)

            # 응답 구성
            revised_sections = [
                ApplicationSection(title=s.get("title", ""), content=s.get("content", ""))
                for s in revised_data.get("sections", [])
            ]

            revised_content = ApplicationContentModel(
                sections=revised_sections,
                plain_text="\n\n".join([f"## {s.title}\n\n{s.content}" for s in revised_sections])
            )

            logger.info(f"[FeedbackRevise] 수정 완료: {len(revised_sections)}개 섹션")

            return FeedbackReviseResponse(
                success=True,
                revised_content=revised_content,
                revision_number=request.revision_number,
                changes_summary=revised_data.get("changes_summary", "수정이 완료되었습니다.")
            )

        except json.JSONDecodeError as e:
            logger.error(f"[FeedbackRevise] JSON 파싱 실패: {str(e)}")
            # JSON 파싱 실패 시 원본 유지하면서 에러 반환
            return FeedbackReviseResponse(
                success=False,
                revised_content=request.current_content,
                revision_number=request.revision_number,
                error="수정 결과 파싱에 실패했습니다. 다시 시도해주세요."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FeedbackRevise] 수정 실패: {str(e)}")
        return FeedbackReviseResponse(
            success=False,
            revised_content=request.current_content,
            revision_number=request.revision_number,
            error=str(e)
        )
