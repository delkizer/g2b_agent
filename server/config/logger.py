"""loguru 로거 설정 (server)

서버 시작 시 setup_logger()를 1회 호출한다.
각 모듈에서는 `from loguru import logger`로 직접 사용.

uvicorn/fastapi 내부 로거도 loguru로 통합하여
모든 로그(에러 traceback 포함)가 파일에 기록된다.

사용법:
    # main.py (엔트리포인트)
    from config.logger import setup_logger
    setup_logger()

    # 각 모듈
    from loguru import logger
    logger.info("메시지")
"""

import logging
import sys
from pathlib import Path

from loguru import logger


LOG_DIR = Path.home() / "work" / "logs" / "g2b_server"


class _InterceptHandler(logging.Handler):
    """표준 logging → loguru 리다이렉트 핸들러"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


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

    # uvicorn/fastapi 로거 → loguru 통합
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        target = logging.getLogger(name)
        target.handlers = [_InterceptHandler()]
        target.propagate = False
