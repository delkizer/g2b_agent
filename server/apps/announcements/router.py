"""공고 라우터 — 6개 엔드포인트

선언 순서 중요:
  1. POST /batch        (배치 등록)
  2. GET  /stats        (통계 — {id}보다 먼저)
  3. GET  /export       (내보내기 — {id}보다 먼저)
  4. GET  /             (목록)
  5. GET  /{id}         (상세)
  6. PATCH /{id}/status (상태 변경)
"""

from typing import Optional

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from apps.announcements.schemas import (
    AnnouncementBatchRequest,
    AnnouncementBatchResponse,
    AnnouncementDetailResponse,
    AnnouncementListResponse,
    AnnouncementStatsResponse,
    FilterParams,
    StatusUpdateRequest,
    StatusUpdateResponse,
)
from apps.dependencies import verify_api_key
from apps.exceptions import AppException
from database.connection import get_session
from services.announcement_service import AnnouncementService

router = APIRouter(prefix="/announcements", tags=["공고"])


# 1. 배치 등록 (POST) ─────────────────────────────────────

@router.post(
    "/batch",
    response_model=AnnouncementBatchResponse,
    dependencies=[Depends(verify_api_key)],
)
async def create_batch(
    body: AnnouncementBatchRequest,
    session: AsyncSession = Depends(get_session),
):
    """에이전트가 수집/분석한 공고를 일괄 등록 (upsert)"""
    service = AnnouncementService()
    items = [item.model_dump(exclude_none=True) for item in body.announcements]

    try:
        result = await service.create_batch(session, items)
    except Exception as e:
        logger.error(f"배치 처리 중 DB 오류: {e}")
        raise AppException(
            status_code=503,
            detail="데이터베이스 연결에 실패했습니다",
            error_code="DATABASE_ERROR",
        )

    return result


# 2. 통계 조회 (GET) — {id}보다 먼저 선언 ─────────────────

@router.get("/stats", response_model=AnnouncementStatsResponse)
async def get_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """카테고리별, 점수구간별, 상태별, 월별 트렌드 통계"""
    service = AnnouncementService()
    try:
        return await service.get_stats(session, date_from, date_to)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"통계 조회 중 DB 오류: {e}")
        raise AppException(
            status_code=503,
            detail="데이터베이스 연결에 실패했습니다",
            error_code="DATABASE_ERROR",
        )


# 3. 내보내기 (GET) — {id}보다 먼저 선언 ──────────────────

@router.get("/export")
async def export_list(
    format: str = "csv",
    filters: FilterParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """공고 목록을 CSV 또는 Excel로 내보내기"""
    service = AnnouncementService()
    try:
        return await service.export_list(session, filters, format)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"내보내기 중 DB 오류: {e}")
        raise AppException(
            status_code=503,
            detail="데이터베이스 연결에 실패했습니다",
            error_code="DATABASE_ERROR",
        )


# 4. 목록 조회 (GET) ──────────────────────────────────────

@router.get("", response_model=AnnouncementListResponse)
async def get_list(
    filters: FilterParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """공고 목록 조회 (필터 + 정렬 + 페이징)"""
    service = AnnouncementService()
    try:
        return await service.get_list(session, filters)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"목록 조회 중 DB 오류: {e}")
        raise AppException(
            status_code=503,
            detail="데이터베이스 연결에 실패했습니다",
            error_code="DATABASE_ERROR",
        )


# 5. 상세 조회 (GET) — 동적 경로 ──────────────────────────

@router.get("/{id}", response_model=AnnouncementDetailResponse)
async def get_detail(
    id: int,
    session: AsyncSession = Depends(get_session),
):
    """공고 상세 정보 조회"""
    service = AnnouncementService()
    try:
        return await service.get_detail(session, id)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"상세 조회 중 DB 오류: {e}")
        raise AppException(
            status_code=503,
            detail="데이터베이스 연결에 실패했습니다",
            error_code="DATABASE_ERROR",
        )


# 6. 상태 변경 (PATCH) ────────────────────────────────────

@router.patch("/{id}/status", response_model=StatusUpdateResponse)
async def update_status(
    id: int,
    body: StatusUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """공고 상태 수동 변경"""
    service = AnnouncementService()
    try:
        return await service.update_status(session, id, body.status)
    except AppException:
        raise
    except Exception as e:
        logger.error(f"상태 변경 중 DB 오류: {e}")
        raise AppException(
            status_code=503,
            detail="데이터베이스 연결에 실패했습니다",
            error_code="DATABASE_ERROR",
        )
