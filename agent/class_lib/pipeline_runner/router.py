"""Pipeline 도메인 — 파이프라인 API 엔드포인트

/pipeline/run      — Collector가 호출 (트리거 + 저장, 즉시 응답)
/pipeline/send     — 워커/수동 호출 (로컬 저장)
/pipeline/sync-ec2 — 로컬 → EC2 동기화

PipelineRunner를 싱글톤으로 유지하여 _running 플래그가 요청 간 공유되도록 한다.

참조:
- docs/pipeline/02-internal-api.md §4 : Pipeline 라우터 설계
- docs/pipeline/01-pipeline-overview.md §6 : PipelineRunner 클래스 설계
"""

from fastapi import APIRouter
from loguru import logger

from class_lib.pipeline_runner.pipeline_runner import PipelineRunner
from class_lib.pipeline_runner.schemas import (
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineSendRequest,
    PipelineSendResponse,
    PipelineSyncRequest,
    PipelineSyncResponse,
)


router = APIRouter()

# 싱글톤 인스턴스 (워커 실행 플래그 유지를 위해)
_runner: PipelineRunner | None = None


def _get_runner() -> PipelineRunner:
    global _runner
    if _runner is None:
        _runner = PipelineRunner()
    return _runner


@router.post(
    "/run",
    summary="파이프라인 트리거 (비동기)",
    description="Collector가 수집 + 필터 완료 후 호출. "
                "DB 저장만 수행하고 즉시 응답. "
                "백그라운드 워커가 분석/전송을 비동기 처리한다.",
    response_model=PipelineRunResponse,
)
async def run_pipeline(body: PipelineRunRequest | None = None):
    """트리거: 저장 + 백그라운드 워커 기동"""
    runner = _get_runner()
    announcements = body.announcements if body else []

    try:
        result = await runner.run(announcements=announcements)
        return result
    except Exception as e:
        logger.error(f"파이프라인 트리거 예외: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post(
    "/send",
    summary="EC2 전송 (독립 API)",
    description="analyzed 상태 건을 EC2 서버로 전송. "
                "워커 또는 수동으로 호출. "
                "bid_notice_nos 지정 시 해당 건만, 미지정 시 analyzed 전체.",
    response_model=PipelineSendResponse,
)
async def send_to_ec2(body: PipelineSendRequest | None = None):
    """collected 건 로컬 저장"""
    runner = _get_runner()
    bid_notice_nos = body.bid_notice_nos if body else []

    try:
        result = await runner.send(bid_notice_nos=bid_notice_nos)
        return result
    except Exception as e:
        logger.error(f"로컬 저장 예외: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post(
    "/sync-ec2",
    summary="로컬 → EC2 동기화",
    description="로컬 g2b.announcements 테이블의 미동기화 또는 갱신된 공고를 "
                "EC2 서버로 동기화. limit으로 최대 건수 지정 (기본 500).",
    response_model=PipelineSyncResponse,
)
async def sync_to_ec2(body: PipelineSyncRequest | None = None):
    """로컬 → EC2 동기화"""
    runner = _get_runner()
    limit = body.limit if body else 500

    try:
        result = await runner.sync_ec2(limit=limit)
        return result
    except Exception as e:
        logger.error(f"EC2 동기화 예외: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
