"""Server lifespan 단위 테스트 (2건)

G2BService, PipelineRunner, CollectorScheduler mock 사용.
v2: get_profile mock 추가, collect_and_filter AsyncMock 처리.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from server import lifespan


class TestLifespan:
    async def test_sv01_startup(self, mocker):
        """SV-01: startup — ensure_tables + scheduler.start 호출"""
        mock_g2b = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_scheduler = MagicMock()
        mock_scheduler.collect_and_filter = AsyncMock()

        mocker.patch("server.G2BService", return_value=mock_g2b)
        mocker.patch("server.PipelineRunner", return_value=mock_pipeline)
        mocker.patch("server.CollectorScheduler", return_value=mock_scheduler)
        mocker.patch("server.get_profile", return_value=MagicMock(
            profile_id="test", company=MagicMock(name="TestCo"),
        ))

        app = FastAPI()

        async with lifespan(app):
            mock_g2b.ensure_tables.assert_called_once()
            mock_pipeline.ensure_tables.assert_called_once()
            mock_scheduler.start.assert_called_once()
            assert app.state.scheduler is mock_scheduler

    async def test_sv02_shutdown(self, mocker):
        """SV-02: shutdown — scheduler.stop 호출"""
        mock_g2b = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_scheduler = MagicMock()
        mock_scheduler.collect_and_filter = AsyncMock()

        mocker.patch("server.G2BService", return_value=mock_g2b)
        mocker.patch("server.PipelineRunner", return_value=mock_pipeline)
        mocker.patch("server.CollectorScheduler", return_value=mock_scheduler)
        mocker.patch("server.get_profile", return_value=MagicMock(
            profile_id="test", company=MagicMock(name="TestCo"),
        ))

        app = FastAPI()

        async with lifespan(app):
            pass

        mock_scheduler.stop.assert_called_once()
