"""PipelineRunner 단위 테스트 (30건)

asyncpg, httpx mock 사용. 실제 DB/HTTP 호출 없음.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from class_lib.pipeline_runner.pipeline_runner import PipelineRunner
from class_lib.pipeline_runner.utils import parse_timestamptz, serialize_dt


# ============================================================
# PR-01: __init__
# ============================================================


class TestInit:
    def test_pr01_defaults(self):
        """PR-01: Config 내부 생성, _running=False"""
        runner = PipelineRunner()
        assert runner.config is not None
        assert runner._running is False


# ============================================================
# PR-02~05: run()
# ============================================================


class TestRun:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr02_concurrent_skip(self, runner):
        """PR-02: 동시 실행 방지 → skipped"""
        runner._running = True
        result = await runner.run()
        assert result["status"] == "skipped"
        assert result["reason"] == "already_running"

    async def test_pr03_no_items(self, runner, mocker, mock_conn):
        """PR-03: 빈 수신 + collected 없음 → no_items"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_conn,
        )
        mock_conn.execute.return_value = "UPDATE 0"
        mock_conn.fetch.return_value = []

        result = await runner.run(announcements=[])
        assert result["status"] == "no_items"
        assert runner._running is False

    async def test_pr04_full_flow(self, runner, mocker, mock_conn,
                                   sample_db_row, sample_analyzed_row):
        """PR-04: 정상 흐름 (저장 → 복구 → 재시도 → 분석 → 전송)"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_conn,
        )
        mocker.patch.object(
            runner, "_save_announcements",
            new_callable=AsyncMock, return_value=(1, 0),
        )
        mocker.patch.object(
            runner, "_recover_stuck",
            new_callable=AsyncMock, return_value=0,
        )
        mocker.patch.object(
            runner, "_retry_failed",
            new_callable=AsyncMock, return_value=0,
        )

        async def mock_fetch(conn, status):
            if status == "collected":
                return [sample_db_row]
            if status == "analyzed":
                return [sample_analyzed_row]
            return []
        mocker.patch.object(runner, "_fetch_by_status", side_effect=mock_fetch)

        mocker.patch.object(
            runner, "_analyze_one",
            new_callable=AsyncMock,
            return_value={"category": "스포츠_데이터"},
        )
        mocker.patch.object(
            runner, "_send_batch",
            new_callable=AsyncMock, return_value=1,
        )

        result = await runner.run(
            announcements=[{"bid_notice_no": "TEST-001"}],
        )
        assert result["status"] == "completed"
        assert result["saved"] == 1
        assert result["analyzed"] == 1
        assert result["sent"] == 1
        assert result["duration_ms"] >= 0
        assert runner._running is False

    async def test_pr05_error(self, runner, mocker):
        """PR-05: DB 연결 예외 → error, _running 리셋"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.asyncpg.connect",
            new_callable=AsyncMock,
            side_effect=ConnectionError("DB 연결 실패"),
        )

        result = await runner.run()
        assert result["status"] == "error"
        assert runner._running is False


# ============================================================
# PR-06~08: _save_announcements
# ============================================================


class TestSaveAnnouncements:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr06_insert_new(self, runner, mock_conn, sample_filtered):
        """PR-06: 신규 INSERT → saved=1, skipped=0"""
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        saved, skipped = await runner._save_announcements(
            mock_conn, [sample_filtered],
        )
        assert saved == 1
        assert skipped == 0

    async def test_pr07_duplicate_skip(self, runner, mock_conn, sample_filtered):
        """PR-07: 중복 SKIP → saved=0, skipped=1"""
        mock_conn.execute = AsyncMock(return_value="INSERT 0 0")

        saved, skipped = await runner._save_announcements(
            mock_conn, [sample_filtered],
        )
        assert saved == 0
        assert skipped == 1

    async def test_pr08_mixed(self, runner, mock_conn):
        """PR-08: 혼합 (신규 1 + 중복 1) → saved=1, skipped=1"""
        mock_conn.execute = AsyncMock(
            side_effect=["INSERT 0 1", "INSERT 0 0"],
        )
        items = [
            {"bid_notice_no": "NEW-001", "bid_notice_nm": "새 공고"},
            {"bid_notice_no": "DUP-001", "bid_notice_nm": "중복 공고"},
        ]

        saved, skipped = await runner._save_announcements(mock_conn, items)
        assert saved == 1
        assert skipped == 1


# ============================================================
# PR-09~11: _analyze_one
# ============================================================


