"""Pipeline 도메인 — 유틸리티 함수

datetime 직렬화/역직렬화 헬퍼.
pipeline_runner, repository 등에서 공통 사용.
"""

from datetime import datetime


def parse_timestamptz(value) -> datetime | None:
    """문자열/datetime → datetime 변환 (TIMESTAMPTZ 컬럼용)

    Args:
        value: ISO 8601 문자열, datetime 객체, 또는 None

    Returns:
        datetime 객체 또는 None
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def serialize_dt(value) -> str | None:
    """datetime → ISO 8601 문자열 변환 (JSON 페이로드용)

    Args:
        value: datetime 객체 또는 문자열 또는 None

    Returns:
        ISO 8601 문자열 또는 None
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None
