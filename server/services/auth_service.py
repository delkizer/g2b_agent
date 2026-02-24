"""인증 비즈니스 로직 — JWT (RS256) + bcrypt"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import Config
from models.user import User


class AuthService:
    def __init__(self, logger):
        self.config = Config()
        self.logger = logger
        self._private_key = self._load_key("private_key.pem")
        self._public_key = self._load_key("public_key.pem")

    def _load_key(self, filename: str) -> str:
        key_path = self.config.jwt_key_path / filename
        return key_path.read_text()

    # ── 비밀번호 ──────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    # ── JWT 생성 ──────────────────────────────────────

    def create_access_token(self, user_id: int, username: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": self.config.jwt_sub,
            "user_id": user_id,
            "username": username,
            "iat": now,
            "exp": now + timedelta(minutes=self.config.jwt_expire_minutes),
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def create_refresh_token(self, user_id: int, username: str) -> tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        expire_at = now + timedelta(days=7)
        payload = {
            "sub": self.config.jwt_sub,
            "user_id": user_id,
            "username": username,
            "type": "refresh",
            "iat": now,
            "exp": expire_at,
        }
        token = jwt.encode(payload, self._private_key, algorithm="RS256")
        return token, expire_at

    # ── JWT 검증 ──────────────────────────────────────

    def verify_access_token(self, token: str) -> dict | None:
        try:
            payload = jwt.decode(token, self._public_key, algorithms=["RS256"])
            if payload.get("type") == "refresh":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def verify_refresh_token(self, token: str) -> dict | None:
        try:
            payload = jwt.decode(token, self._public_key, algorithms=["RS256"])
            if payload.get("type") != "refresh":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # ── DB 조회/저장 ──────────────────────────────────

    async def authenticate_user(self, session: AsyncSession, username: str, password: str) -> User | None:
        result = await session.execute(
            select(User).where(User.username == username, User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()
        if user is None or not self.verify_password(password, user.password_hash):
            return None
        return user

    async def save_refresh_token(self, session: AsyncSession, user_id: int, token: str, expire_at: datetime) -> None:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.refresh_token = token
            user.token_expire_at = expire_at
            await session.commit()

    async def delete_refresh_token(self, session: AsyncSession, user_id: int) -> None:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.refresh_token = None
            user.token_expire_at = None
            await session.commit()

    async def get_user_by_id(self, session: AsyncSession, user_id: int) -> User | None:
        result = await session.execute(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    # ── 현재 사용자 추출 (쿠키 우선 → Header 폴백) ───

    async def get_current_user(self, request: Request, session: AsyncSession) -> User | None:
        token = request.cookies.get("access_token")

        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return None

        payload = self.verify_access_token(token)
        if payload is None:
            return None

        user_id = payload.get("user_id")
        if user_id is None:
            return None

        return await self.get_user_by_id(session, user_id)

    async def validate_refresh_token_db(self, session: AsyncSession, user_id: int, token: str) -> bool:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.refresh_token != token:
            return False
        if user.token_expire_at and user.token_expire_at < datetime.now(timezone.utc):
            return False
        return True
