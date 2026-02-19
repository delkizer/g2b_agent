"""나라장터 공고 SQLAlchemy 모델"""

from sqlalchemy import (
    Column, Integer, BigInteger, SmallInteger, String, Text, Boolean,
    DateTime, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Announcement(Base):
    """나라장터 공고 + Claude 분석 결과 통합 모델"""

    __tablename__ = "announcements"

    # ── PK / 비즈니스 키 ──────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    bid_notice_no = Column(String(50), unique=True, nullable=False,
                           comment="입찰공고번호 (upsert 기준)")

    # ── 원본 데이터 (나라장터 API) ────────────────────────
    bid_notice_nm = Column(Text, nullable=False, comment="공고명")
    ntce_instt_nm = Column(String(200), comment="공고기관명")
    dminstt_nm = Column(String(200), comment="수요기관명")
    presmpt_price = Column(BigInteger, comment="추정가격 (원)")
    bid_begin_dt = Column(DateTime(timezone=True), comment="입찰개시일시")
    bid_close_dt = Column(DateTime(timezone=True), comment="입찰마감일시")
    link_url = Column(Text, comment="나라장터 원문 링크")
    raw_data = Column(JSONB, comment="나라장터 원본 JSON")

    # ── 분석 결과 (Claude API) ────────────────────────────
    category = Column(String(50), comment="분류")
    relevance_score = Column(SmallInteger, nullable=False, default=0,
                             server_default="0",
                             comment="SPOTV 적합성 점수 (0-100)")
    summary = Column(Text, comment="사업 요약")
    requirements = Column(Text, comment="참가자격 요약")
    needs_research_lab = Column(Boolean, nullable=False, default=False,
                                server_default="false",
                                comment="기업부설연구소 필요 여부")
    analysis_detail = Column(JSONB, comment="Claude 상세 분석 결과")

    # ── 시스템 ────────────────────────────────────────────
    status = Column(String(20), nullable=False, default="pending",
                    server_default="pending",
                    comment="공고 상태")
    notion_page_id = Column(String(100), comment="Notion 페이지 ID")
    collected_at = Column(DateTime(timezone=True), comment="수집 시각")
    analyzed_at = Column(DateTime(timezone=True), comment="분석 완료 시각")
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=text("NOW()"), comment="생성 시각")
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=text("NOW()"), comment="최종 갱신 시각")

    # ── 테이블 수준 제약조건 + 인덱스 ─────────────────────
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100",
            name="ck_announcements_relevance_score",
        ),
        CheckConstraint(
            "status IN ('pending', 'analyzed', 'reviewing', 'bidding', 'excluded', 'archived')",
            name="ck_announcements_status",
        ),
        CheckConstraint(
            "category IS NULL OR category IN ('스포츠', '영상분석', 'AI/데이터', '미디어', '플랫폼', '기타')",
            name="ck_announcements_category",
        ),
        Index("idx_announcements_category", "category"),
        Index("idx_announcements_score", relevance_score.desc()),
        Index("idx_announcements_status", "status"),
        Index("idx_announcements_bid_close", "bid_close_dt"),
        Index("idx_announcements_collected", "collected_at"),
        Index("idx_announcements_status_score", "status", relevance_score.desc()),
        {"schema": "g2b"},
    )

    def __repr__(self) -> str:
        return (
            f"<Announcement(id={self.id}, "
            f"bid_notice_no='{self.bid_notice_no}', "
            f"score={self.relevance_score})>"
        )
