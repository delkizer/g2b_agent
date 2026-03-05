"""파이프라인 오케스트레이터 (v3 — 로컬 우선 저장 + EC2 동기화)

Collector 완료 신호(POST /api/internal/pipeline/run)를 받아:
1. DB에 공고를 저장하고 즉시 응답 (status: accepted)
2. 백그라운드 워커를 기동하여 첨부파일 다운로드 + 로컬 announcements 저장을 비동기 처리
3. EC2 동기화는 별도 sync_ec2() 메서드로 분리

v3 변경: EC2 직접 전송 → 로컬 g2b.announcements 저장. EC2 동기화는 별도 API.

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
    """파이프라인 오케스트레이터 (v3 — 로컬 저장 + EC2 동기화)

    run() — 저장 + 워커 기동 (즉시 응답)
    send() — 로컬 저장 (독립 API, 레거시 호환)
    sync_ec2() — 로컬 → EC2 동기화
    _run_worker() — 백그라운드 코루틴 (첨부파일 다운로드 + 로컬 저장 루프)
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
        """로컬 저장 — collected 건을 건별로 g2b.announcements에 저장

        Args:
            bid_notice_nos: 저장 대상 공고번호 리스트.
                           빈 리스트면 collected 전체 저장.

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

            logger.info(f"로컬 저장 시작: {len(items)}건")
            sent_count = 0
            failed_count = 0

            for item in items:
                success = await self._save_to_local(conn, item)
                if success:
                    sent_count += 1
                else:
                    failed_count += 1

            logger.info(f"로컬 저장 완료: sent={sent_count}, failed={failed_count}")
            return {
                "status": "completed",
                "sent": sent_count,
                "failed": failed_count,
                "errors": [],
            }
        except Exception as e:
            logger.error(f"로컬 저장 중 예외: {e}", exc_info=True)
            return {"status": "error", "sent": 0, "failed": 0, "message": str(e)}
        finally:
            await conn.close()

    async def ensure_tables(self) -> None:
        """전체 테이블 생성 (IF NOT EXISTS)

        - g2b.collected_announcements
        - g2b.announcements
        - g2b.ec2_sync_log
        """
        try:
            conn = await asyncpg.connect(self.config.database_url)
            try:
                await repository.ensure_tables(conn)
                await repository.ensure_announcements_table(conn)
                await repository.ensure_ec2_sync_log_table(conn)
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

                logger.info(f"저장 대상: {len(items)}건")

                # 3. 건별 순차: 첨부파일 다운로드 → 로컬 저장
                for item in items:
                    # 첨부파일 다운로드 (실패해도 저장 진행)
                    await self._download_attachments(item)

                    # 로컬 announcements 저장
                    success = await self._save_to_local(conn, item)
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

    # ── 로컬 저장 ───────────────────────────────────────

    async def _save_to_local(self, conn, announcement: dict) -> bool:
        """단건 로컬 g2b.announcements 저장

        collected_announcements → announcements upsert.
        분석 필드(category, relevance_score 등)와 status는 덮어쓰지 않는다.

        Returns:
            True (성공) / False (실패)
        """
        bid_notice_no = announcement["bid_notice_no"]

        await repository.update_status(conn, bid_notice_no, {
            "pipeline_status": "sending",
        })

        try:
            await repository.upsert_to_announcements(conn, announcement)

            now = datetime.now(timezone.utc)
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "sent",
                "sent_at": now,
                "error_message": "",
            })
            logger.debug(f"로컬 저장 성공: {bid_notice_no}")
            return True

        except Exception as e:
            error_msg = str(e)[:500]
            await repository.update_status(conn, bid_notice_no, {
                "pipeline_status": "send_failed",
                "error_message": error_msg,
                "retry_count_increment": True,
            })
            logger.error(
                f"로컬 저장 실패: {bid_notice_no} - {error_msg}", exc_info=True
            )
            return False

    # ── EC2 동기화 ─────────────────────────────────────

    async def sync_ec2(self, limit: int = 500) -> dict:
        """로컬 g2b.announcements → EC2 동기화 (DB + 파일)

        1. fetch_for_ec2_sync() — 미동기화 공고 조회
        2. 20건 청크로 분할
        3. 청크별 HTTP POST /api/announcements/batch
        4. 성공 건 mark_ec2_synced()
        5. 성공 건 파일 업로드 (attachments + output)

        Returns:
            {"status": ..., "synced": N, "failed": N, "errors": [...]}
        """
        conn = await asyncpg.connect(self.config.database_url)
        try:
            items = await repository.fetch_for_ec2_sync(conn, limit=limit)
            if not items:
                logger.info("EC2 동기화 대상 없음")
                return {"status": "no_items", "synced": 0, "failed": 0, "errors": []}

            logger.info(f"EC2 동기화 시작: {len(items)}건")
            synced_total = 0
            failed_total = 0
            errors = []
            all_synced_nos = []

            for i in range(0, len(items), self.SEND_BATCH_SIZE):
                chunk = items[i:i + self.SEND_BATCH_SIZE]
                payloads = [self._build_sync_payload(row) for row in chunk]

                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.config.ec2_api_url}/api/announcements/batch",
                            json={"announcements": payloads},
                            headers={"X-API-Key": self.config.ec2_api_key},
                            timeout=30.0,
                        )
                        response.raise_for_status()
                        resp_body = response.json()

                    resp_errors = resp_body.get("errors", [])
                    error_nos = {e["bid_notice_no"] for e in resp_errors}

                    synced_nos = [
                        row["bid_notice_no"] for row in chunk
                        if row["bid_notice_no"] not in error_nos
                    ]

                    if synced_nos:
                        await repository.mark_ec2_synced(conn, synced_nos)
                        synced_total += len(synced_nos)
                        all_synced_nos.extend(synced_nos)

                    failed_total += len(error_nos)
                    errors.extend(resp_errors)

                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    error_msg = str(e)[:500]
                    logger.error(f"EC2 동기화 청크 실패 ({len(chunk)}건): {error_msg}")
                    failed_total += len(chunk)
                    for row in chunk:
                        errors.append({
                            "bid_notice_no": row["bid_notice_no"],
                            "error": error_msg,
                        })

                except Exception as e:
                    error_msg = str(e)[:500]
                    logger.error(
                        f"EC2 동기화 청크 예외 ({len(chunk)}건): {error_msg}",
                        exc_info=True,
                    )
                    failed_total += len(chunk)
                    for row in chunk:
                        errors.append({
                            "bid_notice_no": row["bid_notice_no"],
                            "error": error_msg,
                        })

            # 파일 동기화 (DB 동기화 성공 건만)
            if all_synced_nos:
                file_result = await self._sync_files_to_ec2(all_synced_nos)
                logger.info(
                    f"파일 동기화: uploaded={file_result['uploaded']}, "
                    f"skipped={file_result['skipped']}"
                )

            logger.info(
                f"EC2 동기화 완료: synced={synced_total}, failed={failed_total}"
            )
            return {
                "status": "completed",
                "synced": synced_total,
                "failed": failed_total,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"EC2 동기화 중 예외: {e}", exc_info=True)
            return {
                "status": "error",
                "synced": 0,
                "failed": 0,
                "message": str(e),
            }
        finally:
            await conn.close()

    async def _sync_files_to_ec2(self, bid_notice_nos: list[str]) -> dict:
        """로컬 파일(attachments + output) → EC2 파일 업로드 API로 전송

        파일이 없는 공고는 스킵. 업로드 실패는 경고 로그만 (DB 동기화에 영향 없음).
        """
        uploaded = 0
        skipped = 0

        for bid_no in bid_notice_nos:
            for file_type, base_dir in [
                ("attachments", ATTACHMENTS_BASE_DIR),
                ("outputs", self._get_output_base_dir()),
            ]:
                source_dir = base_dir / bid_no
                if not source_dir.is_dir():
                    continue

                files_to_upload = [
                    f for f in source_dir.iterdir() if f.is_file()
                ]
                if not files_to_upload:
                    continue

                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        upload_files = [
                            ("files", (f.name, f.read_bytes()))
                            for f in files_to_upload
                        ]
                        response = await client.post(
                            f"{self.config.ec2_api_url}/api/files/{bid_no}/{file_type}",
                            files=upload_files,
                            headers={"X-API-Key": self.config.ec2_api_key},
                        )
                        response.raise_for_status()
                    uploaded += len(files_to_upload)
                    logger.debug(
                        f"파일 업로드: {bid_no}/{file_type} — {len(files_to_upload)}건"
                    )
                except Exception as e:
                    skipped += len(files_to_upload)
                    logger.warning(
                        f"파일 업로드 실패: {bid_no}/{file_type} — {e}"
                    )

        return {"uploaded": uploaded, "skipped": skipped}

    @staticmethod
    def _get_output_base_dir() -> Path:
        """output 디렉토리 경로 (Config의 OneDrive 경로와 동일 위치)"""
        return ATTACHMENTS_BASE_DIR.parent / "output"

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
        """원본 데이터 → AnalyzedAnnouncement 스키마 변환 (분석 결과 없이)

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

    def _build_sync_payload(self, row: dict) -> dict:
        """g2b.announcements row → batch API payload 변환 (분석 필드 포함)"""
        payload = {
            "bid_notice_no": row["bid_notice_no"],
            "bid_notice_nm": row["bid_notice_nm"],
            "ntce_instt_nm": row.get("ntce_instt_nm"),
            "dminstt_nm": row.get("dminstt_nm"),
            "presmpt_price": row.get("presmpt_price"),
            "bid_begin_dt": serialize_dt(row.get("bid_begin_dt")),
            "bid_close_dt": serialize_dt(row.get("bid_close_dt")),
            "link_url": row.get("link_url"),
            "raw_data": row.get("raw_data"),
            "attachment_urls": row.get("attachment_urls", []),
            "collected_at": serialize_dt(row.get("collected_at")),
        }

        # 분석 필드 (존재하면 포함)
        if row.get("category"):
            payload["category"] = row["category"]
        if row.get("relevance_score"):
            payload["relevance_score"] = row["relevance_score"]
        if row.get("summary"):
            payload["summary"] = row["summary"]
        if row.get("requirements"):
            payload["requirements"] = row["requirements"]
        if row.get("needs_research_lab") is not None:
            payload["needs_research_lab"] = row["needs_research_lab"]
        if row.get("analysis_detail"):
            payload["analysis_detail"] = row["analysis_detail"]
        if row.get("analyzed_at"):
            payload["analyzed_at"] = serialize_dt(row["analyzed_at"])

        return payload
