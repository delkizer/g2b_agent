"""공고 관련 Pydantic 스키마"""

from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field, field_validator


# ── 배치 전송 ────────────────────────────────────────────

ALLOWED_STATUSES = {"pending", "analyzed", "reviewing", "bidding", "excluded", "archived"}


class AnalyzedAnnouncementItem(BaseModel):
    """에이전트가 전송하는 분석 완료 공고 1건"""

    # 원본 데이터 (나라장터)
    bid_notice_no: str = Field(..., description="입찰공고번호 (고유키)", max_length=50)
    bid_notice_nm: str = Field(..., description="공고명")
    ntce_instt_nm: Optional[str] = Field(None, description="공고기관명", max_length=200)
    dminstt_nm: Optional[str] = Field(None, description="수요기관명", max_length=200)
    presmpt_price: Optional[int] = Field(None, description="추정가격 (원)", ge=0)
    bid_begin_dt: Optional[datetime] = Field(None, description="입찰개시일시")
    bid_close_dt: Optional[datetime] = Field(None, description="입찰마감일시")
    link_url: Optional[str] = Field(None, description="나라장터 원문 링크")
    raw_data: Optional[dict] = Field(None, description="나라장터 원본 JSON")

    # v2: 첨부파일 URL
    attachment_urls: Optional[list[str]] = Field(None, description="첨부파일 URL 목록")

    # 분석 결과 (v2: optional — Cowork가 PATCH로 채움)
    category: Optional[str] = Field(None, description="분류")
    relevance_score: Optional[int] = Field(None, description="적합성 점수", ge=0, le=100)
    summary: Optional[str] = Field(None, description="사업 요약")
    requirements: Optional[str] = Field(None, description="참가자격 요약")
    needs_research_lab: Optional[bool] = Field(None, description="기업부설연구소 필요 여부")
    analysis_detail: Optional[dict] = Field(None, description="Claude 상세 분석 결과")

    # 시스템
    collected_at: Optional[datetime] = Field(None, description="수집 시각")
    analyzed_at: Optional[datetime] = Field(None, description="분석 완료 시각")


class AnnouncementBatchRequest(BaseModel):
    """공고 일괄 등록 요청"""
    announcements: list[AnalyzedAnnouncementItem] = Field(
        ..., description="분석 완료 공고 목록", min_length=1
    )


# ── 배치 응답 ────────────────────────────────────────────

class BatchErrorItem(BaseModel):
    """배치 처리 중 개별 실패 건"""
    bid_notice_no: str = Field(..., description="실패한 공고번호")
    error: str = Field(..., description="에러 메시지")


class AnnouncementBatchResponse(BaseModel):
    """공고 일괄 등록 응답"""
    received: int = Field(..., description="수신한 공고 총 건수")
    created: int = Field(..., description="신규 생성된 건수")
    updated: int = Field(..., description="업데이트된 건수")
    errors: list[BatchErrorItem] = Field(
        default_factory=list, description="개별 처리 실패 건 목록"
    )


# ── 목록 조회 ────────────────────────────────────────────

class AnnouncementListItem(BaseModel):
    """공고 목록 조회 응답 -- 경량 필드"""
    id: int
    bid_notice_no: str
    bid_notice_nm: str
    ntce_instt_nm: Optional[str] = None
    dminstt_nm: Optional[str] = None
    category: Optional[str] = None
    relevance_score: int = 0
    summary: Optional[str] = None
    presmpt_price: Optional[int] = None
    bid_begin_dt: Optional[datetime] = None
    bid_close_dt: Optional[datetime] = None
    contract_method: Optional[str] = None
    openg_dt: Optional[datetime] = None
    status: str = "pending"
    needs_research_lab: bool = False
    key_factors: Optional[list[str]] = None
    risks: Optional[list[str]] = None
    collected_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    """공고 목록 조회 응답 (페이징 포함)"""
    items: list[AnnouncementListItem]
    total: int = Field(..., description="전체 건수")
    page: int = Field(..., description="현재 페이지")
    size: int = Field(..., description="페이지당 건수")
    pages: int = Field(..., description="전체 페이지 수")


# ── 상세 조회 ────────────────────────────────────────────

class AnnouncementDetailResponse(BaseModel):
    """공고 상세 조회 응답 -- 전체 필드"""
    id: int
    bid_notice_no: str
    bid_notice_nm: str
    ntce_instt_nm: Optional[str] = None
    dminstt_nm: Optional[str] = None
    presmpt_price: Optional[int] = None
    bid_begin_dt: Optional[datetime] = None
    bid_close_dt: Optional[datetime] = None
    contract_method: Optional[str] = None
    openg_dt: Optional[datetime] = None
    link_url: Optional[str] = None
    raw_data: Optional[dict] = None
    attachment_urls: Optional[list[str]] = None

    category: Optional[str] = None
    relevance_score: int = 0
    summary: Optional[str] = None
    requirements: Optional[str] = None
    needs_research_lab: bool = False
    analysis_detail: Optional[dict] = None

    status: str = "pending"
    notion_page_id: Optional[str] = None
    collected_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 통계 ─────────────────────────────────────────────────

