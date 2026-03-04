"""파일 서빙 라우터 — 첨부파일/output 다운로드 + bid_context 조회/동기화"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from apps.dependencies import verify_api_key
from apps.exceptions import AppException
from database.connection import get_session
from services.announcement_service import AnnouncementService
from services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])


# ── 고정 경로 (동적 {bid_notice_no}보다 먼저 선언) ─────────

@router.post("/sync-all", dependencies=[Depends(verify_api_key)])
async def sync_all_bid_contexts(
    session: AsyncSession = Depends(get_session),
):
    """모든 bid_context.md → DB 일괄 동기화"""
    file_service = FileService()
    announcement_service = AnnouncementService()

    notices = file_service.list_bid_context_notices()
    results = {"synced": 0, "failed": 0, "details": []}

    for bid_notice_no in notices:
        try:
            analysis_data = file_service.parse_bid_context_json(bid_notice_no)
            if analysis_data is None:
                results["failed"] += 1
                results["details"].append({
                    "bid_notice_no": bid_notice_no,
                    "status": "failed",
                    "reason": "JSON 파싱 실패",
                })
                continue

            result = await announcement_service.sync_from_bid_context(
                session, bid_notice_no, analysis_data
            )
            results["synced"] += 1
            results["details"].append({
                "bid_notice_no": bid_notice_no,
                "status": "synced",
                "relevance_score": result["relevance_score"],
            })
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "bid_notice_no": bid_notice_no,
                "status": "failed",
                "reason": str(e),
            })
            logger.warning(f"bid_context 동기화 실패: {bid_notice_no} — {e}")

    logger.info(f"bid_context 일괄 동기화: {results['synced']}건 성공, {results['failed']}건 실패")
    return results


# ── 동적 경로 ─────────────────────────────────────────────

@router.get("/{bid_notice_no}/attachments")
def list_attachments(bid_notice_no: str):
    service = FileService()
    return {
        "bid_notice_no": bid_notice_no,
        "files": service.list_attachments(bid_notice_no),
    }


@router.post(
    "/{bid_notice_no}/attachments",
    dependencies=[Depends(verify_api_key)],
)
async def upload_attachments(
    bid_notice_no: str,
    files: list[UploadFile] = File(...),
):
    """첨부파일 업로드 (복수 파일)"""
    service = FileService()
    saved = await service.save_attachments(bid_notice_no, files)
    logger.info(f"첨부파일 업로드: {bid_notice_no} — {len(saved)}건")
    return {
        "bid_notice_no": bid_notice_no,
        "uploaded": len(saved),
        "files": saved,
    }


@router.get("/{bid_notice_no}/attachments/{filename:path}")
def download_attachment(bid_notice_no: str, filename: str):
    service = FileService()
    file_path = service.get_attachment_path(bid_notice_no, filename)
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_path.name)}"
        },
    )


@router.get("/{bid_notice_no}/outputs")
def list_output_files(bid_notice_no: str):
    service = FileService()
    return {
        "bid_notice_no": bid_notice_no,
        "files": service.list_output_files(bid_notice_no),
    }


@router.post(
    "/{bid_notice_no}/outputs",
    dependencies=[Depends(verify_api_key)],
)
async def upload_output_files(
    bid_notice_no: str,
    files: list[UploadFile] = File(...),
):
    """생성 문서 업로드 (bid_context.md 등)"""
    service = FileService()
    saved = await service.save_output_files(bid_notice_no, files)
    logger.info(f"생성 문서 업로드: {bid_notice_no} — {len(saved)}건")
    return {
        "bid_notice_no": bid_notice_no,
        "uploaded": len(saved),
        "files": saved,
    }


@router.get("/{bid_notice_no}/outputs/{filename:path}")
def download_output_file(bid_notice_no: str, filename: str):
    service = FileService()
    file_path = service.get_output_file_path(bid_notice_no, filename)
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_path.name)}"
        },
    )


@router.get("/{bid_notice_no}/bid-context")
def get_bid_context(bid_notice_no: str):
    service = FileService()
    content = service.read_bid_context(bid_notice_no)
    return {
        "bid_notice_no": bid_notice_no,
        "exists": content is not None,
        "content": content,
    }


@router.post("/{bid_notice_no}/sync-context", dependencies=[Depends(verify_api_key)])
async def sync_bid_context(
    bid_notice_no: str,
    session: AsyncSession = Depends(get_session),
):
    """bid_context.md JSON → DB 동기화 (단건)"""
    file_service = FileService()
    analysis_data = file_service.parse_bid_context_json(bid_notice_no)

    if analysis_data is None:
        raise AppException(
            status_code=404,
            detail=f"bid_context.md를 찾을 수 없거나 JSON 파싱 실패: {bid_notice_no}",
            error_code="BID_CONTEXT_NOT_FOUND",
        )

    announcement_service = AnnouncementService()
    return await announcement_service.sync_from_bid_context(
        session, bid_notice_no, analysis_data
    )