def _mock_httpx_success(mocker, response_json):
    """httpx AsyncClient mock — 성공 응답"""
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch(
        "class_lib.pipeline_runner.pipeline_runner.httpx.AsyncClient",
        return_value=mock_client,
    )
    return mock_client


def _mock_httpx_error(mocker, error):
    """httpx AsyncClient mock — 에러 발생"""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=error)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch(
        "class_lib.pipeline_runner.pipeline_runner.httpx.AsyncClient",
        return_value=mock_client,
    )
    return mock_client


class TestAnalyzeOne:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr09_success(self, runner, mocker, mock_conn, sample_db_row):
        """PR-09: 분석 성공 → analyzing → analyzed 상태 전이"""
        analysis = {"category": "스포츠_데이터", "relevance_score": 85}
        _mock_httpx_success(mocker, analysis)
        mocker.patch.object(runner, "_update_status", new_callable=AsyncMock)

        result = await runner._analyze_one(mock_conn, sample_db_row)

        assert result == analysis
        calls = runner._update_status.call_args_list
        assert calls[0].args[2]["pipeline_status"] == "analyzing"
        assert calls[1].args[2]["pipeline_status"] == "analyzed"

    async def test_pr10_http_error(self, runner, mocker, mock_conn, sample_db_row):
        """PR-10: HTTP 에러 → analyze_failed, retry_count 증가"""
        _mock_httpx_error(
            mocker,
            httpx.RequestError("Connection refused"),
        )
        mocker.patch.object(runner, "_update_status", new_callable=AsyncMock)

        result = await runner._analyze_one(mock_conn, sample_db_row)

        assert result is None
        calls = runner._update_status.call_args_list
        assert calls[1].args[2]["pipeline_status"] == "analyze_failed"
        assert calls[1].args[2]["retry_count_increment"] is True

    async def test_pr11_unexpected_exception(self, runner, mocker, mock_conn,
                                              sample_db_row):
        """PR-11: 예상치 못한 예외 → analyze_failed"""
        _mock_httpx_error(mocker, RuntimeError("예상치 못한 에러"))
        mocker.patch.object(runner, "_update_status", new_callable=AsyncMock)

        result = await runner._analyze_one(mock_conn, sample_db_row)

        assert result is None
        calls = runner._update_status.call_args_list
        assert calls[1].args[2]["pipeline_status"] == "analyze_failed"


# ============================================================
# PR-12~15: _send_batch
# ============================================================


class TestSendBatch:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr12_all_success(self, runner, mocker, mock_conn,
                                     sample_analyzed_row):
        """PR-12: 전체 성공 → sent 상태"""
        _mock_httpx_success(mocker, {
            "received": 1, "created": 1, "errors": [],
        })
        mocker.patch.object(runner, "_update_status", new_callable=AsyncMock)

        sent = await runner._send_batch(mock_conn, [sample_analyzed_row])
        assert sent == 1

    async def test_pr13_partial_failure(self, runner, mocker, mock_conn,
                                         make_db_row):
        """PR-13: 부분 실패 → sent/send_failed 혼합"""
        row_ok = make_db_row(
            bid_notice_no="OK-001", pipeline_status="analyzed",
            analysis_result={"category": "test"},
        )
        row_fail = make_db_row(
            bid_notice_no="FAIL-001", pipeline_status="analyzed",
            analysis_result={"category": "test"},
        )
        _mock_httpx_success(mocker, {
            "received": 2,
            "created": 1,
            "errors": [{"bid_notice_no": "FAIL-001", "error": "duplicate"}],
        })
        mocker.patch.object(runner, "_update_status", new_callable=AsyncMock)

        sent = await runner._send_batch(mock_conn, [row_ok, row_fail])
        assert sent == 1

        statuses = [
            call.args[2]["pipeline_status"]
            for call in runner._update_status.call_args_list
        ]
        assert "sent" in statuses
        assert "send_failed" in statuses

    async def test_pr14_total_failure(self, runner, mocker, mock_conn,
                                       sample_analyzed_row):
        """PR-14: EC2 전송 전체 실패 → send_failed"""
        _mock_httpx_error(mocker, httpx.RequestError("Connection refused"))
        mocker.patch.object(runner, "_update_status", new_callable=AsyncMock)

        sent = await runner._send_batch(mock_conn, [sample_analyzed_row])
        assert sent == 0

        calls = runner._update_status.call_args_list
        assert calls[0].args[2]["pipeline_status"] == "send_failed"

    async def test_pr15_empty_list(self, runner, mock_conn):
        """PR-15: 빈 리스트 → 0 반환, DB 호출 없음"""
        sent = await runner._send_batch(mock_conn, [])
        assert sent == 0


