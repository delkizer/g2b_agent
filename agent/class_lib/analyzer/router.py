"""Analyzer 도메인 — 단건 공고 분석 엔드포인트

PipelineRunner가 건별로 호출하는 내부 API.
ClaudeClient를 싱글톤으로 유지하여 PromptBuilder의 시스템 프롬프트 캐시를 재사용한다.

참조:
- docs/pipeline/02-internal-api.md §5 : Analyzer 라우터 설계
- docs/analyzer/01-analyzer-overview.md §3.1 : ClaudeClient 인터페이스
"""

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from class_lib.analyzer.claude_client import ClaudeClient


# ---------------------------------------------------------------------------
# Request / Response 모델 (Swagger 문서화용)
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """단건 공고 분석 요청 (collected_announcements 행)"""
    bid_notice_no: str
    bid_notice_nm: str
    ntce_instt_nm: str = ""
    dminstt_nm: str = ""
    presmpt_price: int = 0
    bid_begin_dt: str | None = None
    bid_close_dt: str | None = None
    link_url: str = ""
    raw_data: dict = Field(default_factory=dict)
    collected_at: str | None = None
    filter_meta: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class AnalysisDimension(BaseModel):
    score: int
    reason: str


class AnalysisDetail(BaseModel):
    dimensions: dict[str, AnalysisDimension] = Field(default_factory=dict)
    key_factors: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class AnalyzeResponse(BaseModel):
    """분석 성공 응답"""
    category: str
    relevance_score: int
    summary: str
    requirements: str = ""
    needs_research_lab: bool = False
    analysis_detail: AnalysisDetail | None = None

    model_config = ConfigDict(extra="allow")


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str


router = APIRouter()

# 싱글톤 (프롬프트 템플릿 캐싱 유지)
_client: ClaudeClient | None = None


def _get_client() -> ClaudeClient:
    global _client
    if _client is None:
        _client = ClaudeClient()
    return _client


@router.post(
    "/analyze",
    summary="단건 공고 분석",
    description="PipelineRunner가 건별로 호출하는 내부 API. "
                "ClaudeClient를 통해 Claude API로 분석 수행.",
    responses={
        200: {
            "description": "분석 성공 또는 실패",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "분석 성공",
                            "value": {
                                "category": "스포츠",
                                "relevance_score": 87,
                                "summary": "프로스포츠 경기 데이터 분석 플랫폼 구축 사업",
                                "requirements": "기업부설연구소 보유",
                                "needs_research_lab": True,
                                "analysis_detail": {},
                            },
                        },
                        "error": {
                            "summary": "분석 실패",
                            "value": {"status": "error", "message": "분석 실패"},
                        },
                    }
                }
            },
        }
    },
)
async def analyze_announcement(body: AnalyzeRequest):
    """단건 공고 분석 (Claude API)"""
    announcement = body.model_dump()
    bid_notice_no = body.bid_notice_no

    client = _get_client()
    result = await client.analyze_announcement(announcement)

    if not result:
        logger.warning(f"분석 실패: [{bid_notice_no}]")
        return {"status": "error", "message": "분석 실패"}

    return result
