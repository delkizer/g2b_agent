"""관리자 계정 관리 스크립트

사용:
    cd ~/work/g2b_agent
    source .venv/bin/activate

    python scripts/seed_admin.py seed                       # 관리자 계정 생성
    python scripts/seed_admin.py passwd                     # 비밀번호 변경 (프롬프트 입력)
    python scripts/seed_admin.py passwd --password NEW_PW   # 비밀번호 변경 (인자 지정)
    python scripts/seed_admin.py help                       # 도움말
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# server/ 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from sqlalchemy import select
from database.connection import get_session, init_db
from models.user import User
from services.auth_service import AuthService
from loguru import logger


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin1234"
ADMIN_DISPLAY_NAME = "관리자"


async def cmd_seed():
    """관리자 계정 생성 (이미 존재하면 스킵)"""
    await init_db()

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.username == ADMIN_USERNAME)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"이미 존재하는 관리자 계정: {ADMIN_USERNAME}")
            return

        password_hash = AuthService.hash_password(ADMIN_PASSWORD)
        user = User(
            username=ADMIN_USERNAME,
            password_hash=password_hash,
            display_name=ADMIN_DISPLAY_NAME,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        logger.info(f"관리자 계정 생성 완료: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")


async def cmd_passwd(new_password: str | None):
    """관리자 비밀번호 변경"""
    await init_db()

    if not new_password:
        new_password = getpass.getpass("새 비밀번호: ")
        confirm = getpass.getpass("비밀번호 확인: ")
        if new_password != confirm:
            logger.error("비밀번호가 일치하지 않습니다.")
            sys.exit(1)

    if len(new_password) < 4:
        logger.error("비밀번호는 4자 이상이어야 합니다.")
        sys.exit(1)

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.username == ADMIN_USERNAME)
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.error(f"관리자 계정이 존재하지 않습니다. 먼저 seed를 실행하세요.")
            sys.exit(1)

        user.password_hash = AuthService.hash_password(new_password)
        user.refresh_token = None
        user.token_expire_at = None
        await session.commit()
        logger.info(f"비밀번호 변경 완료: {ADMIN_USERNAME}")


def print_help():
    print("""
관리자 계정 관리 스크립트
========================

사용법:
    python scripts/seed_admin.py <command> [options]

명령어:
    seed                            관리자 계정 생성 (admin / admin1234)
                                    이미 존재하면 스킵

    passwd                          관리자 비밀번호 변경 (프롬프트 입력)
    passwd --password NEW_PW        관리자 비밀번호 변경 (인자 지정)

    help                            이 도움말 표시

예시:
    python scripts/seed_admin.py seed
    python scripts/seed_admin.py passwd
    python scripts/seed_admin.py passwd --password myNewPass123
""".strip())


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?", default="help")
    parser.add_argument("--password", dest="password", default=None)

    args = parser.parse_args()

    if args.command == "seed":
        asyncio.run(cmd_seed())
    elif args.command == "passwd":
        asyncio.run(cmd_passwd(args.password))
    else:
        print_help()


if __name__ == "__main__":
    main()
