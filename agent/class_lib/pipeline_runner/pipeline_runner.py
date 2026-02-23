"""파이프라인 오케스트레이터 (v2 — 비동기 워커)

Collector 완료 신호(POST /api/internal/pipeline/run)를 받아:
1. DB에 공고를 저장하고 즉시 응답 (status: accepted)
2. 백그라운드 워커를 기동하여 분석/전송을 비동기 처리
3. 워커는 건별로 Analyzer API, Send API를 순차 호출
4. 실패 건 재시도 (retry_count < 3)

Config는 내부에서 직접 생성 (외부 주입 금지).
Logger는 module-level import (loguru).

참조:
- docs/pipeline/01-pipeline-overview.md §6 : PipelineRunner 클래스 설계
- docs/pipeline/02-internal-api.md §4, §6 : 내부 API + 워커 설계
- docs/shared/01-data-schema.md : AnalyzedAnnouncement 스키마
"""

import asyncio
import json
import time
from datetime import datetime, timezone

import asyncpg
import httpx
from loguru import logger

from config.config import Config
from class_lib.pipeline_runner import repository
from class_lib.pipeline_runner.utils import serialize_dt


class PipelineRunner:
    """파이프라인 오케스트레이터 (v2 — 비동기 워커)

    run() — 저장 + 워커 기동 (즉시 응답)
    send() — EC2 전송 (독립 API)
    _run_worker() — 백그라운드 코루틴 (분석 + 전송 루프)
    """

    def __init__(self):
        self.config = Config()
        self._running = False  # 워커 실행 중 플래그

    # ── 공개 메서드 ──────────────────────────────────

    async def run(self, announcements: list[dict] | None = None) -> dict:
        """파이프라인 트리거 — 저장 + 워커 기동

        1. 수신 공고 DB 저장 (항상 수행)
        2. 백그라운드 워커 기동 (이미 실행 중이면 스킵)
        3. 즉시 응답 반환

        Returns:
            {"status": "accepted", "saved": N, "skipped": N}
        """
        saved = 0
        skipped = 0

        try:
            if announcements:
                conn = await asyncpg.connect(self.config.database_url)
                try:
                    saved, skipped = await repository.save_announcements(
                        conn, announcements
                    )
                    logger.info(f"공고 저장: 신규 {saved}건, 중복 스킵 {skipped}건")
                finally:
                    await conn.close()
        except Exception as e:
            logger.error(f"공고 저장 중 예외: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

        # 워커 기동
        if self._running:
            logger.warning("워커가 이미 실행 중 — 저장만 수행")
        else:
            asyncio.create_task(self._run_worker())

        return {"status": "accepted", "saved": saved, "skipped": skipped}

    async def send(self, bid_notice_nos: list[str] | None = None) -> dict:
        """EC2 전송 — analyzed 건을 EC2로 전송

        Args:
            bid_notice_nos: 전송 대상 공고번호 리스트.
                           빈 리스트면 analyzed 전체 배치 전송.

        Returns:
            {"status": "completed", "sent": N, "failed": N, "errors": [...]}
        """
        conn = await asyncpg.connect(self.config.database_url)
        try:
            if bid_notice_nos:
                # 지정된 건만 조회
                items = []
                all_analyzed = await repository.fetch_by_status(conn, "analyzed")
                for item in all_analyzed:
                    if item["bid_notice_no"] in bid_notice_nos:
                        items.append(item)
            else:
                items = await repository.fetch_by_status(conn, "analyzed")

            if not items:
                return {"status": "no_items", "sent": 0, "failed": 0, "errors": []}

            sent_count = await self._send_batch(conn, items)
            failed_count = len(items) - sent_count

            return {
                "status": "completed",
                "sent": sent_count,
                "failed": failed_count,
                "errors": [],
            }
        except Exception as e:
            logger.error(f"EC2 전송 중 예외: {e}", exc_info=True)
            return {"status": "error", "sent": 0, "failed": 0, "message": str(e)}
        finally:
            await conn.close()

    async def ensure_tables(self) -> None:
        """collected_announcements 테이블 생성 (IF NOT EXISTS)"""
        try:
            conn = await asyncpg.connect(self.config.database_url)
            try:
                await repository.ensure_tables(conn)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"테이블 생성 실패: {e}", exc_info=True)

    # ── 백그라운드 워커 ───────────────────────────────

    async def _run_worker(self) -> None:
        """백그라운드 워커 코루틴

        asyncio.create_task()로 기동됨.
        1. 비정상 종료 복구
        2. 실패 건 재시도 원복
        3. collected 건 조회
        4. 건별 순차: 분석 → (성공 시) 전송
        5. 완료 후 자동 종료
        """
        self._running = True
        start_time = time.monotonic()
        analyzed_count = 0
        sent_count = 0
        failed_count = 0

        try:
            conn = await asyncpg.connect(self.config.database_url)
            try:
                # 1. 복구 + 원복
                recovered = await repository.recover_stuck(conn)
                if recovered > 0:
                    logger.info(f"비정상 종료 복구: {recovered}건")

                retried = await repository.retry_failed(conn)
                if retried > 0:
                    logger.info(f"실패 건 원복: {retried}건")

                # 2. collected 건 조회
                items = await repository.fetch_by_status(conn, "collected")
                if not items:
                    logger.info("분석 대상 공고 없음")
                    return

                logger.info(f"분석 대상: {len(items)}건")

                # 3. 건별 순차 분석 + 전송
                for item in items:
                    result = await self._analyze_one(conn, item)
                    if result is not None:
                        analyzed_count += 1
                        # 분석 성공 → EC2 전송 시도
                        success = await self._send_one(conn, item, result)
                        if success:
                            sent_count += 1
                    else:
                        failed_count += 1

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"워커 실행 중 예외: {e}", exc_info=True)

        finally:
            self._running = False
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                f"워커 종료: analyzed={analyzed_count}, "
                f"sent={sent_count}, failed={failed_count}, "
                f"duration={elapsed_ms}ms"
            )

    # ── 분석 ─────────────────────────────────────────

    async def _analyze_one(self, conn, announcement: dict) -> dict | None:
        """단건 분석: Analyzer 라우터 HTTP 호출 + DB 상태 갱신

        Returns:
            분석 결과 dict (성공) 또는 None (실패)
        """
        bid_notice_no = announcement["bid_notice_no"]

        # 1. analyzing 상태로 변경
        await repository.update_status(conn, bid_notice_no, {
            "pipeline_status": "analyzing",
        })

        try:
            # 2. Analyzer API 호출 (datetime → ISO 8601 변환)
            payload = dict(announcement)
            for key in ("bid_begin_dt", "bid_close_dt", "collected_at", "analyzed_at"):
                if key in payload:
                    payload[key] = serialize_dt(payload[key])

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.internal_api_base_url}/api/internal/analyzer/analyze",
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                analysis_result = response.json()

            # 3. 성공: analyzed 상태로 변경
            now = datetime.now(timezone.utc)
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "analyzed",
                "analysis_result": json.dumps(analysis_result, ensure_ascii=False),
                "analyzed_at": now,
                "error_message": "",
            })

            logger.debug(f"분석 성공: {bid_notice_no}")
            return analysis_result

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            error_msg = str(e)[:500]
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "analyze_failed",
                "error_message": error_msg,
                "retry_count_increment": True,
            })
            logger.warning(f"분석 실패: {bid_notice_no} - {error_msg}")
            return None

        except Exception as e:
            error_msg = str(e)[:500]
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "analyze_failed",
                "error_message": error_msg,
                "retry_count_increment": True,
            })
            logger.error(f"분석 중 예외: {bid_notice_no} - {error_msg}", exc_info=True)
            return None

    # ── EC2 전송 ─────────────────────────────────────

    async def _send_one(self, conn, announcement: dict, analysis_result: dict) -> bool:
        """단건 EC2 전송 (워커 내 분석 성공 즉시 호출)

        Returns:
            True (성공) / False (실패)
        """
        bid_notice_no = announcement["bid_notice_no"]
        payload = self._build_payload(announcement, analysis_result)

        await repository.update_status(conn, bid_notice_no, {
            "pipeline_status": "sending",
        })

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.ec2_api_url}/api/announcements/batch",
                    json={"announcements": [payload]},
                    headers={"X-API-Key": self.config.ec2_api_key},
                    timeout=30.0,
                )
                response.raise_for_status()

            now = datetime.now(timezone.utc)
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "sent",
                "sent_at": now,
                "error_message": "",
            })
            logger.debug(f"EC2 전송 성공: {bid_notice_no}")
            return True

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            error_msg = str(e)[:500]
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "send_failed",
                "error_message": error_msg,
                "retry_count_increment": True,
            })
            logger.warning(f"EC2 전송 실패: {bid_notice_no} - {error_msg}")
            return False

        except Exception as e:
            error_msg = str(e)[:500]
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "send_failed",
                "error_message": error_msg,
                "retry_count_increment": True,
            })
            logger.error(
                f"EC2 전송 중 예외: {bid_notice_no} - {error_msg}", exc_info=True
            )
            return False

    async def _send_batch(self, conn, analyzed_items: list[dict]) -> int:
        """배치 EC2 전송 (send() 공개 메서드에서 호출)

        Returns:
            전송 성공 건수
        """
        if not analyzed_items:
            return 0

        payloads = []
        for item in analyzed_items:
            analysis_result = item.get("analysis_result") or {}
            payload = self._build_payload(item, analysis_result)
            payloads.append(payload)

        bid_nos = [item["bid_notice_no"] for item in analyzed_items]
        await conn.execute(
            """
            UPDATE g2b.collected_announcements
            SET pipeline_status = 'sending'
            WHERE bid_notice_no = ANY($1::varchar[]);
            """,
            bid_nos,
        )

        now = datetime.now(timezone.utc)
        sent_count = 0

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.ec2_api_url}/api/announcements/batch",
                    json={"announcements": payloads},
                    headers={"X-API-Key": self.config.ec2_api_key},
                    timeout=30.0,
                )
                response.raise_for_status()
                response_body = response.json()

            errors = response_body.get("errors", [])

            if not errors:
                for item in analyzed_items:
                    await repository.update_status(conn, item["bid_notice_no"], {
                        "pipeline_status": "sent",
                        "sent_at": now,
                        "error_message": "",
                    })
                    sent_count += 1
            else:
                error_nos = {e["bid_notice_no"] for e in errors}
                for item in analyzed_items:
                    if item["bid_notice_no"] in error_nos:
                        await repository.update_status(conn, item["bid_notice_no"], {
                            "pipeline_status": "send_failed",
                            "error_message": "EC2 서버 부분 실패",
                            "retry_count_increment": True,
                        })
                    else:
                        await repository.update_status(conn, item["bid_notice_no"], {
                            "pipeline_status": "sent",
                            "sent_at": now,
                            "error_message": "",
                        })
                        sent_count += 1

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            error_msg = str(e)[:500]
            logger.error(f"EC2 배치 전송 실패: {error_msg}")
            for item in analyzed_items:
                await repository.update_status(conn, item["bid_notice_no"], {
                    "pipeline_status": "send_failed",
                    "error_message": error_msg,
                    "retry_count_increment": True,
                })

        except Exception as e:
            error_msg = str(e)[:500]
            logger.error(f"EC2 배치 전송 중 예외: {error_msg}", exc_info=True)
            for item in analyzed_items:
                await repository.update_status(conn, item["bid_notice_no"], {
                    "pipeline_status": "send_failed",
                    "error_message": error_msg,
                    "retry_count_increment": True,
                })

        return sent_count

    # ── 페이로드 ─────────────────────────────────────

    def _build_payload(self, announcement: dict, analysis_result: dict) -> dict:
        """원본 + 분석 결과 → AnalyzedAnnouncement 스키마 병합"""
        return {
            "bid_notice_no": announcement["bid_notice_no"],
            "bid_notice_nm": announcement["bid_notice_nm"],
            "ntce_instt_nm": announcement.get("ntce_instt_nm"),
            "dminstt_nm": announcement.get("dminstt_nm"),
            "presmpt_price": announcement.get("presmpt_price"),
            "bid_begin_dt": serialize_dt(announcement.get("bid_begin_dt")),
            "bid_close_dt": serialize_dt(announcement.get("bid_close_dt")),
            "link_url": announcement.get("link_url"),
            "raw_data": announcement.get("raw_data"),
            "category": analysis_result.get("category"),
            "relevance_score": analysis_result.get("relevance_score", 0),
            "summary": analysis_result.get("summary"),
            "requirements": analysis_result.get("requirements"),
            "needs_research_lab": analysis_result.get("needs_research_lab", False),
            "analysis_detail": analysis_result.get("analysis_detail"),
            "collected_at": serialize_dt(announcement.get("collected_at")),
            "analyzed_at": serialize_dt(announcement.get("analyzed_at")),
        }
