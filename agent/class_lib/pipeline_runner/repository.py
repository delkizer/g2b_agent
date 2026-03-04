"""Pipeline 도메인 — DB 접근 계층

g2b.collected_announcements 테이블의 CRUD + 상태 갱신 + DDL.
PipelineRunner가 이 모듈의 함수를 호출하여 DB 접근을 수행한다.

참조:
- docs/pipeline/03-db-schema.md : DDL, 인덱스, 트리거, 쿼리 카탈로그
- docs/pipeline/04-entry-point.md §4.4 : _recover_stuck 설계
"""

import json
from datetime import datetime, timezone

import asyncpg
from loguru import logger

from class_lib.pipeline_runner.utils import parse_timestamptz


# ── DDL ────────────────────────────────────────────────


async def ensure_tables(conn: asyncpg.Connection) -> None:
    """collected_announcements 테이블 + 인덱스 + 트리거 생성 (IF NOT EXISTS)

    03-db-schema.md 2.1, 2.2, 2.3절 DDL을 완전히 포함.
    """
    # 스키마 생성
    await conn.execute("CREATE SCHEMA IF NOT EXISTS g2b;")

    # 2.1 메인 테이블 DDL
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS g2b.collected_announcements (
            id                  SERIAL PRIMARY KEY,
            bid_notice_no       VARCHAR(50) NOT NULL UNIQUE,

            -- 원본 데이터 (나라장터 API)
            bid_notice_nm       TEXT NOT NULL,
            ntce_instt_nm       VARCHAR(200) DEFAULT '',
            dminstt_nm          VARCHAR(200) DEFAULT '',
            presmpt_price       BIGINT DEFAULT 0,
            bid_begin_dt        TIMESTAMPTZ,
            bid_close_dt        TIMESTAMPTZ,
            link_url            TEXT DEFAULT '',
            raw_data            JSONB DEFAULT '{}',

            -- 필터 메타데이터
            filter_meta         JSONB DEFAULT '{}',

            -- 첨부파일 URL (v2)
            attachment_urls     JSONB DEFAULT '[]',

            -- 분석 결과 (v2: deprecated — 기존 데이터 호환용 유지)
            analysis_result     JSONB,

            -- 파이프라인 상태
            pipeline_status     VARCHAR(20) NOT NULL DEFAULT 'collected',
            error_message       TEXT DEFAULT '',
            retry_count         SMALLINT NOT NULL DEFAULT 0,

            -- 시각
            collected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            analyzed_at         TIMESTAMPTZ,
            sent_at             TIMESTAMPTZ,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- 제약조건 (v2: analyzing/analyzed/analyze_failed 제거)
            CONSTRAINT ck_pipeline_status CHECK (
                pipeline_status IN (
                    'collected',
                    'sending', 'sent',
                    'send_failed'
                )
            ),
            CONSTRAINT ck_retry_count CHECK (retry_count >= 0)
        );
    """)

    # 2.2 인덱스
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ca_pipeline_status
            ON g2b.collected_announcements(pipeline_status);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ca_collected_at
            ON g2b.collected_announcements(collected_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ca_status_retry
            ON g2b.collected_announcements(pipeline_status, retry_count)
            WHERE pipeline_status IN ('send_failed');
    """)

    # 2.3 updated_at 자동 갱신 트리거
    await conn.execute("""
        CREATE OR REPLACE FUNCTION g2b.update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_ca_updated_at
            ON g2b.collected_announcements;
    """)

    await conn.execute("""
        CREATE TRIGGER trg_ca_updated_at
            BEFORE UPDATE ON g2b.collected_announcements
            FOR EACH ROW
            EXECUTE FUNCTION g2b.update_updated_at();
    """)

    logger.info("DB 테이블 확인 완료 (g2b.collected_announcements)")


# ── 저장 ───────────────────────────────────────────────


async def save_announcements(
    conn: asyncpg.Connection, announcements: list[dict]
) -> tuple[int, int]:
    """수신 공고 DB 저장 (ON CONFLICT SKIP)

    03-db-schema.md 5.1절 쿼리 카탈로그 참조.

    Returns:
        (saved, skipped) — 신규 INSERT 건수, 중복 SKIP 건수
    """
    saved = 0

    for ann in announcements:
        result = await conn.execute(
            """
            INSERT INTO g2b.collected_announcements (
                bid_notice_no, bid_notice_nm, ntce_instt_nm, dminstt_nm,
                presmpt_price, bid_begin_dt, bid_close_dt, link_url,
                raw_data, filter_meta, attachment_urls,
                pipeline_status, collected_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                'collected', $12
            )
            ON CONFLICT (bid_notice_no) DO NOTHING;
            """,
            ann.get("bid_notice_no", ""),
            ann.get("bid_notice_nm", ""),
            ann.get("ntce_instt_nm", ""),
            ann.get("dminstt_nm", ""),
            ann.get("presmpt_price", 0),
            parse_timestamptz(ann.get("bid_begin_dt")),
            parse_timestamptz(ann.get("bid_close_dt")),
            ann.get("link_url", ""),
            json.dumps(ann.get("raw_data", {}), ensure_ascii=False),
            json.dumps(ann.get("filter_meta", {}), ensure_ascii=False),
            json.dumps(ann.get("attachment_urls", []), ensure_ascii=False),
            parse_timestamptz(ann.get("collected_at")) or datetime.now(timezone.utc),
        )
        count = int(result.split()[-1])
        saved += count

    skipped = len(announcements) - saved
    return saved, skipped


