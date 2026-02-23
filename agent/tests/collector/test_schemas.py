"""Collector 스키마 단위 테스트 (11건)

Mock 없이 Pydantic 모델 자체 검증.
"""

from datetime import datetime

from class_lib.collector.schemas import (
    G2BApiItem,
    G2BApiBody,
    G2BApiResponse,
    G2BApiResponseWrapper,
    G2BApiHeader,
    CollectedAnnouncement,
    FilterMeta,
    FilteredAnnouncement,
    CollectorHistory,
)


# === S-01~02: G2BApiItem ===


class TestG2BApiItem:
    def test_s01_default_values(self):
        """S-01: 기본값으로 생성 가능"""
        item = G2BApiItem()
        assert item.bidNtceNo == ""
        assert item.bidNtceOrd == "00"
        assert item.bidNtceNm == ""
        assert item.presmptPrce == ""
        assert item.bidBeginDate == ""

    def test_s02_extra_allow(self):
        """S-02: extra='allow'로 미정의 필드 수용"""
        item = G2BApiItem(bidNtceNo="001", unknownField="hello", anotherField=42)
        assert item.bidNtceNo == "001"
        assert item.unknownField == "hello"  # type: ignore[attr-defined]
        assert item.anotherField == 42  # type: ignore[attr-defined]


# === S-03~05: G2BApiBody ===


class TestG2BApiBody:
    def test_s03_items_list(self):
        """S-03: items가 list 형태"""
        body = G2BApiBody(items=[{"bidNtceNo": "001"}], totalCount=1)
        assert isinstance(body.items, list)
        assert body.totalCount == 1

    def test_s04_items_dict(self):
        """S-04: items가 dict 형태 (API 실제 응답)"""
        body = G2BApiBody(items={"item": [{"bidNtceNo": "001"}]}, totalCount=1)
        assert isinstance(body.items, dict)

    def test_s05_items_none(self):
        """S-05: items가 None (결과 없음)"""
        body = G2BApiBody(items=None, totalCount=0)
        assert body.items is None
        assert body.totalCount == 0


# === S-06: G2BApiResponse ===


class TestG2BApiResponse:
    def test_s06_nested_structure(self):
        """S-06: response > header/body 중첩 구조 접근"""
        resp = G2BApiResponse(
            response=G2BApiResponseWrapper(
                header=G2BApiHeader(resultCode="00", resultMsg="정상"),
                body=G2BApiBody(totalCount=5, numOfRows=100, pageNo=1),
            )
        )
        assert resp.response.header.resultCode == "00"
        assert resp.response.header.resultMsg == "정상"
        assert resp.response.body.totalCount == 5


# === S-07~08: CollectedAnnouncement ===


class TestCollectedAnnouncement:
    def test_s07_field_mapping(self, sample_announcement):
        """S-07: 필드 매핑 정확성"""
        ann = sample_announcement
        assert ann.bid_notice_no == "20260216001-00"
        assert ann.bid_notice_nm == "스포츠 데이터 분석 플랫폼 구축"
        assert ann.ntce_instt_nm == "국민체육진흥공단"
        assert ann.dminstt_nm == "대한체육회"
        assert ann.presmpt_price == 500_000_000
        assert ann.bid_begin_dt == "2026-02-20T10:00:00"
        assert ann.bid_close_dt == "2026-03-10T18:00:00"
        assert ann.link_url == "https://www.g2b.go.kr/link/20260216001-00"

    def test_s08_default_values(self):
        """S-08: 기본값"""
        ann = CollectedAnnouncement(
            bid_notice_no="001",
            bid_notice_nm="테스트",
        )
        assert ann.ntce_instt_nm == ""
        assert ann.dminstt_nm == ""
        assert ann.presmpt_price == 0
        assert ann.bid_begin_dt == ""
        assert ann.raw_data == {}
        assert ann.collected_at == ""


# === S-09: FilterMeta ===


class TestFilterMeta:
    def test_s09_default_values(self):
        """S-09: 기본값 (빈 리스트, None, False)"""
        meta = FilterMeta()
        assert meta.matched_keywords == []
        assert meta.match_fields == []
        assert meta.keyword_priority is None
        assert meta.matched_categories == []
        assert meta.excluded is False
        assert meta.exclusion_keyword is None


# === S-10: FilteredAnnouncement ===


class TestFilteredAnnouncement:
    def test_s10_inherits_collected(self, sample_announcement):
        """S-10: CollectedAnnouncement 상속 + filter_meta 포함"""
        meta = FilterMeta(
            matched_keywords=["스포츠"],
            match_fields=["bid_notice_nm"],
            keyword_priority="primary",
        )
        filtered = FilteredAnnouncement(
            **sample_announcement.model_dump(),
            filter_meta=meta,
        )
        # 부모 필드 접근
        assert filtered.bid_notice_no == "20260216001-00"
        assert filtered.bid_notice_nm == "스포츠 데이터 분석 플랫폼 구축"
        # filter_meta 접근
        assert filtered.filter_meta.matched_keywords == ["스포츠"]
        assert filtered.filter_meta.keyword_priority == "primary"


# === S-11: CollectorHistory ===


class TestCollectorHistory:
    def test_s11_required_fields(self):
        """S-11: 필수 필드 (operation, collected_at, collected_end_dt)"""
        now = datetime.now()
        history = CollectorHistory(
            operation="bid_announcement",
            collected_at=now,
            collected_end_dt=now,
        )
        assert history.operation == "bid_announcement"
        assert history.collected_at == now
        assert history.total_count == 0
        assert history.filtered_count == 0
        assert history.duration_ms == 0
        assert history.status == "success"
        assert history.error_message == ""
        assert history.id is None
