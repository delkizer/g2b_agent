"""공통 의존성 (FastAPI Depends)"""

from fastapi import Header

from apps.exceptions import AppException
from config.config import Config


async def verify_api_key(x_api_key: str = Header(...)):
    """에이전트 전용 API Key 인증 의존성"""
    config = Config()
    if x_api_key != config.internal_api_key:
        raise AppException(
            status_code=401,
            detail="Invalid or missing API Key",
            error_code="UNAUTHORIZED",
        )
