"""Pipeline fixture — mock DB 커넥션 + 샘플 데이터"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_conn():
    """asyncpg 커넥션 mock"""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 0")
    conn.fetch = AsyncMock(return_value=[])
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def sample_filtered():
    """Collector에서 수신한 FilteredAnnouncement dict"""
    return {
        "bid_notice_no": "20260216001-00",
        "bid_notice_nm": "스포츠 데이터 분석 플랫폼 구축",
        "ntce_instt_nm": "국민체육진흥공단",
        "dminstt_nm": "대한체육회",
        "presmpt_price": 500_000_000,
        "bid_begin_dt": "2026-02-20T10:00:00",
        "bid_close_dt": "2026-03-10T18:00:00",
        "link_url": "https://www.g2b.go.kr/link/20260216001-00",
        "raw_data": {"bidNtceNo": "20260216001-00"},
        "filter_meta": {"matched_keywords": ["스포츠", "데이터"]},
        "collected_at": "2026-02-16T09:00:00",
    }


@pytest.fixture
def sample_db_row():
    """DB collected_announcements 행 dict (collected 상태)"""
    return {
        "id": 1,
        "bid_notice_no": "20260216001-00",
        "bid_notice_nm": "스포츠 데이터 분석 플랫폼 구축",
        "ntce_instt_nm": "국민체육진흥공단",
        "dminstt_nm": "대한체육회",
        "presmpt_price": 500_000_000,
        "bid_begin_dt": datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        "bid_close_dt": datetime(2026, 3, 10, 18, 0, tzinfo=timezone.utc),
        "link_url": "https://www.g2b.go.kr/link/20260216001-00",
        "raw_data": {"bidNtceNo": "20260216001-00"},
        "filter_meta": {"matched_keywords": ["스포츠", "데이터"]},
        "pipeline_status": "collected",
        "retry_count": 0,
        "collected_at": datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_analyzed_row(sample_db_row):
    """분석 완료 DB 행 dict (analyzed 상태)"""
    row = dict(sample_db_row)
    row["pipeline_status"] = "analyzed"
    row["analysis_result"] = {
        "category": "스포츠_데이터",
        "relevance_score": 85,
        "summary": "스포츠 데이터 분석 플랫폼 구축 사업",
        "requirements": ["데이터 수집", "분석 엔진"],
        "needs_research_lab": False,
        "analysis_detail": "상세 분석 내용",
    }
    row["analyzed_at"] = datetime(2026, 2, 16, 9, 30, tzinfo=timezone.utc)
    return row


@pytest.fixture
def make_db_row():
    """DB 행 팩토리 — 필드 오버라이드 가능"""
    def _factory(**overrides):
        defaults = {
            "id": 1,
            "bid_notice_no": "TEST-001",
            "bid_notice_nm": "테스트 공고",
            "ntce_instt_nm": "",
            "dminstt_nm": "",
            "presmpt_price": 0,
            "bid_begin_dt": None,
            "bid_close_dt": None,
            "link_url": "",
            "raw_data": {},
            "filter_meta": {},
            "pipeline_status": "collected",
            "retry_count": 0,
            "collected_at": datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc),
        }
        defaults.update(overrides)
        return defaults
    return _factory
