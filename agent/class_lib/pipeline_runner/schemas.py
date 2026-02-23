"""Pipeline 도메인 — Pydantic 스키마

라우터 요청/응답 모델 + 내부 DTO.
router.py, pipeline_runner.py 에서 import.

참조:
- docs/pipeline/02-internal-api.md §4 : Pipeline 라우터 설계
"""

from pydantic import BaseModel, Field


# ── /pipeline/run ──────────────────────────────────────


class PipelineRunRequest(BaseModel):
    """파이프라인 트리거 요청

    announcements에 FilteredAnnouncement 리스트를 포함한다.
    빈 리스트이면 저장 없이 워커만 기동 (기존 collected 건 처리).
    """
    announcements: list[dict] = Field(
        default_factory=list,
        description="FilteredAnnouncement 리스트 (빈 리스트 시 워커만 기동)",
    )


class PipelineRunResponse(BaseModel):
    """파이프라인 트리거 응답 (즉시 반환)"""
    status: str = Field(description="accepted / skipped / error")
    saved: int = 0
    skipped: int = 0
    reason: str | None = None
    message: str | None = None


# ── /pipeline/send ─────────────────────────────────────


class PipelineSendRequest(BaseModel):
    """EC2 전송 요청

    bid_notice_nos에 전송 대상 공고번호 리스트를 포함.
    빈 리스트 또는 생략 시 analyzed 전체 배치 전송.
    """
    bid_notice_nos: list[str] = Field(
        default_factory=list,
        description="전송 대상 공고번호 (빈 리스트 시 analyzed 전체)",
    )


class SendError(BaseModel):
    """전송 실패 건 상세"""
    bid_notice_no: str
    error: str


class PipelineSendResponse(BaseModel):
    """EC2 전송 응답"""
    status: str = Field(description="completed / no_items / error")
    sent: int = 0
    failed: int = 0
    errors: list[SendError] = Field(default_factory=list)
    message: str | None = None
