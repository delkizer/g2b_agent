"""나라장터 입찰공고 수집 서비스

나라장터(G2B) API 호출 + 응답 파싱 + 스키마 매핑 + 수집 이력 DB를 자체 완결로 처리.
향후 다른 정부 OpenAPI 추가 시 같은 패턴으로 xxx_service.py를 만들 수 있는 구조.

참조:
- docs/collector/02-api-spec.md : 전체 API 규격 (에러 코드, 페이징, 스키마 매핑)
- agent/class_lib/collector/schemas.py : Pydantic 모델
- agent/config/config.py : Config 클래스
"""

import asyncio
import math
from datetime import datetime, timedelta

import asyncpg
import httpx

from config.config import Config
from class_lib.collector.schemas import (
    G2BApiResponse,
    G2BApiItem,
    CollectedAnnouncement,
    CollectorHistory,
)


class G2BApiError(Exception):
    """나라장터 API 에러"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"G2B API Error [{code}]: {message}")


class G2BService:
    """나라장터 입찰공고 수집 서비스

    API 호출 + 응답 파싱 + 스키마 매핑 + 수집 이력 DB를 자체 완결로 처리.
    Config는 내부에서 직접 생성 (외부 주입 금지).
    """

    # 재시도 불필요 에러 코드 (02-api-spec.md 12.2절)
    NON_RETRYABLE_CODES = {"06", "07", "08", "10", "11", "12", "20", "30", "31", "32"}
    NODATA_CODE = "03"

    def __init__(self, logger):
        self.config = Config()
        self.logger = logger
        self.base_url = f"{self.config.g2b_api_base_url}/ao/PubDataOpnStdService"
        self.api_key = self.config.g2b_api_key
        self.db_url = self.config.database_url

    async def fetch_announcements(
        self,
        start_dt: datetime,
        end_dt: datetime,
        num_of_rows: int = 100,
    ) -> list[CollectedAnnouncement]:
        """입찰공고 수집 + 내부 스키마 매핑 반환

        1. API 호출 (페이징 자동 처리)
        2. 응답 파싱 (G2BApiItem)
        3. 내부 스키마 매핑 (CollectedAnnouncement)

        Args:
            start_dt: 조회 시작 일시
            end_dt: 조회 종료 일시
            num_of_rows: 페이지당 결과 수 (기본 100)

        Returns:
            CollectedAnnouncement 리스트
        """
        self.logger.info(
            f"나라장터 API 호출 시작: {start_dt.strftime('%Y-%m-%d %H:%M')} ~ "
            f"{end_dt.strftime('%Y-%m-%d %H:%M')}"
        )

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/getDataSetOpnStdBidPblancInfo"
                params = {
                    "ServiceKey": self.api_key,
                    "type": "json",
                    "bidNtceBgnDt": to_g2b_request_dt(start_dt),
                    "bidNtceEndDt": to_g2b_request_dt(end_dt),
                }

                # 페이징 자동 처리하여 전체 결과 수집
                items = await self._fetch_all_pages(client, url, params, num_of_rows)

                # 내부 스키마로 변환
                announcements = [
                    map_item_to_announcement(item) for item in items
                ]

                self.logger.info(f"수집 완료: {len(announcements)}건")
                return announcements

        except G2BApiError as e:
            self.logger.error(f"G2B API 에러: {e}")
            return []
        except Exception as e:
            self.logger.error(f"수집 중 예외 발생: {e}", exc_info=True)
            return []

    async def _call_api(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict,
        max_retries: int = 3,
    ) -> dict:
        """API 호출 + 재시도 + 에러 코드 분류

        02-api-spec.md 12장 에러 처리 참조.
        재시도: 3회, 지수 백오프 (1초, 2초, 4초)

        Args:
            client: httpx 비동기 클라이언트
            url: API URL
            params: 요청 파라미터
            max_retries: 최대 재시도 횟수

        Returns:
            응답 body dict

        Raises:
            G2BApiError: 복구 불가능한 API 에러
        """
        for attempt in range(max_retries):
            try:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()

                data = response.json()
                header = data.get("response", {}).get("header", {})
                result_code = header.get("resultCode", "")
                result_msg = header.get("resultMsg", "")

                # 정상 응답
                if result_code == "00":
                    return data.get("response", {}).get("body", {})

                # 데이터 없음 (정상)
                if result_code == self.NODATA_CODE:
                    self.logger.info("조회 결과 없음 (NODATA)")
                    return {"items": [], "totalCount": 0}

                # 재시도 불필요한 에러
                if result_code in self.NON_RETRYABLE_CODES:
                    self.logger.error(f"G2B API 에러 [{result_code}]: {result_msg}")
                    raise G2BApiError(result_code, result_msg)

                # 재시도 가능 에러
                self.logger.warning(
                    f"G2B API 재시도 가능 에러 [{result_code}]: {result_msg} "
                    f"(시도 {attempt + 1}/{max_retries})"
                )

            except httpx.HTTPStatusError as e:
                self.logger.warning(
                    f"HTTP 에러 {e.response.status_code} "
                    f"(시도 {attempt + 1}/{max_retries})"
                )
                if e.response.status_code in [400, 401, 403, 404]:
                    # 재시도 불필요한 HTTP 에러
                    raise G2BApiError(str(e.response.status_code), str(e))

            except httpx.RequestError as e:
                self.logger.warning(
                    f"요청 에러: {e} (시도 {attempt + 1}/{max_retries})"
                )

            # 지수 백오프 대기 (1초, 2초, 4초)
            if attempt < max_retries - 1:
                wait_seconds = 2 ** attempt
                self.logger.info(f"{wait_seconds}초 후 재시도...")
                await asyncio.sleep(wait_seconds)

        # 최대 재시도 초과 - Graceful Degradation (빈 리스트 반환)
        self.logger.error(f"G2B API 호출 실패 (최대 재시도 {max_retries}회 초과)")
        return {"items": [], "totalCount": 0}

    async def _fetch_all_pages(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict,
        num_of_rows: int = 100,
    ) -> list[G2BApiItem]:
        """페이징 자동 처리하여 전체 결과 수집

        02-api-spec.md 11장 페이징 참조.

        Args:
            client: httpx 비동기 클라이언트
            url: API URL
            params: 공통 요청 파라미터
            num_of_rows: 페이지당 결과 수

        Returns:
            G2BApiItem 리스트 (전체 페이지 결과)
        """
        all_items = []
        page_no = 1

        while True:
            request_params = {
                **params,
                "pageNo": page_no,
                "numOfRows": num_of_rows,
            }

            self.logger.debug(f"페이지 {page_no} 조회 중...")
            body = await self._call_api(client, url, request_params)

            items_raw = body.get("items")
            total_count = body.get("totalCount", 0)

            # items 파싱 (dict/list/None 모두 처리)
            items = self._parse_items(items_raw)
            all_items.extend(items)

            # 마지막 페이지 판단
            total_pages = math.ceil(total_count / num_of_rows) if total_count > 0 else 1
            if page_no >= total_pages:
                break

            page_no += 1

            # Rate Limit 방지 (페이지 간 0.3초 대기)
            await asyncio.sleep(0.3)

        return all_items

    def _parse_items(self, items_raw: list | dict | None) -> list[G2BApiItem]:
        """API 응답 items를 G2BApiItem 리스트로 파싱

        주의: items가 dict({"item": [...]}) 또는 list, 또는 None일 수 있음.
        단건 결과일 때 items.item이 dict일 수 있음 → 리스트 래핑 필요.

        Args:
            items_raw: API 응답의 items 필드

        Returns:
            G2BApiItem 리스트
        """
        if items_raw is None:
            return []

        # dict 형태: {"item": [...]} 또는 {"item": {...}}
        if isinstance(items_raw, dict):
            item_data = items_raw.get("item", [])
            # 단건 결과: {"item": {...}} → [{...}]
            if isinstance(item_data, dict):
                return [G2BApiItem(**item_data)]
            # 복수 결과: {"item": [...]}
            elif isinstance(item_data, list):
                return [G2BApiItem(**item) for item in item_data]
            else:
                return []

        # list 형태: [...]
        if isinstance(items_raw, list):
            return [G2BApiItem(**item) for item in items_raw]

        return []

    # === 수집 이력 DB (Direct SQL, asyncpg) ===

    async def get_last_collected_dt(self, operation: str = "bid_announcement") -> datetime | None:
        """마지막 수집 종료 시점 조회

        SELECT collected_end_dt FROM g2b.collector_history
        WHERE operation = $1 AND status = 'success'
        ORDER BY collected_at DESC LIMIT 1

        Args:
            operation: API 오퍼레이션명

        Returns:
            마지막 수집 종료 시각 또는 None
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT collected_end_dt
                    FROM g2b.collector_history
                    WHERE operation = $1 AND status = 'success'
                    ORDER BY collected_at DESC
                    LIMIT 1
                    """,
                    operation,
                )
                return row["collected_end_dt"] if row else None
            finally:
                await conn.close()
        except Exception as e:
            self.logger.warning(f"수집 이력 조회 실패: {e}")
            return None

    async def save_history(self, history: CollectorHistory) -> None:
        """수집 이력 저장

        INSERT INTO g2b.collector_history
        (operation, collected_at, collected_end_dt, total_count, filtered_count, duration_ms, status, error_message)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)

        Args:
            history: CollectorHistory 인스턴스
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute(
                    """
                    INSERT INTO g2b.collector_history
                    (operation, collected_at, collected_end_dt, total_count, filtered_count, duration_ms, status, error_message)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    history.operation,
                    history.collected_at,
                    history.collected_end_dt,
                    history.total_count,
                    history.filtered_count,
                    history.duration_ms,
                    history.status,
                    history.error_message,
                )
                self.logger.debug(f"수집 이력 저장 완료: {history.operation}")
            finally:
                await conn.close()
        except Exception as e:
            self.logger.error(f"수집 이력 저장 실패: {e}", exc_info=True)

    async def ensure_tables(self) -> None:
        """테이블 생성 (IF NOT EXISTS)

        CREATE SCHEMA IF NOT EXISTS g2b;
        CREATE TABLE IF NOT EXISTS g2b.collector_history (...)
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # 스키마 생성
                await conn.execute("CREATE SCHEMA IF NOT EXISTS g2b;")

                # 수집 이력 테이블 생성
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS g2b.collector_history (
                        id              SERIAL PRIMARY KEY,
                        operation       VARCHAR(50) NOT NULL,
                        collected_at    TIMESTAMPTZ NOT NULL,
                        collected_end_dt TIMESTAMPTZ NOT NULL,
                        total_count     INTEGER DEFAULT 0,
                        filtered_count  INTEGER DEFAULT 0,
                        duration_ms     INTEGER DEFAULT 0,
                        status          VARCHAR(20) DEFAULT 'success',
                        error_message   TEXT DEFAULT ''
                    );
                    """
                )

                self.logger.info("DB 테이블 확인 완료 (g2b.collector_history)")
            finally:
                await conn.close()
        except Exception as e:
            self.logger.error(f"테이블 생성 실패: {e}", exc_info=True)


# ============================================================
# 유틸 함수 (모듈 수준, 클래스 외부)
# ============================================================


def to_g2b_request_dt(dt: datetime) -> str:
    """datetime → 나라장터 요청 파라미터 형식 (YYYYMMDDHHmm 12자리)

    Args:
        dt: Python datetime 객체

    Returns:
        'YYYYMMDDHHmm' 형식 문자열

    Example:
        >>> to_g2b_request_dt(datetime(2026, 2, 16, 10, 30))
        '202602161030'
    """
    return dt.strftime("%Y%m%d%H%M")


def map_item_to_announcement(item: G2BApiItem) -> CollectedAnnouncement:
    """G2BApiItem → CollectedAnnouncement 변환

    02-api-spec.md 9장 매핑 테이블 참조.

    Args:
        item: G2BApiItem 인스턴스

    Returns:
        CollectedAnnouncement 인스턴스
    """
    return CollectedAnnouncement(
        bid_notice_no=item.bidNtceNo,
        bid_notice_nm=item.bidNtceNm,
        ntce_instt_nm=item.ntceInsttNm,
        dminstt_nm=item.dmndInsttNm,
        presmpt_price=_parse_price(item.presmptPrce),
        bid_begin_dt=_combine_date_time(item.bidBeginDate, item.bidBeginTm),
        bid_close_dt=_combine_date_time(item.bidClseDate, item.bidClseTm),
        link_url=item.bidNtceUrl,
        raw_data=item.model_dump(),
        collected_at=datetime.now().isoformat(),
    )


def _parse_price(value: str) -> int:
    """추정가격 문자열 → 정수 변환

    Args:
        value: 추정가격 문자열 (예: "500000000" 또는 "")

    Returns:
        정수 (변환 실패 시 0)

    Example:
        >>> _parse_price("500000000")
        500000000
        >>> _parse_price("")
        0
    """
    if not value or not value.strip():
        return 0
    try:
        return int(float(value.replace(",", "")))
    except (ValueError, TypeError):
        return 0


def _combine_date_time(date_str: str, time_str: str) -> str:
    """날짜(YYYY-MM-DD) + 시각(HH:MM) → ISO 8601 변환

    Args:
        date_str: 'YYYY-MM-DD' 형식 (예: '2026-02-16')
        time_str: 'HH:MM' 형식 (예: '10:00')

    Returns:
        'YYYY-MM-DDTHH:MM:00' (ISO 8601) 또는 빈 문자열

    Example:
        >>> _combine_date_time("2026-02-16", "10:00")
        '2026-02-16T10:00:00'
        >>> _combine_date_time("", "10:00")
        ''
    """
    if not date_str or not date_str.strip():
        return ""
    time_part = time_str.strip() if time_str else "00:00"
    try:
        dt = datetime.strptime(f"{date_str.strip()} {time_part}", "%Y-%m-%d %H:%M")
        return dt.isoformat()
    except ValueError:
        return date_str  # 파싱 실패 시 원본 반환
