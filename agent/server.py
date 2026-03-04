"""FastAPI 앱 정의 + lifespan + 라우터 등록

uvicorn의 lifespan 이벤트를 활용하여 APScheduler와 FastAPI가
동일 asyncio 이벤트 루프에서 동작하도록 한다.

Startup:
    1. setup_logger()                  — loguru 전역 설정
    2. G2BService.ensure_tables()       — collector_history 테이블
    3. PipelineRunner.ensure_tables()   — collected_announcements 테이블
    4. CollectorScheduler.start()       — APScheduler 크론 등록 + 시작
    5. collect_and_filter()             — 서버 기동 완료 후 백그라운드 1회 수집

Shutdown:
    1. scheduler.stop()                 — APScheduler 중지

참조:
- docs/pipeline/04-entry-point.md §2.4, §3 : lifespan 방식 설계
- docs/pipeline/02-internal-api.md §2, §3 : 서버 구성 + 라우터 구조
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from config.logger import setup_logger
from class_lib.profile.profile_loader import get_profile
from class_lib.collector.collector_scheduler import CollectorScheduler
from class_lib.collector.g2b_service import G2BService
from class_lib.pipeline_runner.pipeline_runner import PipelineRunner
from class_lib.collector.router import router as collector_router
from class_lib.pipeline_runner.router import router as pipeline_router
# v2: analyzer_router 비활성화 (분석은 Cowork에서 수행)
# from class_lib.analyzer.router import router as analyzer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 lifespan 이벤트 — 시작/종료 시 실행"""
    # ── Startup ──

    # 1. loguru 전역 설정 (진입점 무관하게 여기서 통일)
    setup_logger(level="INFO")
    logger.info("G2B Agent 시작")

    # 1.5. 프로필 로드 + 검증 (fail-fast)
    profile = get_profile()
    logger.info(f"Analysis Profile: {profile.profile_id} ({profile.company.name})")

    # 2. DB 테이블 보장
    g2b_service = G2BService()
    await g2b_service.ensure_tables()

    pipeline_runner = PipelineRunner()
    await pipeline_runner.ensure_tables()

    # 3. APScheduler 시작
    scheduler = CollectorScheduler()
    scheduler.start()
    app.state.scheduler = scheduler

    logger.info("초기화 완료 — 수집 스케줄러 + API 서버 가동")

    # 4. 서버 기동 완료 후 1회 수집 실행 (백그라운드 태스크)
    #    yield 이후 FastAPI가 HTTP 수신 가능 → create_task로 지연 실행
    asyncio.create_task(scheduler.collect_and_filter())

    yield

    # ── Shutdown ──
    scheduler.stop()
    logger.info("G2B Agent 종료")


app = FastAPI(
    title="G2B Agent Internal API",
    description="나라장터 공고 수집·분석 에이전트 내부 API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# 라우터 등록
app.include_router(collector_router, prefix="/api/internal/collector", tags=["Collector"])
app.include_router(pipeline_router, prefix="/api/internal/pipeline", tags=["Pipeline"])
# v2: analyzer_router 비활성화 (분석은 Cowork에서 수행)
# app.include_router(analyzer_router, prefix="/api/internal/analyzer", tags=["Analyzer"])
