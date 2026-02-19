"""헬스체크 라우터"""

from datetime import datetime, timezone

from fastapi import APIRouter

from apps.announcements.schemas import HealthResponse
from database.connection import check_db

router = APIRouter(tags=["시스템"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """서비스 및 데이터베이스 상태 확인"""
    db_ok = await check_db()

    status_code = 200 if db_ok else 503
    response = HealthResponse(
        status="healthy" if db_ok else "unhealthy",
        database="connected" if db_ok else "disconnected",
        timestamp=datetime.now(timezone.utc),
    )

    if not db_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=response.model_dump(mode="json"))

    return response
