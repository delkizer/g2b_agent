"""인증 라우터 — 4개 엔드포인트

1. POST /auth/login    — 로그인
2. POST /auth/refresh  — 토큰 갱신
3. GET  /auth/me       — 현재 사용자 정보
4. POST /auth/logout   — 로그아웃
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from apps.auth.schemas import LoginRequest, TokenResponse, UserResponse
from config.config import Config
from database.connection import get_session
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["인증"])


def _get_auth_service() -> AuthService:
    return AuthService(logger)


def _cookie_params() -> dict:
    config = Config()
    return {
        "httponly": True,
        "secure": config.set_cookie_secure,
        "samesite": config.set_cookie_samesite,
        "path": "/",
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(_get_auth_service),
):
    """로그인 → 쿠키 설정 + body 응답"""
    user = await auth_service.authenticate_user(session, body.username, body.password)
    if user is None:
        return JSONResponse(status_code=401, content={"detail": "아이디 또는 비밀번호가 올바르지 않습니다."})

    access_token = auth_service.create_access_token(user.id, user.username)
    refresh_token, expire_at = auth_service.create_refresh_token(user.id, user.username)

    await auth_service.save_refresh_token(session, user.id, refresh_token, expire_at)

    cookie = _cookie_params()
    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
    })
    response.set_cookie("access_token", access_token, **cookie)
    response.set_cookie("refresh_token", refresh_token, **cookie)

    logger.info(f"로그인 성공: {user.username}")
    return response


@router.post("/refresh")
async def refresh_token(
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(_get_auth_service),
):
    """쿠키에서 refresh_token → 새 access_token 쿠키 설정"""
    token = request.cookies.get("refresh_token")
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Refresh token이 없습니다."})

    payload = auth_service.verify_refresh_token(token)
    if payload is None:
        return JSONResponse(status_code=401, content={"detail": "Refresh token이 유효하지 않습니다."})

    user_id = payload.get("user_id")
    username = payload.get("username")

    valid = await auth_service.validate_refresh_token_db(session, user_id, token)
    if not valid:
        return JSONResponse(status_code=401, content={"detail": "Refresh token이 만료되었습니다."})

    new_access_token = auth_service.create_access_token(user_id, username)

    cookie = _cookie_params()
    response = JSONResponse(content={
        "access_token": new_access_token,
        "token_type": "bearer",
    })
    response.set_cookie("access_token", new_access_token, **cookie)
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(_get_auth_service),
):
    """현재 로그인 사용자 정보"""
    user = await auth_service.get_current_user(request, session)
    if user is None:
        return JSONResponse(status_code=401, content={"detail": "인증이 필요합니다."})

    return UserResponse(id=user.id, username=user.username, display_name=user.display_name)


@router.post("/logout")
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(_get_auth_service),
):
    """로그아웃 — 쿠키 삭제 + DB refresh_token 무효화"""
    user = await auth_service.get_current_user(request, session)
    if user:
        await auth_service.delete_refresh_token(session, user.id)
        logger.info(f"로그아웃: {user.username}")

    cookie = _cookie_params()
    cookie.pop("httponly", None)
    cookie.pop("secure", None)
    cookie.pop("samesite", None)

    response = JSONResponse(content={"detail": "로그아웃 완료"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response
