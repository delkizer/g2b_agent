"""공고 비즈니스 로직 서비스"""

import csv
import io
import math
from datetime import date, datetime

from loguru import logger
from openpyxl import Workbook
from sqlalchemy import select, func, case, text, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from apps.exceptions import AppException
from config.config import Config
from models.announcement import Announcement


# CSV/XLSX 내보내기 컬럼 매핑 (한국어 헤더 → DB 필드)
EXPORT_COLUMNS = [
    ("공고번호", "bid_notice_no"),
    ("공고명", "bid_notice_nm"),
    ("공고기관", "ntce_instt_nm"),
    ("수요기관", "dminstt_nm"),
    ("카테고리", "category"),
    ("적합성점수", "relevance_score"),
    ("추정가격", "presmpt_price"),
    ("입찰개시일", "bid_begin_dt"),
    ("입찰마감일", "bid_close_dt"),
    ("상태", "status"),
    ("연구소필요", "needs_research_lab"),
    ("요약", "summary"),
    ("참가자격", "requirements"),
    ("수집일", "collected_at"),
    ("원문링크", "link_url"),
]

EXPORT_MAX_ROWS = 10_000

# 정렬 가능 컬럼 매핑
SORT_COLUMN_MAP = {
    "relevance_score": Announcement.relevance_score,
    "bid_close_dt": Announcement.bid_close_dt,
    "collected_at": Announcement.collected_at,
    "presmpt_price": Announcement.presmpt_price,
    "created_at": Announcement.created_at,
}


