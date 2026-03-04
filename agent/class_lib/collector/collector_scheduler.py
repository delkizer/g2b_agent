"""수집 스케줄러 (오케스트레이션)

APScheduler로 수집 주기를 관리하고 G2BService + KeywordFilter를 오케스트레이션한다.

참조:
- docs/collector/01-collector-overview.md : 3.4절 CollectorScheduler 설계
- agent/class_lib/collector/g2b_service.py : G2BService 인터페이스
- agent/class_lib/collector/keyword_filter.py : KeywordFilter.filter() 시그니처
- agent/class_lib/collector/schemas.py : FilteredAnnouncement, CollectorHistory
"""

import asyncio
import time
from datetime import datetime, timedelta

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from loguru import logger

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

    def __init__(self):
        self.config = Config()

        # APScheduler (MemoryJobStore — SQLAlchemy 의존 제거)
        jobstores = {"default": MemoryJobStore()}
        self.scheduler = AsyncIOScheduler(jobstores=jobstores)

        # 서비스 인스턴스
        self.g2b_service = G2BService()
        self.keyword_filter = KeywordFilter()

        logger.info(
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

        logger.info(
            f"수집 시작: {start_dt.strftime('%Y-%m-%d %H:%M')} ~ "
            f"{end_dt.strftime('%Y-%m-%d %H:%M')} "
            f"({'이력 기반' if last_dt else '최초 실행 (24h 전부터)'})"
        )

        try:
            # 수집
            announcements = await self.g2b_service.fetch_announcements(start_dt, end_dt)

            # 필터링
            filtered = self.keyword_filter.filter(announcements)

            # v2: 필터 통과 공고의 첨부파일 URL 수집
            if filtered:
                await self._enrich_attachment_urls(filtered)

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

            logger.info(
                f"수집 완료: 전체={len(announcements)}건, "
                f"필터 통과={len(filtered)}건, "
                f"{elapsed_ms}ms 소요"
            )

            # Pipeline에 데이터 전달 (DB 저장은 PipelineRunner가 수행)
            if filtered:
                await self._signal_pipeline(filtered)

            return filtered

        except Exception as e:
            # Graceful Degradation: 예외 전파하지 않음
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            logger.error(f"수집/필터 중 예외 발생: {e}", exc_info=True)

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
        logger.info("수동 수집 실행 (run_once)")
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
        logger.info(
            f"CollectorScheduler 시작 "
            f"(주기: {self.config.schedule_interval_minutes}분)"
        )

    def stop(self) -> None:
        """스케줄러 중지

        실행 중인 모든 Job을 중지하고 스케줄러를 종료한다.
        """
        self.scheduler.shutdown(wait=False)
        logger.info("CollectorScheduler 중지 완료")

    # ─── 첨부파일 URL 수집 (v2) ──────────────────────────

    async def _enrich_attachment_urls(
        self, filtered: list[FilteredAnnouncement]
    ) -> None:
        """필터 통과 공고에 첨부파일 URL 추가 (in-place)

        BidPublicInfoService API로 각 공고의 규격서/e발주 첨부파일 URL을 수집한다.
        실패 시 해당 공고만 빈 리스트 유지 (다른 공고에 영향 없음).

        Args:
            filtered: FilteredAnnouncement 리스트 (in-place 수정)
        """
        total_urls = 0
        for ann in filtered:
            urls = await self.g2b_service.fetch_attachment_urls(ann.bid_notice_no)
            if urls:
                ann.attachment_urls = urls
                total_urls += len(urls)
            # Rate limit (API 호출 간 0.3초 대기)
            await asyncio.sleep(0.3)

        if total_urls > 0:
            logger.info(
                f"첨부파일 URL 수집 완료: {len(filtered)}건 공고, "
                f"총 {total_urls}개 URL"
            )

    # ─── Pipeline 연동 ────────────────────────────────────

    async def _signal_pipeline(self, filtered: list[FilteredAnnouncement]) -> None:
        """PipelineRunner에 필터 통과 공고 전달

        POST /api/internal/pipeline/run
        Body: { "announcements": [FilteredAnnouncement, ...] }
        타임아웃: 300초 (배치 전체 분석 + EC2 전송 시간 고려)

        실패 시: 로그 경고만 남김 (Graceful Degradation)
        다음 스케줄에서 PipelineRunner가 기존 collected 건을 재처리.
        """
        url = f"{self.config.internal_api_base_url}/api/internal/pipeline/run"
        payload = {
            "announcements": [ann.model_dump(mode="json") for ann in filtered]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=300.0)
                result = response.json()
                logger.info(
                    f"Pipeline 전달 완료: status={result.get('status')}, "
                    f"saved={result.get('saved', 0)}, "
                    f"skipped={result.get('skipped', 0)}"
                )
        except httpx.HTTPStatusError as e:
            logger.warning(f"Pipeline API HTTP 에러 ({e.response.status_code}): {e}")
        except httpx.RequestError as e:
            logger.warning(f"Pipeline API 요청 실패: {e}")
        except Exception as e:
            logger.warning(f"Pipeline 전달 중 예외: {e}")

    # ─── 초기화 헬퍼 ──────────────────────────────────────

    async def ensure_tables(self) -> None:
        """DB 테이블 생성 (IF NOT EXISTS)

        g2b_service.ensure_tables()를 위임 호출한다.
        start() 전에 호출하여 테이블 존재를 보장한다.
        """
        await self.g2b_service.ensure_tables()
