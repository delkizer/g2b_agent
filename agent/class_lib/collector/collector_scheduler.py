"""수집 스케줄러 (오케스트레이션)

APScheduler로 수집 주기를 관리하고 G2BService + KeywordFilter를 오케스트레이션한다.

참조:
- docs/collector/01-collector-overview.md : 3.4절 CollectorScheduler 설계
- agent/class_lib/collector/g2b_service.py : G2BService 인터페이스
- agent/class_lib/collector/keyword_filter.py : KeywordFilter.filter() 시그니처
- agent/class_lib/collector/schemas.py : FilteredAnnouncement, CollectorHistory
"""

import time
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from config.config import Config
from class_lib.collector.g2b_service import G2BService
from class_lib.collector.keyword_filter import KeywordFilter
from class_lib.collector.schemas import FilteredAnnouncement, CollectorHistory


class CollectorScheduler:
    """수집 스케줄러 (오케스트레이션)

    APScheduler AsyncIOScheduler + MemoryJobStore로 주기적 수집을 관리하고,
    G2BService(수집) → KeywordFilter(필터링) 파이프라인을 실행한다.

    Config는 내부에서 직접 생성 (외부 주입 금지).

    Attributes:
        config: 설정 인스턴스
        logger: 로거 인스턴스
        scheduler: APScheduler AsyncIOScheduler
        g2b_service: 나라장터 수집 서비스
        keyword_filter: 키워드 필터
    """

    OPERATION = "bid_announcement"
    DEFAULT_LOOKBACK_HOURS = 24

    def __init__(self, logger):
        self.config = Config()
        self.logger = logger

        # APScheduler (MemoryJobStore — SQLAlchemy 의존 제거)
        jobstores = {"default": MemoryJobStore()}
        self.scheduler = AsyncIOScheduler(jobstores=jobstores)

        # 서비스 인스턴스
        self.g2b_service = G2BService(logger)
        self.keyword_filter = KeywordFilter(logger)

        self.logger.info(
            f"CollectorScheduler 초기화 완료 "
            f"(수집 주기: {self.config.schedule_interval_minutes}분)"
        )

    # ─── 공개 메서드 ──────────────────────────────────────

    async def collect_and_filter(self) -> list[FilteredAnnouncement]:
        """수집 + 필터링 실행 (스케줄러에서 호출)

        1. g2b_service.get_last_collected_dt()로 시작 시점 결정 (없으면 now - 24h)
        2. g2b_service.fetch_announcements(start_dt, end_dt)로 수집
        3. keyword_filter.filter(announcements)로 필터링
        4. g2b_service.save_history()로 이력 기록 (성공/실패 모두)
        5. list[FilteredAnnouncement] 반환

        Returns:
            필터 통과 공고 리스트 (실패 시 빈 리스트)
        """
        start_time = time.perf_counter()
        now = datetime.now()

        # 시작 시점 결정
        last_dt = await self.g2b_service.get_last_collected_dt(self.OPERATION)
        start_dt = last_dt if last_dt else (now - timedelta(hours=self.DEFAULT_LOOKBACK_HOURS))
        end_dt = now

        self.logger.info(
            f"수집 시작: {start_dt.strftime('%Y-%m-%d %H:%M')} ~ "
            f"{end_dt.strftime('%Y-%m-%d %H:%M')} "
            f"({'이력 기반' if last_dt else '최초 실행 (24h 전부터)'})"
        )

        try:
            # 수집
            announcements = await self.g2b_service.fetch_announcements(start_dt, end_dt)

            # 필터링
            filtered = self.keyword_filter.filter(announcements)

            # 소요 시간
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # 이력 기록 (성공)
            history = CollectorHistory(
                operation=self.OPERATION,
                collected_at=now,
                collected_end_dt=end_dt,
                total_count=len(announcements),
                filtered_count=len(filtered),
                duration_ms=elapsed_ms,
                status="success",
                error_message="",
            )
            await self.g2b_service.save_history(history)

            self.logger.info(
                f"수집 완료: 전체={len(announcements)}건, "
                f"필터 통과={len(filtered)}건, "
                f"{elapsed_ms}ms 소요"
            )

            return filtered

        except Exception as e:
            # Graceful Degradation: 예외 전파하지 않음
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            self.logger.error(f"수집/필터 중 예외 발생: {e}", exc_info=True)

            # 이력 기록 (실패)
            history = CollectorHistory(
                operation=self.OPERATION,
                collected_at=now,
                collected_end_dt=end_dt,
                total_count=0,
                filtered_count=0,
                duration_ms=elapsed_ms,
                status="failure",
                error_message=str(e),
            )
            await self.g2b_service.save_history(history)

            return []

    async def run_once(self) -> list[FilteredAnnouncement]:
        """수동 실행 (테스트/디버그용)

        collect_and_filter()를 1회 실행하고 결과를 반환한다.
        스케줄러 등록 없이 즉시 실행할 때 사용.

        Returns:
            필터 통과 공고 리스트
        """
        self.logger.info("수동 수집 실행 (run_once)")
        return await self.collect_and_filter()

    def start(self) -> None:
        """크론 스케줄 시작

        Config.schedule_interval_minutes 간격으로 collect_and_filter를 반복 실행한다.
        시작 전 ensure_tables()를 위해 별도 호출이 필요하며,
        start() 호출 시점에 스케줄러가 즉시 구동된다.
        """
        self.scheduler.add_job(
            self.collect_and_filter,
            "interval",
            minutes=self.config.schedule_interval_minutes,
            id="collect_and_filter",
            replace_existing=True,
        )
        self.scheduler.start()
        self.logger.info(
            f"CollectorScheduler 시작 "
            f"(주기: {self.config.schedule_interval_minutes}분)"
        )

    def stop(self) -> None:
        """스케줄러 중지

        실행 중인 모든 Job을 중지하고 스케줄러를 종료한다.
        """
        self.scheduler.shutdown(wait=False)
        self.logger.info("CollectorScheduler 중지 완료")

    # ─── 초기화 헬퍼 ──────────────────────────────────────

    async def ensure_tables(self) -> None:
        """DB 테이블 생성 (IF NOT EXISTS)

        g2b_service.ensure_tables()를 위임 호출한다.
        start() 전에 호출하여 테이블 존재를 보장한다.
        """
        await self.g2b_service.ensure_tables()
