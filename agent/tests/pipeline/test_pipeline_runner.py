"""PipelineRunner + repository 단위 테스트 (v2 — 30건)

v2 변경:
- PipelineRunner.run() → 저장 + 워커 기동 (즉시 "accepted" 반환)
- DB 조작은 repository 모듈 함수로 분리
- _analyze_one() 제거 (분석은 Cowork에서 수행)
- _build_payload() 단일 인자 (analysis_result 제거)
- _send_one() 건별 EC2 전송

asyncpg, httpx mock 사용. 실제 DB/HTTP 호출 없음.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from class_lib.pipeline_runner.pipeline_runner import PipelineRunner
from class_lib.pipeline_runner import repository
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

    async def test_pr02_concurrent_skip(self, runner, mocker, mock_conn):
        """PR-02: 워커 실행 중 → 저장만 수행, "accepted" 반환"""
        runner._running = True
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_conn,
        )
        mock_conn.execute.return_value = "INSERT 0 1"

        result = await runner.run(announcements=[{
            "bid_notice_no": "TEST-001",
            "bid_notice_nm": "테스트",
        }])
        assert result["status"] == "accepted"
        assert result["saved"] == 1

    async def test_pr03_no_items(self, runner, mocker, mock_conn):
        """PR-03: 빈 수신 → accepted, saved=0"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_conn,
        )
        # _run_worker를 mock하여 백그라운드 태스크 방지
        mocker.patch.object(runner, "_run_worker", new_callable=AsyncMock)

        result = await runner.run(announcements=[])
        assert result["status"] == "accepted"
        assert result["saved"] == 0
        assert result["skipped"] == 0

    async def test_pr04_save_and_accept(self, runner, mocker, mock_conn):
        """PR-04: 정상 저장 → accepted, saved=1"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=mock_conn,
        )
        mock_conn.execute.return_value = "INSERT 0 1"
        # _run_worker를 mock하여 백그라운드 태스크 방지
        mocker.patch.object(runner, "_run_worker", new_callable=AsyncMock)

        result = await runner.run(announcements=[{
            "bid_notice_no": "TEST-001",
            "bid_notice_nm": "테스트 공고",
        }])
        assert result["status"] == "accepted"
        assert result["saved"] == 1

    async def test_pr05_error(self, runner, mocker):
        """PR-05: DB 연결 예외 → error"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.asyncpg.connect",
            new_callable=AsyncMock,
            side_effect=ConnectionError("DB 연결 실패"),
        )

        result = await runner.run(announcements=[{
            "bid_notice_no": "TEST-001",
            "bid_notice_nm": "테스트",
        }])
        assert result["status"] == "error"


# ============================================================
# PR-06~08: repository.save_announcements
# ============================================================


class TestSaveAnnouncements:
    async def test_pr06_insert_new(self, mock_conn, sample_filtered):
        """PR-06: 신규 INSERT → saved=1, skipped=0"""
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        saved, skipped = await repository.save_announcements(
            mock_conn, [sample_filtered],
        )
        assert saved == 1
        assert skipped == 0

    async def test_pr07_duplicate_skip(self, mock_conn, sample_filtered):
        """PR-07: 중복 SKIP → saved=0, skipped=1"""
        mock_conn.execute = AsyncMock(return_value="INSERT 0 0")

        saved, skipped = await repository.save_announcements(
            mock_conn, [sample_filtered],
        )
        assert saved == 0
        assert skipped == 1

    async def test_pr08_mixed(self, mock_conn):
        """PR-08: 혼합 (신규 1 + 중복 1) → saved=1, skipped=1"""
        mock_conn.execute = AsyncMock(
            side_effect=["INSERT 0 1", "INSERT 0 0"],
        )
        items = [
            {"bid_notice_no": "NEW-001", "bid_notice_nm": "새 공고"},
            {"bid_notice_no": "DUP-001", "bid_notice_nm": "중복 공고"},
        ]

        saved, skipped = await repository.save_announcements(mock_conn, items)
        assert saved == 1
        assert skipped == 1


# ============================================================
# PR-09~11: _download_attachments (v2: replaces _analyze_one)
# ============================================================


def _mock_httpx_success(mocker, response_json):
    """httpx AsyncClient mock — 성공 응답"""
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"fake file content"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
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
    mock_client.get = AsyncMock(side_effect=error)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch(
        "class_lib.pipeline_runner.pipeline_runner.httpx.AsyncClient",
        return_value=mock_client,
    )
    return mock_client


