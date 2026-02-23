"""Collector fixture — 샘플 데이터 팩토리"""

import pytest

from class_lib.collector.schemas import (
    CollectedAnnouncement,
    G2BApiItem,
)


@pytest.fixture
def sample_api_item() -> G2BApiItem:
    """나라장터 API 응답 아이템 샘플"""
    return G2BApiItem(
        bidNtceNo="20260216001-00",
        bidNtceOrd="00",
        bidNtceNm="스포츠 데이터 분석 플랫폼 구축",
        ntceInsttNm="국민체육진흥공단",
        dmndInsttNm="대한체육회",
        presmptPrce="500000000",
        bidBeginDate="2026-02-20",
        bidBeginTm="10:00",
        bidClseDate="2026-03-10",
        bidClseTm="18:00",
        bidNtceUrl="https://www.g2b.go.kr/link/20260216001-00",
    )


@pytest.fixture
def sample_announcement() -> CollectedAnnouncement:
    """내부 스키마 공고 샘플"""
    return CollectedAnnouncement(
        bid_notice_no="20260216001-00",
        bid_notice_nm="스포츠 데이터 분석 플랫폼 구축",
        ntce_instt_nm="국민체육진흥공단",
        dminstt_nm="대한체육회",
        presmpt_price=500_000_000,
        bid_begin_dt="2026-02-20T10:00:00",
        bid_close_dt="2026-03-10T18:00:00",
        link_url="https://www.g2b.go.kr/link/20260216001-00",
        raw_data={"bidNtceNo": "20260216001-00"},
        collected_at="2026-02-16T09:00:00",
    )


@pytest.fixture
def make_announcement():
    """CollectedAnnouncement 팩토리 — 필드 오버라이드 가능"""
    def _factory(**overrides) -> CollectedAnnouncement:
        defaults = {
            "bid_notice_no": "TEST-001",
            "bid_notice_nm": "테스트 공고",
            "ntce_instt_nm": "",
            "dminstt_nm": "",
            "presmpt_price": 0,
            "bid_begin_dt": "",
            "bid_close_dt": "",
            "link_url": "",
            "raw_data": {},
            "collected_at": "2026-02-16T09:00:00",
        }
        defaults.update(overrides)
        return CollectedAnnouncement(**defaults)
    return _factory
