"""Pipeline fixture — mock DB 커넥션 + 샘플 데이터 (v2)

v2 변경:
- sample_analyzed_row 제거 (pipeline에서 분석 단계 제거)
- attachment_urls 필드 추가
- analysis_result 필드 제거
"""

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
        "attachment_urls": [],
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
        "attachment_urls": [],
        "pipeline_status": "collected",
        "retry_count": 0,
        "collected_at": datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc),
        "sent_at": None,
    }


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
            "attachment_urls": [],
            "pipeline_status": "collected",
            "retry_count": 0,
            "collected_at": datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc),
            "sent_at": None,
        }
        defaults.update(overrides)
        return defaults
    return _factory
