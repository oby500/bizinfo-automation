# models/application.py
"""
신청서 작성 시스템 Pydantic 모델

Development guide 기준 데이터 구조 정의
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class TierEnum(str, Enum):
    """티어 (가격 플랜)"""
    basic = "basic"
    standard = "standard"
    premium = "premium"


class StyleEnum(str, Enum):
    """신청서 작성 스타일"""
    data = "data"  # 데이터 중심형
    story = "story"  # 스토리 중심형
    balanced = "balanced"  # 균형형
    aggressive = "aggressive"  # 공격형 (혁신 강조)
    conservative = "conservative"  # 안정형 (신뢰 강조)


class ApplicationStatusEnum(str, Enum):
    """신청서 생성 상태"""
    pending = "pending"  # 대기 중
    processing = "processing"  # 생성 중
    completed = "completed"  # 완료
    failed = "failed"  # 실패


# ============================================================================
# Z (회사 정보) 모델
# ============================================================================

class CompanyBasicInfo(BaseModel):
    """회사 기본 정보"""
    상호: str = Field(..., min_length=1, max_length=200, description="회사명")
    대표자: Optional[str] = Field(None, max_length=100, description="대표자명")
    사업자번호: str = Field(..., pattern=r'^\d{3}-\d{2}-\d{5}$', description="사업자등록번호")
    설립일: date = Field(..., description="설립일 (YYYY-MM-DD)")
    직원수: int = Field(..., gt=0, description="직원 수")
    주소: Optional[str] = Field(None, max_length=500)
    업종: str = Field(..., min_length=1, max_length=200)
    홈페이지: Optional[str] = Field(None, description="회사 홈페이지 URL")


class Patent(BaseModel):
    """특허 정보"""
    번호: str = Field(..., description="특허 번호")
    명칭: str = Field(..., description="특허 명칭")
    등록일: date = Field(..., description="특허 등록일")


class Certification(BaseModel):
    """인증 정보"""
    종류: str = Field(..., description="인증 종류 (예: 벤처기업인증, ISO)")
    발급기관: str = Field(..., description="발급 기관")
    유효기간: Optional[str] = Field(None, description="유효 기간 또는 취득일")


class TechCapability(BaseModel):
    """기술력"""
    특허: Optional[List[Patent]] = Field(default_factory=list)
    인증: Optional[List[Certification]] = Field(default_factory=list)
    수상: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    연구개발: Optional[Dict[str, Any]] = Field(None, description="R&D 투자 비율, 연구 인력 등")


class KeyPerson(BaseModel):
    """핵심 인력 정보"""
    직책: str = Field(..., description="직책")
    이름: str = Field(..., description="이름")
    경력: str = Field(..., description="경력 요약")
    주요경력: Optional[List[str]] = Field(default_factory=list, description="상세 경력")


class TeamStructure(BaseModel):
    """팀 구성"""
    핵심인력: Optional[List[KeyPerson]] = Field(default_factory=list)
    조직도: Optional[Dict[str, int]] = Field(None, description="부서별 인원")
    외부협력: Optional[List[Dict[str, str]]] = Field(default_factory=list)


class Revenue(BaseModel):
    """매출 정보"""
    연도: int = Field(..., ge=2000, le=2100)
    매출액: int = Field(..., ge=0, description="매출액 (원)")
    영업이익: Optional[int] = Field(None, description="영업이익 (원)")


class FinancialStatus(BaseModel):
    """재무 현황"""
    최근3년매출: Optional[List[Revenue]] = Field(default_factory=list)
    자본금: Optional[int] = Field(None, ge=0)
    부채비율: Optional[float] = Field(None, ge=0)
    신용등급: Optional[str] = None
    투자유치: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class FundingPlan(BaseModel):
    """자금 계획"""
    총사업비: int = Field(..., gt=0, description="총 사업비 (원)")
    자부담: int = Field(..., ge=0, description="자부담 금액 (원)")
    정부지원_희망액: int = Field(..., gt=0, description="정부 지원 희망액 (원)")
    용도: Dict[str, int] = Field(..., description="용도별 금액 (예: 연구개발, 마케팅)")

    @validator('자부담', '정부지원_희망액')
    def check_funding_sum(cls, v, values):
        """총사업비 = 자부담 + 정부지원_희망액 검증"""
        if '총사업비' in values:
            총사업비 = values['총사업비']
            # 완전 검증은 모든 필드가 있을 때만
            if '자부담' in values and '정부지원_희망액' in values:
                if values['자부담'] + values['정부지원_희망액'] != 총사업비:
                    raise ValueError(f"총사업비({총사업비})는 자부담 + 정부지원_희망액과 같아야 합니다.")
        return v


class BusinessPlan(BaseModel):
    """사업 계획"""
    목표시장: Optional[Dict[str, str]] = Field(None, description="국내/해외 시장")
    경쟁우위: Optional[List[str]] = Field(default_factory=list)
    성장전략: Optional[str] = None
    예상매출: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    자금계획: FundingPlan


class CompanyInfo(BaseModel):
    """Z (회사 정보) 전체 스키마"""
    회사정보: CompanyBasicInfo
    사업내용: Dict[str, Any]  # 주력제품, 기술분야, 사업실적 등
    기술력: Optional[TechCapability] = None
    팀구성: Optional[TeamStructure] = None
    재무현황: Optional[FinancialStatus] = None
    사업계획: BusinessPlan
    차별화요소: Optional[Dict[str, Any]] = None
    제출서류_체크리스트: Optional[Dict[str, List[str]]] = None


# ============================================================================
# API Request/Response 모델
# ============================================================================

class AnalyzeAnnouncementRequest(BaseModel):
    """공고 분석 요청"""
    announcement_id: str = Field(..., description="공고 ID (PBLN_xxx or announcement_id)")
    source: Literal["kstartup", "bizinfo"] = Field(default="kstartup", description="공고 출처")
    force_refresh: bool = Field(default=False, description="캐시 무시하고 재분석")


class AnalyzeAnnouncementResponse(BaseModel):
    """공고 분석 응답"""
    analysis_id: str
    announcement_id: str
    analysis: Dict[str, Any] = Field(..., description="Claude 분석 결과 (자격요건, 평가기준 등)")
    created_at: datetime


class AnalyzeCompanyRequest(BaseModel):
    """회사 분석 요청"""
    announcement_analysis: Dict[str, Any] = Field(..., description="공고 분석 결과")
    company_info: CompanyInfo = Field(..., description="회사 정보 (Z)")


class AnalyzeCompanyResponse(BaseModel):
    """회사 분석 응답"""
    analysis_id: str
    company_analysis: Dict[str, Any] = Field(..., description="Claude 분석 결과 (강점, 약점 등)")
    created_at: datetime


class ComposeApplicationRequest(BaseModel):
    """신청서 생성 요청"""
    announcement_analysis: Dict[str, Any] = Field(..., description="공고 분석 결과")
    company_analysis: Dict[str, Any] = Field(..., description="회사 분석 결과")
    style: StyleEnum = Field(..., description="작성 스타일")
    tier: TierEnum = Field(..., description="선택한 티어")
    user_id: str = Field(..., description="사용자 ID")


class ComposeApplicationResponse(BaseModel):
    """신청서 생성 응답"""
    application_id: str
    status: ApplicationStatusEnum
    message: str


class ApplicationStatusResponse(BaseModel):
    """신청서 상태 응답"""
    application_id: str
    status: ApplicationStatusEnum
    progress: int = Field(..., ge=0, le=100, description="진행률 (0-100)")
    current_step: Optional[str] = Field(None, description="현재 단계 (analyzing, generating 등)")
    documents: Optional[List[Dict[str, Any]]] = Field(None, description="생성된 문서들 (완료 시)")
    error: Optional[str] = Field(None, description="에러 메시지 (실패 시)")


class DownloadApplicationResponse(BaseModel):
    """신청서 다운로드 응답"""
    download_url: str = Field(..., description="다운로드 URL (Supabase Storage)")
    filename: str = Field(..., description="파일명")
    expires_at: datetime = Field(..., description="URL 만료 시간 (24시간)")


# ============================================================================
# Database 모델
# ============================================================================

class ApplicationDB(BaseModel):
    """applications 테이블 모델"""
    id: str
    user_id: str
    order_id: Optional[str] = None
    tier: TierEnum

    # 공고 정보
    announcement_url: Optional[str] = None
    announcement_text: Optional[str] = None
    announcement_analysis: Optional[Dict[str, Any]] = None

    # 회사 정보
    company_info: CompanyInfo
    company_analysis: Optional[Dict[str, Any]] = None

    # 생성된 문서들
    documents: Optional[List[Dict[str, Any]]] = None

    # AI 추천 (Standard, Premium)
    ai_recommendation: Optional[Dict[str, Any]] = None

    # 메타
    status: ApplicationStatusEnum
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class DocumentVersion(BaseModel):
    """document_versions 테이블 모델"""
    id: str
    application_id: str
    version: int = Field(..., ge=1)
    style: StyleEnum
    content: str = Field(..., description="생성된 신청서 텍스트")
    metadata: Optional[Dict[str, Any]] = Field(None, description="글자 수, 표 개수 등")
    created_at: datetime

    class Config:
        orm_mode = True