class MonthlyTrendItem(BaseModel):
    """월별 트렌드 데이터"""
    month: str = Field(..., description="연월 (YYYY-MM)")
    count: int = Field(..., description="공고 건수")
    avg_score: float = Field(..., description="평균 점수")
    total_budget: int = Field(..., description="예산 합계 (원)")


class AnnouncementStatsResponse(BaseModel):
    """공고 통계 응답"""
    total_count: int = Field(..., description="전체 건수")
    by_category: dict[str, int] = Field(..., description="카테고리별 건수")
    by_score_range: dict[str, int] = Field(..., description="점수 구간별 건수")
    by_status: dict[str, int] = Field(..., description="상태별 건수")
    avg_score: float = Field(..., description="평균 적합성 점수")
    total_budget: int = Field(..., description="총 추정가격 합계 (원)")
    trend: list[MonthlyTrendItem] = Field(..., description="월별 트렌드")


# ── 필터 파라미터 ────────────────────────────────────────

class SortField(str, Enum):
    bid_begin_dt = "bid_begin_dt"
    relevance_score = "relevance_score"
    bid_close_dt = "bid_close_dt"
    collected_at = "collected_at"
    presmpt_price = "presmpt_price"
    created_at = "created_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class FilterParams(BaseModel):
    """공고 목록 조회 필터 파라미터"""
    category: Optional[str] = Query(
        None, description="카테고리 필터 (콤마 구분, 예: 스포츠,AI/데이터)"
    )
    min_score: Optional[int] = Query(
        None, description="최소 적합성 점수 (0-100)", ge=0, le=100
    )
    status: Optional[str] = Query(None, description="상태 필터")
    date_from: Optional[str] = Query(None, description="수집일 시작 (YYYY-MM-DD)")
    date_to: Optional[str] = Query(None, description="수집일 종료 (YYYY-MM-DD)")
    search: Optional[str] = Query(
        None, description="텍스트 검색 (공고명, 요약)", max_length=200
    )
    deadline: Optional[str] = Query(
        None, description="마감 여부 필터 (active=진행중, closed=마감)"
    )

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v):
        if v is not None and v not in ("active", "closed"):
            raise ValueError(f"deadline 값이 유효하지 않습니다: '{v}' (active 또는 closed)")
        return v
    sort: SortField = Query(SortField.bid_begin_dt, description="정렬 기준")
    order: SortOrder = Query(SortOrder.desc, description="정렬 방향")
    page: int = Query(1, description="페이지 번호", ge=1)
    size: int = Query(20, description="페이지당 건수", ge=1, le=100)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ALLOWED_STATUSES:
            raise ValueError(f"status 값이 유효하지 않습니다: '{v}'")
        return v

    def get_category_list(self) -> Optional[list[str]]:
        """콤마 구분 category 문자열을 리스트로 변환"""
        if self.category is None:
            return None
        return [c.strip() for c in self.category.split(",") if c.strip()]


# ── 분석 결과 업데이트 (v2: Cowork MCP PATCH) ───────────

class AnalysisResultUpdate(BaseModel):
    """Cowork가 MCP를 통해 분석 결과를 저장할 때 사용하는 스키마"""
    category: str = Field(..., description="분류")
    relevance_score: int = Field(..., description="적합성 점수", ge=0, le=100)
    summary: str = Field(..., description="사업 요약")
    requirements: Optional[str] = Field(None, description="참가자격 요약")
    needs_research_lab: Optional[bool] = Field(None, description="기업부설연구소 필요 여부")
    analysis_detail: Optional[dict] = Field(None, description="상세 분석 결과")


class AnalysisResultResponse(BaseModel):
    """분석 결과 저장 응답"""
    id: int
    bid_notice_no: str
    status: str
    relevance_score: int
    analyzed_at: datetime


# ── 상태 변경 ────────────────────────────────────────────

class StatusUpdateRequest(BaseModel):
    """공고 상태 변경 요청"""
    status: str = Field(..., description="변경할 상태 값")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in ALLOWED_STATUSES:
            raise ValueError(f"status 값이 유효하지 않습니다: '{v}'")
        return v


class StatusUpdateResponse(BaseModel):
    """공고 상태 변경 응답"""
    id: int
    bid_notice_no: str
    status: str
    updated_at: datetime


# ── 헬스체크 ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    """서비스 상태 응답"""
    status: str = Field(..., description="서비스 상태 (healthy/unhealthy)")
    database: str = Field(..., description="DB 연결 상태 (connected/disconnected)")
    timestamp: datetime = Field(..., description="응답 시각")


# ── 에러 ─────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """공통 에러 응답"""
    detail: str = Field(..., description="에러 설명")
    error_code: str = Field(..., description="머신 판독용 에러 코드")
