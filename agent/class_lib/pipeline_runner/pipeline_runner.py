"""파이프라인 오케스트레이터 (v2 — 분석 없이 전송)

Collector 완료 신호(POST /api/internal/pipeline/run)를 받아:
1. DB에 공고를 저장하고 즉시 응답 (status: accepted)
2. 백그라운드 워커를 기동하여 첨부파일 다운로드 + EC2 전송을 비동기 처리
3. 워커는 건별로 첨부파일 다운로드 → EC2 전송을 순차 호출
4. 실패 건 재시도 (retry_count < 3)

v2 변경: Analyzer API 호출 제거. 분석은 Cowork(Windows)에서 수행.

Config는 내부에서 직접 생성 (외부 주입 금지).
Logger는 module-level import (loguru).

참조:
- docs/pipeline/01-pipeline-overview.md §6 : PipelineRunner 클래스 설계
- docs/shared/01-data-schema.md : AnalyzedAnnouncement 스키마
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx
from loguru import logger

from config.config import Config
from class_lib.pipeline_runner import repository
from class_lib.pipeline_runner.utils import serialize_dt

# v2: 첨부파일 다운로드 경로 (WSL → Windows OneDrive 공유)
ATTACHMENTS_BASE_DIR = Path(
    "/mnt/c/Users/USER/OneDrive - 이용석/spotv/TRACKMAN/인수인계/베드민턴/g2b_agent/attachments"
)


class PipelineRunner:
    """파이프라인 오케스트레이터 (v2 — 분석 없이 전송)

    run() — 저장 + 워커 기동 (즉시 응답)
    send() — EC2 전송 (독립 API)
    _run_worker() — 백그라운드 코루틴 (첨부파일 다운로드 + 전송 루프)
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
        """EC2 전송 — collected 건을 건별로 EC2로 전송

        Args:
            bid_notice_nos: 전송 대상 공고번호 리스트.
                           빈 리스트면 collected 전체 전송.

        Returns:
            {"status": "completed", "sent": N, "failed": N, "errors": [...]}
        """
        conn = await asyncpg.connect(self.config.database_url)
        try:
            if bid_notice_nos:
                items = []
                all_collected = await repository.fetch_by_status(conn, "collected")
                for item in all_collected:
                    if item["bid_notice_no"] in bid_notice_nos:
                        items.append(item)
            else:
                items = await repository.fetch_by_status(conn, "collected")

            if not items:
                return {"status": "no_items", "sent": 0, "failed": 0, "errors": []}

            logger.info(f"EC2 건별 전송 시작: {len(items)}건")
            sent_count = 0
            failed_count = 0

            for item in items:
                success = await self._send_one(conn, item)
                if success:
                    sent_count += 1
                else:
                    failed_count += 1

            logger.info(f"EC2 전송 완료: sent={sent_count}, failed={failed_count}")
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
        4. 건별 순차: 첨부파일 다운로드 → EC2 전송
        5. 완료 후 자동 종료

        v2: 분석 단계 제거. 수집 → 전송 직행.
        """
        self._running = True
        start_time = time.monotonic()
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
                    logger.info("전송 대상 공고 없음")
                    return

                logger.info(f"전송 대상: {len(items)}건")

                # 3. 건별 순차: 첨부파일 다운로드 → EC2 전송
                for item in items:
                    # 첨부파일 다운로드 (실패해도 전송 진행)
                    await self._download_attachments(item)

                    # EC2 전송
                    success = await self._send_one(conn, item)
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
                f"워커 종료: sent={sent_count}, failed={failed_count}, "
                f"duration={elapsed_ms}ms"
            )

    # ── 첨부파일 다운로드 (v2) ────────────────────────

    async def _download_attachments(self, announcement: dict) -> None:
        """공고 첨부파일 다운로드

        attachment_urls의 파일을 /mnt/c/work/g2b_agent/attachments/{bid_notice_no}/에 저장.
        Cowork가 C:\\work\\g2b_agent\\attachments\\{bid_notice_no}\\ 에서 접근.
        다운로드 실패는 경고 로그만 (전송 흐름에 영향 없음).
        """
        bid_notice_no = announcement["bid_notice_no"]
        urls = announcement.get("attachment_urls") or []
        if not urls:
            return

        target_dir = ATTACHMENTS_BASE_DIR / bid_notice_no
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"첨부파일 디렉토리 생성 실패: {target_dir} - {e}")
            return

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            for idx, url in enumerate(urls):
                try:
                    response = await client.get(url)
                    response.raise_for_status()

                    # 파일명 추출: Content-Disposition 헤더 우선
                    filename = self._extract_filename(response, url, idx)

                    filepath = target_dir / filename
                    # 파일명 충돌 시 _1, _2 접미사
                    if filepath.exists():
                        stem = filepath.stem
                        suffix = filepath.suffix
                        counter = 1
                        while filepath.exists():
                            filepath = target_dir / f"{stem}_{counter}{suffix}"
                            counter += 1

                    filepath.write_bytes(response.content)
                    logger.debug(f"첨부파일 다운로드: {filepath.name} ({len(response.content):,} bytes)")

                except Exception as e:
                    logger.warning(
                        f"첨부파일 다운로드 실패: {bid_notice_no} url={url[:100]} - {e}"
                    )

    @staticmethod
    def _extract_filename(response: httpx.Response, url: str, idx: int) -> str:
        """응답 헤더 Content-Disposition에서 원본 파일명 추출"""
        import re
        from urllib.parse import unquote

        cd = response.headers.get("content-disposition", "")
        if cd:
            # filename*=UTF-8''encoded_name (RFC 5987)
            match = re.search(r"filename\*\s*=\s*(?:UTF-8|utf-8)?''(.+?)(?:;|$)", cd)
            if match:
                return unquote(match.group(1).strip())
            # filename="name" or filename=name
            match = re.search(r'filename\s*=\s*"?([^";]+)"?', cd)
            if match:
                raw = match.group(1).strip()
                # URL 인코딩된 경우 (%XX 패턴) 디코딩
                if "%" in raw:
                    return unquote(raw)
                # EUC-KR로 인코딩된 경우 디코딩 시도
                try:
                    return raw.encode("latin-1").decode("euc-kr")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    return raw

        # fallback: URL 경로에서 추출 (downloadFile.do 등 제외)
        url_path = url.split("?")[0].split("/")[-1] if "/" in url else ""
        if url_path and "." in url_path and "download" not in url_path.lower():
            return url_path

        return f"attachment_{idx + 1}.bin"

    # ── EC2 전송 ─────────────────────────────────────

    async def _send_one(self, conn, announcement: dict) -> bool:
        """단건 EC2 전송 (v2: 미분석 원본 전송)

        Returns:
            True (성공) / False (실패)
        """
        bid_notice_no = announcement["bid_notice_no"]
        payload = self._build_payload(announcement)

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

    SEND_BATCH_SIZE = 20  # 청크당 최대 건수

    async def _send_batch(self, conn, collected_items: list[dict]) -> int:
        """배치 EC2 전송 (send() 공개 메서드에서 호출)

        SEND_BATCH_SIZE 단위로 청크 분할하여 전송한다.

        Returns:
            전송 성공 건수
        """
        if not collected_items:
            return 0

        bid_nos = [item["bid_notice_no"] for item in collected_items]
        await conn.execute(
            """
            UPDATE g2b.collected_announcements
            SET pipeline_status = 'sending'
            WHERE bid_notice_no = ANY($1::varchar[]);
            """,
            bid_nos,
        )

        total_sent = 0

        for i in range(0, len(collected_items), self.SEND_BATCH_SIZE):
            chunk = collected_items[i:i + self.SEND_BATCH_SIZE]
            sent = await self._send_chunk(conn, chunk)
            total_sent += sent

        return total_sent

    async def _send_chunk(self, conn, chunk: list[dict]) -> int:
        """청크 단위 EC2 전송"""
        payloads = []
        for item in chunk:
            payload = self._build_payload(item)
            payloads.append(payload)

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
                for item in chunk:
                    await repository.update_status(conn, item["bid_notice_no"], {
                        "pipeline_status": "sent",
                        "sent_at": now,
                        "error_message": "",
                    })
                    sent_count += 1
            else:
                error_nos = {e["bid_notice_no"] for e in errors}
                for item in chunk:
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
            logger.error(f"EC2 배치 전송 실패 (청크 {len(chunk)}건): {error_msg}")
            for item in chunk:
                await repository.update_status(conn, item["bid_notice_no"], {
                    "pipeline_status": "send_failed",
                    "error_message": error_msg,
                    "retry_count_increment": True,
                })

        except Exception as e:
            error_msg = str(e)[:500]
            logger.error(f"EC2 배치 전송 중 예외 (청크 {len(chunk)}건): {error_msg}", exc_info=True)
            for item in chunk:
                await repository.update_status(conn, item["bid_notice_no"], {
                    "pipeline_status": "send_failed",
                    "error_message": error_msg,
                    "retry_count_increment": True,
                })

        return sent_count

    # ── 페이로드 ─────────────────────────────────────

    def _build_payload(self, announcement: dict) -> dict:
        """원본 데이터 → AnalyzedAnnouncement 스키마 변환 (v2: 분석 결과 없이)

        분석 필드는 비워서 전송. Cowork가 MCP PATCH로 나중에 채움.
        """
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
            "attachment_urls": announcement.get("attachment_urls", []),
            "collected_at": serialize_dt(announcement.get("collected_at")),
        }
