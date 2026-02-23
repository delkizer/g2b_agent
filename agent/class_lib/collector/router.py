"""Collector 도메인 — 수동 수집 트리거 엔드포인트

외부에서 수집을 강제 실행할 때 사용하는 내부 API.
app.state.scheduler에서 기존 CollectorScheduler 인스턴스를 사용하여
중복 생성 없이 collect_and_filter()를 호출한다.

호출 흐름:
    POST /api/internal/collector/run
      → scheduler.collect_and_filter()
        → fetch + filter + _signal_pipeline() (자동)

참조:
- docs/collector/01-collector-overview.md : CollectorScheduler 설계
- docs/pipeline/02-internal-api.md : 내부 API 전체 구조
"""

from fastapi import APIRouter, Request
from loguru import logger
from pydantic import BaseModel


class CollectorRunResponse(BaseModel):
    status: str
    filtered_count: int | None = None
    message: str | None = None


router = APIRouter()


@router.post(
    "/run",
    summary="수동 수집 트리거",
    description="app.state.scheduler의 collect_and_filter()를 1회 실행한다. "
                "내부에서 _signal_pipeline()이 자동 호출되어 파이프라인까지 연쇄 실행된다.",
    response_model=CollectorRunResponse,
)
async def run_collect(request: Request):
    """수동 수집 트리거

    app.state.scheduler의 collect_and_filter()를 1회 실행한다.
    내부에서 _signal_pipeline()이 자동 호출되어 파이프라인까지 연쇄 실행된다.

    Returns:
        {"status": "completed", "filtered_count": N}
        {"status": "error", "message": "..."}
    """
    scheduler = getattr(request.app.state, "scheduler", None)

    if scheduler is None:
        logger.error("CollectorScheduler가 초기화되지 않음")
        return {"status": "error", "message": "scheduler not initialized"}

    try:
        filtered = await scheduler.collect_and_filter()
        return {
            "status": "completed",
            "filtered_count": len(filtered),
        }
    except Exception as e:
        logger.error(f"수동 수집 실행 예외: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
