"""G2BService 통합 테스트 (3건)

실제 PostgreSQL DB 필요. @pytest.mark.integration.
Docker: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15

실행: pytest -m integration -v
"""

from datetime import datetime

import pytest

from class_lib.collector.g2b_service import G2BService
from class_lib.collector.schemas import CollectorHistory


pytestmark = pytest.mark.integration


class TestG2BServiceIntegration:
    @pytest.fixture
    async def service(self):
        """통합 테스트용 G2BService (실제 DB 연결)"""
        svc = G2BService()
        await svc.ensure_tables()
        return svc

    async def test_gi01_ensure_tables(self):
        """GI-01: ensure_tables → 스키마 + 테이블 생성 (오류 없음)"""
        svc = G2BService()
        # 두 번 호출해도 IF NOT EXISTS로 안전
        await svc.ensure_tables()
        await svc.ensure_tables()

    async def test_gi02_save_and_get_last_collected_dt(self, service):
        """GI-02: save_history + get_last_collected_dt 라운드트립"""
        now = datetime.now()
        history = CollectorHistory(
            operation="test_integration",
            collected_at=now,
            collected_end_dt=now,
            total_count=10,
            filtered_count=3,
            duration_ms=500,
            status="success",
        )
        await service.save_history(history)

        last_dt = await service.get_last_collected_dt("test_integration")
        assert last_dt is not None
        # 타임스탬프 비교 (초 단위까지)
        assert last_dt.year == now.year
        assert last_dt.month == now.month
        assert last_dt.day == now.day

    async def test_gi03_no_history_returns_none(self, service):
        """GI-03: 이력 없는 operation → None 반환"""
        result = await service.get_last_collected_dt("nonexistent_operation_xyz")
        assert result is None
