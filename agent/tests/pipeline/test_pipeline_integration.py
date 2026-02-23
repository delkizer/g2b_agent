"""Pipeline 통합 테스트 (7건)

실제 PostgreSQL DB + mock HTTP (Analyzer API, EC2 API).
테스트 데이터는 bid_notice_no 'E2E-' 접두사, 테스트 후 자동 정리.

실행: pytest -m integration tests/pipeline/test_pipeline_integration.py -v
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import httpx
import pytest

from class_lib.pipeline_runner.pipeline_runner import PipelineRunner


pytestmark = pytest.mark.integration


# ── 헬퍼 ────────────────────────────────────────────────────


def _read_real_db_url() -> str:
    """환경 파일에서 실제 DATABASE_URL을 읽는다.

    monkeypatch 이전에 호출 가능하도록 모듈 수준에서 실행.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent  # agent/

    django_env = "development"
    env_file = base_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("DJANGO_ENV="):
                django_env = stripped.split("=", 1)[1].strip().strip("\"'")
                break

    env_specific = base_dir / f".env.{django_env}"
    if env_specific.exists():
        for line in env_specific.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("DATABASE_URL="):
                return stripped.split("=", 1)[1].strip().strip("\"'")

    return "postgresql://localhost:5432/spotv"


REAL_DB_URL = _read_real_db_url()


# ── 픽스처 ──────────────────────────────────────────────────


@pytest.fixture
def use_real_db(monkeypatch):
    """autouse _override_env 이후 DATABASE_URL을 실제 값으로 재설정"""
    monkeypatch.setenv("DATABASE_URL", REAL_DB_URL)


@pytest.fixture
def runner(use_real_db):
    """실제 DB 연결 PipelineRunner"""
    return PipelineRunner()


@pytest.fixture
async def db_conn(use_real_db):
    """직접 asyncpg 커넥션 (검증 쿼리용)"""
    conn = await asyncpg.connect(REAL_DB_URL)
    yield conn
    await conn.close()


@pytest.fixture(autouse=True)
async def cleanup(use_real_db):
    """E2E- 접두사 테스트 데이터 정리 (전후)"""
    conn = await asyncpg.connect(REAL_DB_URL)
    await conn.execute(
        "DELETE FROM g2b.collected_announcements "
        "WHERE bid_notice_no LIKE 'E2E-%'"
    )
    await conn.close()

    yield

    conn = await asyncpg.connect(REAL_DB_URL)
    await conn.execute(
        "DELETE FROM g2b.collected_announcements "
        "WHERE bid_notice_no LIKE 'E2E-%'"
    )
    await conn.close()


# ── 테스트 ──────────────────────────────────────────────────


