"""loguru 로거 설정 (server)

서버 시작 시 setup_logger()를 1회 호출한다.
각 모듈에서는 `from loguru import logger`로 직접 사용.

사용법:
    # main.py (엔트리포인트)
    from config.logger import setup_logger
    setup_logger()

    # 각 모듈
    from loguru import logger
    logger.info("메시지")
"""

import sys
from pathlib import Path

from loguru import logger


LOG_DIR = Path.home() / "work" / "logs" / "g2b_server"


def setup_logger(level: str = "DEBUG", log_dir: Path | str | None = None) -> None:
    """loguru 로거를 설정한다.

    Args:
        level: 콘솔 출력 레벨 (DEBUG, INFO, WARNING, ERROR)
        log_dir: 로그 파일 디렉토리 (기본값: ~/work/logs/g2b_server)
    """
    logger.remove()

    # 콘솔 출력
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
    )

    # 파일 출력
    log_path = Path(log_dir) if log_dir else LOG_DIR
    log_path.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path / "server_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )
