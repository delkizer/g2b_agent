"""CollectorScheduler 단위 테스트 (7건)

G2BService, KeywordFilter mock.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from class_lib.collector.collector_scheduler import CollectorScheduler
from class_lib.collector.schemas import CollectedAnnouncement, FilteredAnnouncement, FilterMeta


# ============================================================
# CS-01~02: collect_and_filter 시작 시점 결정
# ============================================================


class TestCollectAndFilterStartPoint:
    @pytest.fixture
    def scheduler(self, mocker):
        sched = CollectorScheduler()
        # mock 서비스들
        sched.g2b_service = MagicMock()
        sched.g2b_service.get_last_collected_dt = AsyncMock()
        sched.g2b_service.fetch_announcements = AsyncMock(return_value=[])
        sched.g2b_service.save_history = AsyncMock()
        sched.keyword_filter = MagicMock()
        sched.keyword_filter.filter = MagicMock(return_value=[])
        return sched

    async def test_cs01_history_based(self, scheduler):
        """CS-01: 이력 기반 시작점 — get_last_collected_dt 반환값 사용"""
        last_dt = datetime(2026, 2, 15, 12, 0)
        scheduler.g2b_service.get_last_collected_dt.return_value = last_dt

        await scheduler.collect_and_filter()

        # fetch_announcements의 start_dt가 last_dt인지 확인
        call_args = scheduler.g2b_service.fetch_announcements.call_args
        assert call_args[0][0] == last_dt  # start_dt

    async def test_cs02_first_run(self, scheduler):
        """CS-02: 최초 실행 — get_last_collected_dt=None → 24시간 전"""
        scheduler.g2b_service.get_last_collected_dt.return_value = None

        before = datetime.now()
        await scheduler.collect_and_filter()

        call_args = scheduler.g2b_service.fetch_announcements.call_args
        start_dt = call_args[0][0]
        # start_dt가 대략 24시간 전인지 확인 (±1분 허용)
        diff_hours = (before - start_dt).total_seconds() / 3600
        assert 23.9 < diff_hours < 24.1


# ============================================================
# CS-03: 성공 이력 저장
# ============================================================


class TestSuccessHistory:
    async def test_cs03_success_history(self):
        """CS-03: 성공 시 이력 저장 (status='success')"""
        sched = CollectorScheduler()
        sched.g2b_service = MagicMock()
        sched.g2b_service.get_last_collected_dt = AsyncMock(return_value=None)

        collected = [
            CollectedAnnouncement(bid_notice_no="001", bid_notice_nm="테스트"),
            CollectedAnnouncement(bid_notice_no="002", bid_notice_nm="테스트2"),
        ]
        sched.g2b_service.fetch_announcements = AsyncMock(return_value=collected)
        sched.g2b_service.fetch_attachment_urls = AsyncMock(return_value=[])
        sched.g2b_service.save_history = AsyncMock()

        filtered = [
            FilteredAnnouncement(
                bid_notice_no="001",
                bid_notice_nm="테스트",
                filter_meta=FilterMeta(matched_keywords=["스포츠"]),
            )
        ]
        sched.keyword_filter = MagicMock()
        sched.keyword_filter.filter = MagicMock(return_value=filtered)

        result = await sched.collect_and_filter()

        assert len(result) == 1
        # save_history 호출 검증
        history_arg = sched.g2b_service.save_history.call_args[0][0]
        assert history_arg.status == "success"
        assert history_arg.total_count == 2
        assert history_arg.filtered_count == 1


# ============================================================
# CS-04~05: 실패 시 Graceful Degradation
# ============================================================


class TestFailureGraceful:
    async def test_cs04_fetch_failure(self):
        """CS-04: fetch 실패 → 빈 리스트 반환 + failure 이력"""
        sched = CollectorScheduler()
        sched.g2b_service = MagicMock()
        sched.g2b_service.get_last_collected_dt = AsyncMock(return_value=None)
        sched.g2b_service.fetch_announcements = AsyncMock(side_effect=Exception("네트워크 오류"))
        sched.g2b_service.save_history = AsyncMock()
        sched.keyword_filter = MagicMock()

        result = await sched.collect_and_filter()

        assert result == []
        history_arg = sched.g2b_service.save_history.call_args[0][0]
        assert history_arg.status == "failure"
        assert "네트워크 오류" in history_arg.error_message

    async def test_cs05_filter_failure(self):
        """CS-05: filter 실패 → 빈 리스트 반환 + failure 이력"""
        sched = CollectorScheduler()
        sched.g2b_service = MagicMock()
        sched.g2b_service.get_last_collected_dt = AsyncMock(return_value=None)
        sched.g2b_service.fetch_announcements = AsyncMock(return_value=[])
        sched.g2b_service.save_history = AsyncMock()
        sched.keyword_filter = MagicMock()
        sched.keyword_filter.filter = MagicMock(side_effect=Exception("필터 에러"))

        result = await sched.collect_and_filter()

        assert result == []
        history_arg = sched.g2b_service.save_history.call_args[0][0]
        assert history_arg.status == "failure"


# ============================================================
# CS-06~07: start / stop
# ============================================================


class TestStartStop:
    def test_cs06_start(self, mocker):
        """CS-06: start() → job 등록 + scheduler.start()"""
        sched = CollectorScheduler()
        mock_add_job = mocker.patch.object(sched.scheduler, "add_job")
        mock_start = mocker.patch.object(sched.scheduler, "start")

        sched.start()

        mock_add_job.assert_called_once()
        call_kwargs = mock_add_job.call_args
        assert call_kwargs[1]["id"] == "collect_and_filter"
        mock_start.assert_called_once()

    def test_cs07_stop(self, mocker):
        """CS-07: stop() → scheduler.shutdown(wait=False)"""
        sched = CollectorScheduler()
        mock_shutdown = mocker.patch.object(sched.scheduler, "shutdown")

        sched.stop()

        mock_shutdown.assert_called_once_with(wait=False)