# ============================================================
# PR-16~17: _recover_stuck
# ============================================================


class TestRecoverStuck:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr16_recover(self, runner, mock_conn):
        """PR-16: analyzing/sending 건 복구 → 건수 반환"""
        mock_conn.execute = AsyncMock(return_value="UPDATE 2")

        recovered = await runner._recover_stuck(mock_conn)
        assert recovered == 2

    async def test_pr17_nothing_to_recover(self, runner, mock_conn):
        """PR-17: 복구 대상 없음 → 0"""
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        recovered = await runner._recover_stuck(mock_conn)
        assert recovered == 0


# ============================================================
# PR-18~20: _retry_failed
# ============================================================


class TestRetryFailed:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr18_analyze_failed_retry(self, runner, mock_conn):
        """PR-18: analyze_failed (retry<3) → collected 원복"""
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"bid_notice_no": "FAIL-001",
              "pipeline_status": "analyze_failed", "retry_count": 1}],
            [],  # critical 대상 없음
        ])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        retried = await runner._retry_failed(mock_conn)
        assert retried == 1

    async def test_pr19_send_failed_retry(self, runner, mock_conn):
        """PR-19: send_failed (retry<3) → analyzed 원복"""
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"bid_notice_no": "FAIL-001",
              "pipeline_status": "send_failed", "retry_count": 2}],
            [],
        ])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        retried = await runner._retry_failed(mock_conn)
        assert retried == 1

    async def test_pr20_critical_no_retry(self, runner, mock_conn):
        """PR-20: retry_count >= 3 → CRITICAL 로그, 원복하지 않음"""
        mock_conn.fetch = AsyncMock(side_effect=[
            [],  # 재시도 대상 없음
            [{"bid_notice_no": "DEAD-001",
              "pipeline_status": "analyze_failed",
              "retry_count": 3, "error_message": "영구 실패"}],
        ])

        retried = await runner._retry_failed(mock_conn)
        assert retried == 0


# ============================================================
# PR-21~22: _build_payload
# ============================================================


class TestBuildPayload:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    def test_pr21_normal_merge(self, runner, sample_db_row):
        """PR-21: 원본 + 분석 결과 정상 병합"""
        analysis = {
            "category": "스포츠_데이터",
            "relevance_score": 85,
            "summary": "요약",
            "requirements": ["요구사항1"],
            "needs_research_lab": False,
            "analysis_detail": "상세",
        }

        payload = runner._build_payload(sample_db_row, analysis)
        assert payload["bid_notice_no"] == "20260216001-00"
        assert payload["category"] == "스포츠_데이터"
        assert payload["relevance_score"] == 85
        assert payload["summary"] == "요약"

    def test_pr22_empty_analysis(self, runner, sample_db_row):
        """PR-22: 빈 분석 결과 → 기본값"""
        payload = runner._build_payload(sample_db_row, {})
        assert payload["bid_notice_no"] == "20260216001-00"
        assert payload["category"] is None
        assert payload["relevance_score"] == 0
        assert payload["needs_research_lab"] is False


# ============================================================
# PR-23~27: parse_timestamptz
# ============================================================


class TestParseTimestamptz:
    def test_pr23_none(self):
        """PR-23: None → None"""
        assert parse_timestamptz(None) is None

    def test_pr24_empty_string(self):
        """PR-24: 빈 문자열 → None"""
        assert parse_timestamptz("") is None

    def test_pr25_iso_string(self):
        """PR-25: ISO 문자열 → datetime"""
        result = parse_timestamptz("2026-02-16T09:00:00")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 16

    def test_pr26_datetime_passthrough(self):
        """PR-26: datetime → datetime (pass-through)"""
        dt = datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc)
        assert parse_timestamptz(dt) is dt

    def test_pr27_invalid_string(self):
        """PR-27: 잘못된 문자열 → None"""
        assert parse_timestamptz("not-a-date") is None


# ============================================================
# PR-28~30: serialize_dt
# ============================================================


class TestSerializeDt:
    def test_pr28_none(self):
        """PR-28: None → None"""
        assert serialize_dt(None) is None

    def test_pr29_datetime_to_iso(self):
        """PR-29: datetime → ISO 문자열"""
        dt = datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc)
        result = serialize_dt(dt)
        assert isinstance(result, str)
        assert "2026-02-16" in result

    def test_pr30_string_passthrough(self):
        """PR-30: 문자열 → 문자열 (pass-through)"""
        assert serialize_dt("2026-02-16T09:00:00") == "2026-02-16T09:00:00"