class TestDownloadAttachments:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr09_no_urls(self, runner):
        """PR-09: 첨부파일 URL 없음 → 스킵"""
        announcement = {"bid_notice_no": "TEST-001", "attachment_urls": []}
        # Should not raise
        await runner._download_attachments(announcement)

    async def test_pr10_download_success(self, runner, mocker, tmp_path):
        """PR-10: 첨부파일 다운로드 성공"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.ATTACHMENTS_BASE_DIR",
            tmp_path,
        )
        mock_response = MagicMock()
        mock_response.content = b"PDF content"
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {
            "content-disposition": "attachment;filename=spec.pdf"
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.httpx.AsyncClient",
            return_value=mock_client,
        )

        announcement = {
            "bid_notice_no": "TEST-001",
            "attachment_urls": ["https://example.com/spec.pdf"],
        }
        await runner._download_attachments(announcement)

        downloaded = tmp_path / "TEST-001" / "spec.pdf"
        assert downloaded.exists()
        assert downloaded.read_bytes() == b"PDF content"

    async def test_pr11_download_failure_graceful(self, runner, mocker, tmp_path):
        """PR-11: 첨부파일 다운로드 실패 → 경고만, 예외 전파 없음"""
        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.ATTACHMENTS_BASE_DIR",
            tmp_path,
        )
        _mock_httpx_error(mocker, httpx.RequestError("Connection refused"))

        announcement = {
            "bid_notice_no": "TEST-001",
            "attachment_urls": ["https://example.com/spec.pdf"],
        }
        # Should not raise
        await runner._download_attachments(announcement)


# ============================================================
# PR-12~15: _send_one / _send_batch / _send_chunk
# ============================================================


class TestSendOne:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    async def test_pr12_send_success(self, runner, mocker, mock_conn, sample_db_row):
        """PR-12: 건별 전송 성공 → sent 상태"""
        _mock_httpx_success(mocker, {
            "received": 1, "created": 1, "errors": [],
        })

        success = await runner._send_one(mock_conn, sample_db_row)
        assert success is True

        # update_status 호출 확인 (sending → sent)
        calls = mock_conn.execute.call_args_list
        assert len(calls) >= 2  # sending + sent

    async def test_pr13_send_http_error(self, runner, mocker, mock_conn, sample_db_row):
        """PR-13: HTTP 에러 → send_failed"""
        _mock_httpx_error(mocker, httpx.RequestError("Connection refused"))

        success = await runner._send_one(mock_conn, sample_db_row)
        assert success is False

    async def test_pr14_send_unexpected_error(self, runner, mocker, mock_conn,
                                                sample_db_row):
        """PR-14: 예상치 못한 예외 → send_failed"""
        _mock_httpx_error(mocker, RuntimeError("예상치 못한 에러"))

        success = await runner._send_one(mock_conn, sample_db_row)
        assert success is False

    async def test_pr15_send_batch_empty(self, runner, mock_conn):
        """PR-15: 빈 리스트 → 0 반환"""
        sent = await runner._send_batch(mock_conn, [])
        assert sent == 0


# ============================================================
# PR-16~17: repository.recover_stuck
# ============================================================


class TestRecoverStuck:
    async def test_pr16_recover(self, mock_conn):
        """PR-16: sending 건 복구 → 건수 반환"""
        mock_conn.execute = AsyncMock(return_value="UPDATE 2")

        recovered = await repository.recover_stuck(mock_conn)
        assert recovered == 2

    async def test_pr17_nothing_to_recover(self, mock_conn):
        """PR-17: 복구 대상 없음 → 0"""
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        recovered = await repository.recover_stuck(mock_conn)
        assert recovered == 0


# ============================================================
# PR-18~20: repository.retry_failed
# ============================================================


class TestRetryFailed:
    async def test_pr18_send_failed_retry(self, mock_conn):
        """PR-18: send_failed (retry<3) → collected 원복"""
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.fetch = AsyncMock(return_value=[])  # critical 대상 없음

        retried = await repository.retry_failed(mock_conn)
        assert retried == 1

    async def test_pr19_multiple_retry(self, mock_conn):
        """PR-19: 여러 건 send_failed → collected 원복"""
        mock_conn.execute = AsyncMock(return_value="UPDATE 3")
        mock_conn.fetch = AsyncMock(return_value=[])

        retried = await repository.retry_failed(mock_conn)
        assert retried == 3

    async def test_pr20_critical_no_retry(self, mock_conn):
        """PR-20: retry_count >= 3 → CRITICAL 로그, 원복하지 않음"""
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")
        mock_conn.fetch = AsyncMock(return_value=[
            {"bid_notice_no": "DEAD-001",
             "pipeline_status": "send_failed",
             "retry_count": 3, "error_message": "영구 실패"},
        ])

        retried = await repository.retry_failed(mock_conn)
        assert retried == 0


# ============================================================
# PR-21~22: _build_payload (v2: 단일 인자)
# ============================================================


class TestBuildPayload:
    @pytest.fixture
    def runner(self):
        return PipelineRunner()

    def test_pr21_normal(self, runner, sample_db_row):
        """PR-21: 원본 데이터 → 페이로드 변환"""
        payload = runner._build_payload(sample_db_row)
        assert payload["bid_notice_no"] == "20260216001-00"
        assert payload["bid_notice_nm"] == "스포츠 데이터 분석 플랫폼 구축"
        assert payload["ntce_instt_nm"] == "국민체육진흥공단"
        assert payload["presmpt_price"] == 500_000_000
        assert payload["attachment_urls"] == []

    def test_pr22_minimal_data(self, runner, make_db_row):
        """PR-22: 최소 데이터 → 기본값으로 페이로드 생성"""
        row = make_db_row()
        payload = runner._build_payload(row)
        assert payload["bid_notice_no"] == "TEST-001"
        assert payload["bid_notice_nm"] == "테스트 공고"
        assert payload["attachment_urls"] == []
        assert payload["collected_at"] is not None


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
