"""파일 서빙 서비스 — 첨부파일/output 파일 업로드/조회/다운로드 + bid_context 파싱"""

import json
import re
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from config.config import Config


# 파일 확장자 → 타입 라벨
EXTENSION_LABELS = {
    ".pdf": "PDF",
    ".hwp": "한글",
    ".hwpx": "한글",
    ".docx": "Word",
    ".doc": "Word",
    ".xlsx": "Excel",
    ".xls": "Excel",
    ".pptx": "PPT",
    ".ppt": "PPT",
    ".zip": "압축",
    ".txt": "텍스트",
    ".md": "마크다운",
}


class FileService:
    """첨부파일/output 파일 목록 조회 + 다운로드 경로 검증"""

    def __init__(self):
        self.config = Config()

    def _list_files(self, base_dir: str, bid_notice_no: str) -> list[dict]:
        """디렉토리 내 파일 목록 반환"""
        directory = Path(base_dir) / bid_notice_no
        if not directory.is_dir():
            return []

        files = []
        for f in sorted(directory.iterdir()):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            files.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "extension": ext,
                "type_label": EXTENSION_LABELS.get(ext, ext.lstrip(".").upper() or "파일"),
            })
        return files

    def list_attachments(self, bid_notice_no: str) -> list[dict]:
        return self._list_files(self.config.attachments_base_dir, bid_notice_no)

    def list_output_files(self, bid_notice_no: str) -> list[dict]:
        return self._list_files(self.config.output_base_dir, bid_notice_no)

    def _validate_and_resolve(self, base_dir: str, bid_notice_no: str, filename: str) -> Path:
        """경로 보안 검증 후 절대 경로 반환"""
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

        file_path = (Path(base_dir) / bid_notice_no / filename).resolve()
        base_resolved = Path(base_dir).resolve()

        if not str(file_path).startswith(str(base_resolved)):
            raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")

        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        return file_path

    def get_attachment_path(self, bid_notice_no: str, filename: str) -> Path:
        return self._validate_and_resolve(
            self.config.attachments_base_dir, bid_notice_no, filename
        )

    def get_output_file_path(self, bid_notice_no: str, filename: str) -> Path:
        return self._validate_and_resolve(
            self.config.output_base_dir, bid_notice_no, filename
        )

    async def save_files(
        self, base_dir: str, bid_notice_no: str, files: list[UploadFile]
    ) -> list[dict]:
        """파일을 {base_dir}/{bid_notice_no}/ 에 저장. 저장 결과 목록 반환."""
        directory = Path(base_dir) / bid_notice_no
        directory.mkdir(parents=True, exist_ok=True)

        saved = []
        for upload_file in files:
            filename = Path(upload_file.filename or "unknown").name
            if ".." in filename or "/" in filename or "\\" in filename:
                continue

            dest = directory / filename
            content = await upload_file.read()
            dest.write_bytes(content)

            ext = dest.suffix.lower()
            saved.append({
                "filename": filename,
                "size": len(content),
                "extension": ext,
                "type_label": EXTENSION_LABELS.get(ext, ext.lstrip(".").upper() or "파일"),
            })

        return saved

    async def save_attachments(
        self, bid_notice_no: str, files: list[UploadFile]
    ) -> list[dict]:
        return await self.save_files(
            self.config.attachments_base_dir, bid_notice_no, files
        )

    async def save_output_files(
        self, bid_notice_no: str, files: list[UploadFile]
    ) -> list[dict]:
        return await self.save_files(
            self.config.output_base_dir, bid_notice_no, files
        )

    def read_bid_context(self, bid_notice_no: str) -> Optional[str]:
        """bid_context.md 내용 읽기. 없으면 None."""
        context_path = Path(self.config.output_base_dir) / bid_notice_no / "bid_context.md"
        if not context_path.is_file():
            return None
        return context_path.read_text(encoding="utf-8")

    def parse_bid_context_json(self, bid_notice_no: str) -> Optional[dict]:
        """bid_context.md에서 분석 JSON 블록 파싱. 없으면 None."""
        content = self.read_bid_context(bid_notice_no)
        if not content:
            return None

        match = re.search(r'```json\s*\n(.+?)\n```', content, re.DOTALL)
        if not match:
            return None

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def list_bid_context_notices(self) -> list[str]:
        """bid_context.md가 존재하는 공고번호 목록 반환."""
        output_dir = Path(self.config.output_base_dir)
        if not output_dir.is_dir():
            return []
        return sorted(
            d.name for d in output_dir.iterdir()
            if d.is_dir() and (d / "bid_context.md").is_file()
        )
