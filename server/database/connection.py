"""데이터베이스 연결 관리

async engine + session + DDL 초기화를 담당한다.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from config.config import Config
from models.announcement import Base


_engine = None
_async_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        config = Config()
        _engine = create_async_engine(
            config.async_database_url,
            connect_args={"server_settings": {"search_path": "g2b,public"}},
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=(config.app_env not in ("production", "prod")),
        )
    return _engine


def _get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


async def get_session():
    """FastAPI Depends 용 세션 제너레이터"""
    factory = _get_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """DDL 실행 — 스키마, 테이블, 인덱스, 트리거 생성"""
    engine = _get_engine()
    async with engine.begin() as conn:
        # 스키마 생성
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS g2b"))

        # pg_trgm 확장
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

        # 테이블 생성 (SQLAlchemy 메타데이터 기반)
        await conn.run_sync(Base.metadata.create_all)

        # updated_at 자동 갱신 트리거
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION g2b.update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))

        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_announcements_updated_at'
                ) THEN
                    CREATE TRIGGER trg_announcements_updated_at
                        BEFORE UPDATE ON g2b.announcements
                        FOR EACH ROW
                        EXECUTE FUNCTION g2b.update_updated_at_column();
                END IF;
            END
            $$
        """))

        # 부분 인덱스 (SQLAlchemy __table_args__로 정의하기 어려운 것들)
        partial_indexes = [
            """
            CREATE INDEX IF NOT EXISTS idx_announcements_score_high
                ON g2b.announcements(relevance_score DESC)
                WHERE relevance_score >= 60
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_announcements_pending
                ON g2b.announcements(collected_at)
                WHERE status = 'pending'
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_announcements_active
                ON g2b.announcements(bid_close_dt)
                WHERE status NOT IN ('archived', 'excluded')
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_announcements_notion_pending
                ON g2b.announcements(relevance_score DESC)
                WHERE relevance_score >= 60 AND notion_page_id IS NULL
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_announcements_bid_notice_nm_gin
                ON g2b.announcements USING GIN (bid_notice_nm gin_trgm_ops)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_announcements_summary_gin
                ON g2b.announcements USING GIN (summary gin_trgm_ops)
            """,
        ]
        for ddl in partial_indexes:
            await conn.execute(text(ddl))


async def check_db() -> bool:
    """DB 연결 헬스체크"""
    engine = _get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def dispose_engine() -> None:
    """엔진 종료 (앱 shutdown 시 호출)"""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
