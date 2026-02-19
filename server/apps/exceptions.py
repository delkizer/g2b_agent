"""커스텀 예외 + 핸들러

에러 코드 체계:
    UNAUTHORIZED      — 401  인증 실패
    NOT_FOUND         — 404  리소스 없음
    VALIDATION_ERROR  — 400  요청 데이터 유효성 검사 실패
    INVALID_PARAMETER — 400  잘못된 파라미터 값
    INVALID_STATUS    — 400  유효하지 않은 상태 값
    EMPTY_BATCH       — 400  빈 배치
    DATABASE_ERROR    — 503  DB 연결/쿼리 실패
    INTERNAL_ERROR    — 500  서버 내부 오류
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, status_code: int, detail: str, error_code: str):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.error_code,
        },
    )
