"""나라장터 마켓 인텔리전스 서버 진입점

실행:
    cd server
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from apps.announcements.router import router as announcements_router
from apps.auth.router import router as auth_router
from apps.exceptions import AppException, app_exception_handler
from apps.files.router import router as files_router
from apps.health.router import router as health_router
from config.config import Config
from config.logger import setup_logger
from database.connection import dispose_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 생명주기"""
    # startup
    setup_logger()
    logger.info("서버 시작 — DB 초기화 중...")
    try:
        await init_db()
        logger.info("DB 초기화 완료")
    except Exception as e:
        logger.error(f"DB 초기화 실패: {e}")
        raise

    yield

    # shutdown
    logger.info("서버 종료 — 리소스 정리 중...")
    await dispose_engine()
    logger.info("서버 종료 완료")


config = Config()

app = FastAPI(
    title="나라장터 마켓 인텔리전스 API",
    description="나라장터(G2B) 공공조달 공고 수집/분석 플랫폼 REST API",
    version="1.0.0",
    docs_url="/api/docs" if config.app_env != "production" else None,
    redoc_url="/api/redoc" if config.app_env != "production" else None,
    openapi_url="/api/openapi.json" if config.app_env != "production" else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 예외 핸들러
app.add_exception_handler(AppException, app_exception_handler)

# 라우터 등록
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(announcements_router, prefix="/api")
app.include_router(files_router, prefix="/api")