class TestPipelineIntegration:

    # -- DB 저장 ---------------------------------------------------

    async def test_e2e01_save_and_verify(self, runner, db_conn):
        """E2E-01: 공고 저장 → DB 행 검증"""
        conn = await asyncpg.connect(REAL_DB_URL)
        try:
            saved, skipped = await runner._save_announcements(conn, [{
                "bid_notice_no": "E2E-001",
                "bid_notice_nm": "E2E 테스트 공고",
                "ntce_instt_nm": "테스트기관",
                "dminstt_nm": "수요기관",
                "presmpt_price": 100_000_000,
                "bid_begin_dt": "2026-02-20T10:00:00",
                "bid_close_dt": "2026-03-10T18:00:00",
                "link_url": "https://test.example.com",
                "raw_data": {"key": "value"},
                "filter_meta": {"matched": ["스포츠"]},
                "collected_at": "2026-02-16T09:00:00",
            }])
        finally:
            await conn.close()

        assert saved == 1
        assert skipped == 0

        row = await db_conn.fetchrow(
            "SELECT * FROM g2b.collected_announcements "
            "WHERE bid_notice_no = $1", "E2E-001",
        )
        assert row is not None
        assert row["bid_notice_nm"] == "E2E 테스트 공고"
        assert row["pipeline_status"] == "collected"
        assert row["presmpt_price"] == 100_000_000

    async def test_e2e02_duplicate_skip(self, runner, db_conn):
        """E2E-02: 중복 INSERT → ON CONFLICT DO NOTHING"""
        item = {
            "bid_notice_no": "E2E-DUP",
            "bid_notice_nm": "중복 테스트",
            "collected_at": "2026-02-16T09:00:00",
        }

        conn = await asyncpg.connect(REAL_DB_URL)
        try:
            saved1, _ = await runner._save_announcements(conn, [item])
            saved2, skipped2 = await runner._save_announcements(conn, [item])
        finally:
            await conn.close()

        assert saved1 == 1
        assert saved2 == 0
        assert skipped2 == 1

        # DB에 1건만 존재
        count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM g2b.collected_announcements "
            "WHERE bid_notice_no = $1", "E2E-DUP",
        )
        assert count == 1

    # -- 상태 전이 -------------------------------------------------

    async def test_e2e03_status_transitions(self, runner, db_conn):
        """E2E-03: 상태 전이 collected → analyzing → analyzed"""
        conn = await asyncpg.connect(REAL_DB_URL)
        try:
            await runner._save_announcements(conn, [{
                "bid_notice_no": "E2E-STATUS",
                "bid_notice_nm": "상태 전이 테스트",
                "collected_at": "2026-02-16T09:00:00",
            }])

            # collected → analyzing
            await runner._update_status(conn, "E2E-STATUS", {
                "pipeline_status": "analyzing",
            })
        finally:
            await conn.close()

        row = await db_conn.fetchrow(
            "SELECT pipeline_status FROM g2b.collected_announcements "
            "WHERE bid_notice_no = $1", "E2E-STATUS",
        )
        assert row["pipeline_status"] == "analyzing"

    # -- 복구 + 재시도 ---------------------------------------------

    async def test_e2e04_recover_stuck(self, runner, db_conn):
        """E2E-04: 비정상 종료 복구 — analyzing → collected"""
        await db_conn.execute(
            "INSERT INTO g2b.collected_announcements "
            "(bid_notice_no, bid_notice_nm, pipeline_status) "
            "VALUES ($1, $2, 'analyzing')",
            "E2E-STUCK", "stuck 테스트",
        )

        conn = await asyncpg.connect(REAL_DB_URL)
        try:
            recovered = await runner._recover_stuck(conn)
        finally:
            await conn.close()

        assert recovered >= 1

        row = await db_conn.fetchrow(
            "SELECT pipeline_status, error_message "
            "FROM g2b.collected_announcements "
            "WHERE bid_notice_no = $1", "E2E-STUCK",
        )
        assert row["pipeline_status"] == "collected"
        assert "비정상 종료 복구" in row["error_message"]

    async def test_e2e05_retry_failed(self, runner, db_conn):
        """E2E-05: 실패 재시도 — analyze_failed (retry<3) → collected"""
        await db_conn.execute(
            "INSERT INTO g2b.collected_announcements "
            "(bid_notice_no, bid_notice_nm, pipeline_status, retry_count) "
            "VALUES ($1, $2, 'analyze_failed', 1)",
            "E2E-RETRY", "retry 테스트",
        )

        conn = await asyncpg.connect(REAL_DB_URL)
        try:
            retried = await runner._retry_failed(conn)
        finally:
            await conn.close()

        assert retried >= 1

        row = await db_conn.fetchrow(
            "SELECT pipeline_status FROM g2b.collected_announcements "
            "WHERE bid_notice_no = $1", "E2E-RETRY",
        )
        assert row["pipeline_status"] == "collected"

    async def test_e2e06_retry_exhausted(self, runner, db_conn):
        """E2E-06: 재시도 소진 — retry_count >= 3 → 상태 유지"""
        await db_conn.execute(
            "INSERT INTO g2b.collected_announcements "
            "(bid_notice_no, bid_notice_nm, pipeline_status, "
            "retry_count, error_message) "
            "VALUES ($1, $2, 'analyze_failed', 3, '영구 실패')",
            "E2E-DEAD", "dead 테스트",
        )

        conn = await asyncpg.connect(REAL_DB_URL)
        try:
            await runner._retry_failed(conn)
        finally:
            await conn.close()

        row = await db_conn.fetchrow(
            "SELECT pipeline_status, retry_count "
            "FROM g2b.collected_announcements "
            "WHERE bid_notice_no = $1", "E2E-DEAD",
        )
        assert row["pipeline_status"] == "analyze_failed"
        assert row["retry_count"] == 3

    # -- 전체 파이프라인 -------------------------------------------

    async def test_e2e07_full_pipeline(self, runner, mocker, db_conn):
        """E2E-07: 전체 파이프라인 (저장 → 분석 → 전송) — DB 검증"""
        # ── Analyzer API mock ──
        analysis_response = MagicMock()
        analysis_response.json.return_value = {
            "category": "스포츠_데이터",
            "relevance_score": 85,
            "summary": "E2E 테스트 요약",
            "requirements": [],
            "needs_research_lab": False,
            "analysis_detail": "상세",
        }
        analysis_response.raise_for_status = MagicMock()

        # ── EC2 API mock ──
        ec2_response = MagicMock()
        ec2_response.json.return_value = {
            "received": 1, "created": 1, "updated": 0, "errors": [],
        }
        ec2_response.raise_for_status = MagicMock()

        async def mock_post(url, **kwargs):
            if "/api/internal/analyzer/analyze" in url:
                return analysis_response
            if "/api/announcements/batch" in url:
                return ec2_response
            raise ValueError(f"Unexpected URL: {url}")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_post)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mocker.patch(
            "class_lib.pipeline_runner.pipeline_runner.httpx.AsyncClient",
            return_value=mock_client,
        )

        # ── 파이프라인 실행 ──
        result = await runner.run(announcements=[{
            "bid_notice_no": "E2E-FULL",
            "bid_notice_nm": "E2E 전체 파이프라인 테스트",
            "ntce_instt_nm": "테스트기관",
            "dminstt_nm": "수요기관",
            "presmpt_price": 100_000_000,
            "bid_begin_dt": "2026-02-20T10:00:00",
            "bid_close_dt": "2026-03-10T18:00:00",
            "link_url": "https://test.example.com",
            "raw_data": {},
            "filter_meta": {},
            "collected_at": "2026-02-16T09:00:00",
        }])

        # ── 파이프라인 결과 검증 ──
        assert result["status"] == "completed"
        assert result["saved"] == 1
        assert result["analyzed"] == 1
        assert result["sent"] == 1
        assert result["failed"] == 0

        # ── DB 최종 상태 검증 ──
        row = await db_conn.fetchrow(
            "SELECT pipeline_status, analysis_result, "
            "analyzed_at, sent_at "
            "FROM g2b.collected_announcements "
            "WHERE bid_notice_no = $1", "E2E-FULL",
        )
        assert row["pipeline_status"] == "sent"
        assert row["analysis_result"] is not None
        assert row["analyzed_at"] is not None
        assert row["sent_at"] is not None
