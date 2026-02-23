"""Pipeline 라우터 단위 테스트 (3건)

FastAPI TestClient + PipelineRunner mock 사용.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from class_lib.pipeline_runner.router import router


@pytest.fixture
def app():
    """테스트용 FastAPI 앱"""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internal/pipeline")
    return test_app


class TestPipelineRouter:
    async def test_rt01_run_success(self, app, mocker):
        """RT-01: POST /run 정상 → completed"""
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(return_value={
            "status": "completed", "saved": 1, "analyzed": 1, "sent": 1,
        })
        mocker.patch(
            "class_lib.pipeline_runner.router._get_runner",
            return_value=mock_runner,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/internal/pipeline/run",
                json={"announcements": [{"bid_notice_no": "TEST-001"}]},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    async def test_rt02_empty_body(self, app, mocker):
        """RT-02: POST /run 빈 body → PipelineRunner에 빈 리스트 전달"""
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(return_value={"status": "no_items"})
        mocker.patch(
            "class_lib.pipeline_runner.router._get_runner",
            return_value=mock_runner,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/internal/pipeline/run",
                content=b"{}",
                headers={"content-type": "application/json"},
            )

        assert response.status_code == 200
        mock_runner.run.assert_called_once_with(announcements=[])

    async def test_rt03_exception(self, app, mocker):
        """RT-03: POST /run 예외 → error 응답"""
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(
            side_effect=RuntimeError("DB 연결 실패"),
        )
        mocker.patch(
            "class_lib.pipeline_runner.router._get_runner",
            return_value=mock_runner,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/internal/pipeline/run",
                json={"announcements": []},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "error"
