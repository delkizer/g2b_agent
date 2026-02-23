"""Analyzer 라우터 단위 테스트 (2건)

FastAPI TestClient + ClaudeClient mock 사용.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from class_lib.analyzer.router import router


@pytest.fixture
def app():
    """테스트용 FastAPI 앱"""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internal/analyzer")
    return test_app


class TestAnalyzerRouter:
    async def test_rt04_analyze_success(self, app, mocker):
        """RT-04: POST /analyze 정상 → 분석 결과 반환"""
        mock_client = AsyncMock()
        mock_client.analyze_announcement = AsyncMock(return_value={
            "category": "스포츠_데이터",
            "relevance_score": 85,
        })
        mocker.patch(
            "class_lib.analyzer.router._get_client",
            return_value=mock_client,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/internal/analyzer/analyze",
                json={
                    "bid_notice_no": "TEST-001",
                    "bid_notice_nm": "테스트 공고",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "스포츠_데이터"
        assert data["relevance_score"] == 85

    async def test_rt05_analyze_failure(self, app, mocker):
        """RT-05: POST /analyze 실패 → error 응답"""
        mock_client = AsyncMock()
        mock_client.analyze_announcement = AsyncMock(return_value={})
        mocker.patch(
            "class_lib.analyzer.router._get_client",
            return_value=mock_client,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/internal/analyzer/analyze",
                json={
                    "bid_notice_no": "TEST-001",
                    "bid_notice_nm": "테스트 공고",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "error"
