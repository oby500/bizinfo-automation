#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
북마크 Pydantic 모델
"""

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class BookmarkCreate(BaseModel):
    """북마크 생성 요청 모델"""
    announcement_id: str = Field(..., description="공고 ID (예: KS_175399, PBLN_000000000116027)")
    announcement_source: Literal["kstartup", "bizinfo"] = Field(..., description="공고 출처")

    class Config:
        json_schema_extra = {
            "example": {
                "announcement_id": "KS_175399",
                "announcement_source": "kstartup"
            }
        }


class BookmarkResponse(BaseModel):
    """북마크 응답 모델"""
    id: str = Field(..., description="북마크 고유 ID")
    user_id: str = Field(..., description="사용자 ID")
    announcement_id: str = Field(..., description="공고 ID")
    announcement_source: str = Field(..., description="공고 출처 (kstartup/bizinfo)")
    created_at: datetime = Field(..., description="북마크 생성 시각")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "announcement_id": "KS_175399",
                "announcement_source": "kstartup",
                "created_at": "2025-11-10T12:00:00Z"
            }
        }


class BookmarkDeleteResponse(BaseModel):
    """북마크 삭제 응답 모델"""
    message: str = Field(..., description="삭제 결과 메시지")
    deleted_id: str = Field(..., description="삭제된 북마크 ID")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "북마크가 삭제되었습니다",
                "deleted_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class BookmarkListResponse(BaseModel):
    """북마크 목록 응답 모델"""
    bookmarks: list[BookmarkResponse] = Field(..., description="북마크 목록")
    total: int = Field(..., description="전체 북마크 개수")
    page: int = Field(..., description="현재 페이지")
    page_size: int = Field(..., description="페이지 크기")

    class Config:
        json_schema_extra = {
            "example": {
                "bookmarks": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "announcement_id": "KS_175399",
                        "announcement_source": "kstartup",
                        "created_at": "2025-11-10T12:00:00Z"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20
            }
        }