# ── 조회 ───────────────────────────────────────────────


async def fetch_by_status(conn: asyncpg.Connection, status: str) -> list[dict]:
    """pipeline_status로 공고 조회

    03-db-schema.md 5.2절 (collected), 5.6절 (analyzed) 참조.

    Returns:
        공고 행 dict 리스트
    """
    rows = await conn.fetch(
        """
        SELECT id, bid_notice_no, bid_notice_nm, ntce_instt_nm, dminstt_nm,
               presmpt_price, bid_begin_dt, bid_close_dt, link_url,
               raw_data, filter_meta, attachment_urls, pipeline_status,
               retry_count, collected_at, sent_at
        FROM g2b.collected_announcements
        WHERE pipeline_status = $1
        ORDER BY collected_at ASC;
        """,
        status,
    )

    result = []
    for row in rows:
        d = dict(row)
        for jsonb_col in ("raw_data", "filter_meta", "attachment_urls"):
            val = d.get(jsonb_col)
            if isinstance(val, str):
                d[jsonb_col] = json.loads(val)
        result.append(d)
    return result


# ── 상태 갱신 ──────────────────────────────────────────


async def update_status(
    conn: asyncpg.Connection, bid_notice_no: str, updates: dict
) -> None:
    """공고 상태 갱신 (pipeline_status, analysis_result 등)

    동적 UPDATE: updates dict의 키에 따라 SET 절 구성.
    retry_count_increment=True이면 retry_count = retry_count + 1로 처리.
    """
    set_clauses = []
    params = []
    param_idx = 1

    retry_increment = updates.pop("retry_count_increment", False)

    for key, value in updates.items():
        param_idx += 1
        if key == "analysis_result":
            set_clauses.append(f"{key} = ${param_idx}::jsonb")
        else:
            set_clauses.append(f"{key} = ${param_idx}")
        params.append(value)

    if retry_increment:
        set_clauses.append("retry_count = retry_count + 1")

    if not set_clauses:
        return

    sql = f"""
        UPDATE g2b.collected_announcements
        SET {', '.join(set_clauses)}
        WHERE bid_notice_no = $1;
    """

    await conn.execute(sql, bid_notice_no, *params)


# ── 복구/재시도 ────────────────────────────────────────


async def recover_stuck(conn: asyncpg.Connection) -> int:
    """비정상 종료로 sending에 머문 공고를 원복

    v2: analyzing 제거. sending → collected로 원복.

    Returns:
        복구된 건수
    """
    result = await conn.execute("""
        UPDATE g2b.collected_announcements
        SET pipeline_status = 'collected',
        error_message = '비정상 종료 복구'
        WHERE pipeline_status = 'sending';
    """)
    count = int(result.split()[-1])
    if count > 0:
        logger.warning(f"비정상 종료 복구: {count}건 원복")
    return count


async def retry_failed(conn: asyncpg.Connection) -> int:
    """실패 건 상태 원복

    v2 원복 규칙:
    - send_failed (retry_count < 3) → collected
    retry_count는 원복 시 증가하지 않는다.

    Returns:
        원복된 건수
    """
    result = await conn.execute("""
        UPDATE g2b.collected_announcements
        SET pipeline_status = 'collected',
            error_message = ''
        WHERE pipeline_status = 'send_failed'
          AND retry_count < 3;
    """)
    retried = int(result.split()[-1])

    # 최종 실패 건 CRITICAL 로그
    critical_rows = await conn.fetch("""
        SELECT bid_notice_no, pipeline_status, retry_count, error_message
        FROM g2b.collected_announcements
        WHERE pipeline_status = 'send_failed'
          AND retry_count >= 3;
    """)

    for row in critical_rows:
        logger.critical(
            f"최종 실패 (수동 개입 필요): "
            f"bid_notice_no={row['bid_notice_no']}, "
            f"status={row['pipeline_status']}, "
            f"retry_count={row['retry_count']}, "
            f"error={row['error_message']}"
        )

    return retried
