"""G2BService 단위 테스트 (25건)

httpx, asyncpg mock 사용.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from class_lib.collector.g2b_service import (
    G2BService,
    G2BApiError,
    to_g2b_request_dt,
    map_item_to_announcement,
    _parse_price,
    _combine_date_time,
)
from class_lib.collector.schemas import G2BApiItem


# ============================================================
# GS-01~04: _parse_items
# ============================================================


class TestParseItems:
    @pytest.fixture
    def service(self):
        return G2BService()

    def test_gs01_none(self, service):
        """GS-01: items=None → 빈 리스트"""
        assert service._parse_items(None) == []

    def test_gs02_list(self, service):
        """GS-02: items=list → G2BApiItem 리스트"""
        items = [{"bidNtceNo": "001"}, {"bidNtceNo": "002"}]
        result = service._parse_items(items)
        assert len(result) == 2
        assert result[0].bidNtceNo == "001"
        assert result[1].bidNtceNo == "002"

    def test_gs03_dict_with_item_list(self, service):
        """GS-03: items={"item": [...]} → G2BApiItem 리스트"""
        items = {"item": [{"bidNtceNo": "001"}, {"bidNtceNo": "002"}]}
        result = service._parse_items(items)
        assert len(result) == 2

    def test_gs04_dict_single_item(self, service):
        """GS-04: items={"item": {...}} (단건) → [G2BApiItem]"""
        items = {"item": {"bidNtceNo": "001"}}
        result = service._parse_items(items)
        assert len(result) == 1
        assert result[0].bidNtceNo == "001"


# ============================================================
# GS-05~06: to_g2b_request_dt
# ============================================================


class TestToG2bRequestDt:
    def test_gs05_normal(self):
        """GS-05: datetime → 12자리 문자열"""
        dt = datetime(2026, 2, 16, 10, 30)
        assert to_g2b_request_dt(dt) == "202602161030"

    def test_gs06_midnight(self):
        """GS-06: 자정 (00:00)"""
        dt = datetime(2026, 1, 1, 0, 0)
        assert to_g2b_request_dt(dt) == "202601010000"


# ============================================================
# GS-07: map_item_to_announcement
# ============================================================


class TestMapItemToAnnouncement:
    def test_gs07_field_mapping(self, sample_api_item):
        """GS-07: G2BApiItem → CollectedAnnouncement 필드 매핑"""
        ann = map_item_to_announcement(sample_api_item)
        assert ann.bid_notice_no == "20260216001-00"
        assert ann.bid_notice_nm == "스포츠 데이터 분석 플랫폼 구축"
        assert ann.ntce_instt_nm == "국민체육진흥공단"
        assert ann.dminstt_nm == "대한체육회"
        assert ann.presmpt_price == 500_000_000
        assert ann.bid_begin_dt == "2026-02-20T10:00:00"
        assert ann.bid_close_dt == "2026-03-10T18:00:00"
        assert ann.link_url == "https://www.g2b.go.kr/link/20260216001-00"
        assert ann.raw_data["bidNtceNo"] == "20260216001-00"
        assert ann.collected_at  # ISO 8601 문자열 존재 확인


# ============================================================
# GS-08~11: _parse_price
# ============================================================


class TestParsePrice:
    def test_gs08_normal(self):
        """GS-08: 정상 숫자 문자열"""
        assert _parse_price("500000000") == 500_000_000

    def test_gs09_empty(self):
        """GS-09: 빈 문자열"""
        assert _parse_price("") == 0

    def test_gs10_comma(self):
        """GS-10: 쉼표 포함"""
        assert _parse_price("500,000,000") == 500_000_000

    def test_gs11_non_numeric(self):
        """GS-11: 비숫자"""
        assert _parse_price("미정") == 0


# ============================================================
# GS-12~15: _combine_date_time
# ============================================================


class TestCombineDateTime:
    def test_gs12_normal(self):
        """GS-12: 정상 변환"""
        result = _combine_date_time("2026-02-16", "10:00")
        assert result == "2026-02-16T10:00:00"

    def test_gs13_empty_date(self):
        """GS-13: 빈 날짜 → 빈 문자열"""
        assert _combine_date_time("", "10:00") == ""

    def test_gs14_empty_time(self):
        """GS-14: 빈 시간 → 00:00 기본값"""
        result = _combine_date_time("2026-02-16", "")
        assert result == "2026-02-16T00:00:00"

    def test_gs15_parse_failure(self):
        """GS-15: 파싱 실패 → 원본 날짜 문자열 반환"""
        result = _combine_date_time("invalid-date", "10:00")
        assert result == "invalid-date"


# ============================================================
# GS-16~21: _call_api
# ============================================================


class TestCallApi:
    @pytest.fixture
    def service(self):
        return G2BService()

    def _make_response(self, result_code, result_msg="", body=None):
        """httpx.Response mock 생성 헬퍼"""
        data = {
            "response": {
                "header": {"resultCode": result_code, "resultMsg": result_msg},
                "body": body or {"items": [], "totalCount": 0},
            }
        }
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = data
        resp.raise_for_status = MagicMock()
        return resp

    async def test_gs16_success(self, service):
        """GS-16: 정상 응답 (resultCode=00)"""
        client = AsyncMock(spec=httpx.AsyncClient)
        body = {"items": [{"bidNtceNo": "001"}], "totalCount": 1}
        client.get.return_value = self._make_response("00", body=body)

        result = await service._call_api(client, "http://test", {})
        assert result["totalCount"] == 1

    async def test_gs17_nodata(self, service):
        """GS-17: NODATA (resultCode=03) → 빈 리스트 (정상)"""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = self._make_response("03")

        result = await service._call_api(client, "http://test", {})
        assert result["items"] == []
        assert result["totalCount"] == 0

    async def test_gs18_retryable_then_success(self, service, mocker):
        """GS-18: 재시도 가능 에러 후 성공"""
        mocker.patch("class_lib.collector.g2b_service.asyncio.sleep", new_callable=AsyncMock)

        client = AsyncMock(spec=httpx.AsyncClient)
        body = {"items": [{"bidNtceNo": "001"}], "totalCount": 1}
        client.get.side_effect = [
            self._make_response("99", "일시 장애"),  # 재시도 가능
            self._make_response("00", body=body),     # 성공
        ]

        result = await service._call_api(client, "http://test", {})
        assert result["totalCount"] == 1
        assert client.get.call_count == 2

    async def test_gs19_non_retryable(self, service):
        """GS-19: 비재시도 에러 (resultCode=10) → G2BApiError"""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = self._make_response("10", "잘못된 요청")

        with pytest.raises(G2BApiError) as exc_info:
            await service._call_api(client, "http://test", {})
        assert exc_info.value.code == "10"

    async def test_gs20_http_error_non_retryable(self, service):
        """GS-20: HTTP 4xx 에러 → G2BApiError"""
        client = AsyncMock(spec=httpx.AsyncClient)

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        client.get.return_value = mock_resp
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_resp
        )

        with pytest.raises(G2BApiError):
            await service._call_api(client, "http://test", {})

    async def test_gs21_max_retries_exceeded(self, service, mocker):
        """GS-21: 최대 재시도 초과 → Graceful Degradation (빈 결과)"""
        mocker.patch("class_lib.collector.g2b_service.asyncio.sleep", new_callable=AsyncMock)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = self._make_response("99", "일시 장애")

        result = await service._call_api(client, "http://test", {}, max_retries=3)
        assert result["items"] == []
        assert client.get.call_count == 3


# ============================================================
# GS-22~23: _fetch_all_pages
# ============================================================


class TestFetchAllPages:
    @pytest.fixture
    def service(self):
        return G2BService()

    async def test_gs22_single_page(self, service, mocker):
        """GS-22: 단일 페이지"""
        mocker.patch("class_lib.collector.g2b_service.asyncio.sleep", new_callable=AsyncMock)

        body = {"items": [{"bidNtceNo": "001"}], "totalCount": 1}
        mocker.patch.object(service, "_call_api", new_callable=AsyncMock, return_value=body)

        client = AsyncMock(spec=httpx.AsyncClient)
        items = await service._fetch_all_pages(client, "http://test", {}, num_of_rows=100)
        assert len(items) == 1
        assert items[0].bidNtceNo == "001"

    async def test_gs23_multi_page(self, service, mocker):
        """GS-23: 멀티 페이지 (2페이지)"""
        mocker.patch("class_lib.collector.g2b_service.asyncio.sleep", new_callable=AsyncMock)

        page1 = {"items": [{"bidNtceNo": f"{i:03d}"} for i in range(2)], "totalCount": 3}
        page2 = {"items": [{"bidNtceNo": "002"}], "totalCount": 3}

        call_count = 0

        async def mock_call_api(client, url, params, max_retries=3):
            nonlocal call_count
            call_count += 1
            return page1 if call_count == 1 else page2

        mocker.patch.object(service, "_call_api", side_effect=mock_call_api)

        client = AsyncMock(spec=httpx.AsyncClient)
        items = await service._fetch_all_pages(client, "http://test", {}, num_of_rows=2)
        assert len(items) == 3  # 2 + 1


# ============================================================
# GS-24~25: fetch_announcements
# ============================================================


class TestFetchAnnouncements:
    @pytest.fixture
    def service(self):
        return G2BService()

    async def test_gs24_success(self, service, mocker):
        """GS-24: 정상 수집"""
        mocker.patch("class_lib.collector.g2b_service.asyncio.sleep", new_callable=AsyncMock)

        body = {
            "items": [
                {
                    "bidNtceNo": "001",
                    "bidNtceNm": "스포츠 플랫폼",
                    "presmptPrce": "100000000",
                    "bidBeginDate": "2026-02-20",
                    "bidBeginTm": "10:00",
                    "bidClseDate": "2026-03-10",
                    "bidClseTm": "18:00",
                }
            ],
            "totalCount": 1,
        }
        mocker.patch.object(service, "_call_api", new_callable=AsyncMock, return_value=body)

        start = datetime(2026, 2, 16, 0, 0)
        end = datetime(2026, 2, 16, 23, 59)
        result = await service.fetch_announcements(start, end)

        assert len(result) == 1
        assert result[0].bid_notice_no == "001"
        assert result[0].bid_notice_nm == "스포츠 플랫폼"

    async def test_gs25_api_error_graceful(self, service, mocker):
        """GS-25: API 에러 → Graceful Degradation (빈 리스트)"""
        mocker.patch.object(
            service,
            "_call_api",
            new_callable=AsyncMock,
            side_effect=G2BApiError("10", "잘못된 요청"),
        )

        start = datetime(2026, 2, 16, 0, 0)
        end = datetime(2026, 2, 16, 23, 59)
        result = await service.fetch_announcements(start, end)

        assert result == []