class AnnouncementService:
    """공고 CRUD + 비즈니스 로직"""

    def __init__(self):
        self.config = Config()

    async def create_batch(
        self, session: AsyncSession, announcements: list[dict]
    ) -> dict:
        """일괄 생성/업데이트 (upsert by bid_notice_no)"""
        created = 0
        updated = 0
        errors = []

        for item in announcements:
            try:
                bid_notice_no = item["bid_notice_no"]

                # status 결정: 분석 결과가 있으면 analyzed, 없으면 pending
                if "status" not in item or item["status"] is None:
                    item["status"] = "analyzed" if item.get("relevance_score") is not None else "pending"

                stmt = pg_insert(Announcement).values(**item)

                # ON CONFLICT DO UPDATE — bid_notice_no 기준 upsert
                update_cols = {
                    col: stmt.excluded[col]
                    for col in item.keys()
                    if col != "bid_notice_no"
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=["bid_notice_no"],
                    set_=update_cols,
                ).returning(
                    Announcement.id,
                    literal_column("(xmax = 0)").label("is_insert"),
                )

                result = await session.execute(stmt)
                row = result.one()
                if row.is_insert:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                errors.append({
                    "bid_notice_no": item.get("bid_notice_no", "unknown"),
                    "error": str(e),
                })
                logger.warning(f"배치 처리 실패: {item.get('bid_notice_no')} — {e}")

        await session.commit()

        # TODO: Phase 4 — Notion 자동 연동 (relevance_score >= notion_min_score)

        return {
            "received": len(announcements),
            "created": created,
            "updated": updated,
            "errors": errors,
        }

    async def get_list(self, session: AsyncSession, filters) -> dict:
        """목록 조회 (필터 + 페이징)"""
        # 기본 쿼리
        query = select(
            Announcement.id,
            Announcement.bid_notice_no,
            Announcement.bid_notice_nm,
            Announcement.ntce_instt_nm,
            Announcement.dminstt_nm,
            Announcement.category,
            Announcement.relevance_score,
            Announcement.summary,
            Announcement.presmpt_price,
            Announcement.bid_begin_dt,
            Announcement.bid_close_dt,
            Announcement.status,
            Announcement.needs_research_lab,
            Announcement.collected_at,
            Announcement.created_at,
            Announcement.raw_data['bidwinrDcsnMthdNm'].astext.label('contract_method'),
            literal_column("""
                CASE WHEN raw_data->>'opengDate' IS NOT NULL AND raw_data->>'opengDate' != ''
                THEN (raw_data->>'opengDate' || 'T' || COALESCE(NULLIF(raw_data->>'opengTm', ''), '00:00') || ':00')::timestamptz
                ELSE NULL END
            """).label('openg_dt'),
        )

        count_query = select(func.count()).select_from(Announcement)

        # 필터 적용
        query = self._apply_filters(query, filters)
        count_query = self._apply_filters(count_query, filters)

        # 전체 건수
        total = (await session.execute(count_query)).scalar() or 0

        # 정렬
        sort_col = SORT_COLUMN_MAP.get(filters.sort.value, Announcement.created_at)
        if filters.order.value == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        # 페이징
        offset = (filters.page - 1) * filters.size
        query = query.limit(filters.size).offset(offset)

        result = await session.execute(query)
        items = [row._asdict() for row in result.all()]

        pages = math.ceil(total / filters.size) if filters.size > 0 else 0

        return {
            "items": items,
            "total": total,
            "page": filters.page,
            "size": filters.size,
            "pages": pages,
        }

    async def get_detail(self, session: AsyncSession, announcement_id: int) -> dict:
        """상세 조회 (PK)"""
        result = await session.execute(
            select(Announcement).where(Announcement.id == announcement_id)
        )
        row = result.scalar_one_or_none()

        if row is None:
            raise AppException(
                status_code=404,
                detail=f"공고를 찾을 수 없습니다: id={announcement_id}",
                error_code="NOT_FOUND",
            )

        # ORM 인스턴스 → dict 변환 + computed 필드 추가
        data = {c.name: getattr(row, c.name) for c in Announcement.__table__.columns}
        raw = data.get('raw_data') or {}
        data['contract_method'] = raw.get('bidwinrDcsnMthdNm') or None
        openg_date = raw.get('opengDate', '')
        openg_tm = raw.get('opengTm', '')
        if openg_date:
            try:
                data['openg_dt'] = datetime.fromisoformat(f"{openg_date}T{openg_tm or '00:00'}:00")
            except (ValueError, TypeError):
                data['openg_dt'] = None
        else:
            data['openg_dt'] = None
        return data

    async def get_stats(
        self,
        session: AsyncSession,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        """통계 (카테고리별, 점수구간별, 상태별, 월별 트렌드)"""
        # 날짜 파싱
        parsed_from = self._parse_date(date_from, "date_from") if date_from else None
        parsed_to = self._parse_date(date_to, "date_to") if date_to else None

        def _date_filter(q):
            if parsed_from:
                q = q.where(Announcement.collected_at >= parsed_from)
            if parsed_to:
                q = q.where(Announcement.collected_at <= parsed_to)
            return q

        # 전체 통계
        overall_q = _date_filter(
            select(
                func.count().label("total_count"),
                func.round(func.avg(Announcement.relevance_score), 1).label("avg_score"),
                func.coalesce(func.sum(Announcement.presmpt_price), 0).label("total_budget"),
            )
        )
        overall = (await session.execute(overall_q)).one()

        # 카테고리별
        cat_q = _date_filter(
            select(
                Announcement.category,
                func.count().label("cnt"),
            ).group_by(Announcement.category)
        )
        cat_rows = (await session.execute(cat_q)).all()
        by_category = {(r.category or "미분류"): r.cnt for r in cat_rows}

        # 점수 구간별
        score_range_expr = case(
            (Announcement.relevance_score >= 80, "80-100"),
            (Announcement.relevance_score >= 60, "60-79"),
            (Announcement.relevance_score >= 40, "40-59"),
            else_="0-39",
        )
        score_q = _date_filter(
            select(
                score_range_expr.label("score_range"),
                func.count().label("cnt"),
            ).group_by(score_range_expr)
        )
        score_rows = (await session.execute(score_q)).all()
        by_score_range = {"80-100": 0, "60-79": 0, "40-59": 0, "0-39": 0}
        for r in score_rows:
            by_score_range[r.score_range] = r.cnt

        # 상태별
        status_q = _date_filter(
            select(
                Announcement.status,
                func.count().label("cnt"),
            ).group_by(Announcement.status)
        )
        status_rows = (await session.execute(status_q)).all()
        by_status = {r.status: r.cnt for r in status_rows}

        # 월별 트렌드
        month_expr = func.to_char(Announcement.collected_at, "YYYY-MM")
        trend_q = _date_filter(
            select(
                month_expr.label("month"),
                func.count().label("count"),
                func.round(func.avg(Announcement.relevance_score), 1).label("avg_score"),
                func.coalesce(func.sum(Announcement.presmpt_price), 0).label("total_budget"),
            )
            .where(Announcement.collected_at.isnot(None))
            .group_by(month_expr)
            .order_by(month_expr)
        )
        trend_rows = (await session.execute(trend_q)).all()
        trend = [
            {
                "month": r.month,
                "count": r.count,
                "avg_score": float(r.avg_score or 0),
                "total_budget": int(r.total_budget),
            }
            for r in trend_rows
        ]

        return {
            "total_count": overall.total_count or 0,
            "by_category": by_category,
            "by_score_range": by_score_range,
            "by_status": by_status,
            "avg_score": float(overall.avg_score or 0),
            "total_budget": int(overall.total_budget),
            "trend": trend,
        }

    async def update_status(
        self, session: AsyncSession, announcement_id: int, new_status: str
    ) -> dict:
        """상태 변경"""
        allowed = {"pending", "analyzed", "reviewing", "bidding", "excluded", "archived"}
        if new_status not in allowed:
            raise AppException(
                status_code=400,
                detail=f"status 값이 유효하지 않습니다: '{new_status}'",
                error_code="INVALID_STATUS",
            )

        result = await session.execute(
            select(Announcement).where(Announcement.id == announcement_id)
        )
        row = result.scalar_one_or_none()

        if row is None:
            raise AppException(
                status_code=404,
                detail=f"공고를 찾을 수 없습니다: id={announcement_id}",
                error_code="NOT_FOUND",
            )

        row.status = new_status
        await session.commit()
        await session.refresh(row)

        # TODO: Phase 4 — Notion 상태 동기화

        return {
            "id": row.id,
            "bid_notice_no": row.bid_notice_no,
            "status": row.status,
            "updated_at": row.updated_at,
        }

    async def export_list(
        self, session: AsyncSession, filters, export_format: str = "csv"
    ) -> StreamingResponse:
        """CSV/XLSX 내보내기"""
        if export_format not in ("csv", "xlsx"):
            raise AppException(
                status_code=400,
                detail="format은 csv 또는 xlsx만 가능합니다",
                error_code="INVALID_PARAMETER",
            )

        # 내보내기 컬럼
        columns = [getattr(Announcement, field) for _, field in EXPORT_COLUMNS]
        query = select(*columns)
        query = self._apply_filters(query, filters)

        # 정렬
        sort_col = SORT_COLUMN_MAP.get(filters.sort.value, Announcement.created_at)
        if filters.order.value == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        query = query.limit(EXPORT_MAX_ROWS)

        result = await session.execute(query)
        rows = result.all()

        today_str = date.today().strftime("%Y%m%d")
        headers = [h for h, _ in EXPORT_COLUMNS]

        if export_format == "csv":
            return self._build_csv_response(headers, rows, today_str)
        else:
            return self._build_xlsx_response(headers, rows, today_str)

    # ── private helpers ──────────────────────────────────

    def _apply_filters(self, query, filters):
        """공통 필터 조건 적용"""
        # 카테고리
        try:
            category_list = filters.get_category_list()
        except ValueError as e:
            raise AppException(
                status_code=400, detail=str(e), error_code="INVALID_PARAMETER"
            )
        if category_list:
            query = query.where(Announcement.category.in_(category_list))

        # 최소 점수
        if filters.min_score is not None:
            query = query.where(Announcement.relevance_score >= filters.min_score)

        # 상태
        if filters.status is not None:
            query = query.where(Announcement.status == filters.status)

        # 수집일 범위
        if filters.date_from:
            parsed = self._parse_date(filters.date_from, "date_from")
            query = query.where(Announcement.collected_at >= parsed)
        if filters.date_to:
            parsed = self._parse_date(filters.date_to, "date_to")
            query = query.where(Announcement.collected_at <= parsed)

        # 텍스트 검색
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(
                Announcement.bid_notice_nm.ilike(search_term)
                | Announcement.summary.ilike(search_term)
            )

        return query

    @staticmethod
    def _parse_date(value: str, field_name: str) -> datetime:
        """YYYY-MM-DD 문자열을 datetime으로 변환"""
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise AppException(
                status_code=400,
                detail=f"{field_name} 형식이 올바르지 않습니다 (YYYY-MM-DD)",
                error_code="INVALID_PARAMETER",
            )

    @staticmethod
    def _build_csv_response(headers, rows, today_str) -> StreamingResponse:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([
                str(v) if v is not None else "" for v in row
            ])
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="announcements_{today_str}.csv"'
            },
        )

    @staticmethod
    def _build_xlsx_response(headers, rows, today_str) -> StreamingResponse:
        wb = Workbook()
        ws = wb.active
        ws.title = "공고목록"
        ws.append(headers)
        for row in rows:
            ws.append([
                str(v) if isinstance(v, datetime) else v
                for v in row
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="announcements_{today_str}.xlsx"'
            },
        )
