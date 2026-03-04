"""Analysis Profile 로더

프로필 JSON을 로드하고 Pydantic으로 검증한다.
싱글톤 패턴으로 동일 프로세스 내 1회만 로드한다.

참조:
- CLAUDE.md : Analysis Profile 시스템 설계
- config/config.py : profile_id 프로퍼티
"""

import json
from pathlib import Path

from loguru import logger

from class_lib.profile.profile_schema import AnalysisProfile
from config.config import Config


# ── 프로필 디렉토리 루트 ──────────────────────────────────
# agent/profiles/
PROFILES_ROOT = Path(__file__).resolve().parent.parent.parent / "profiles"


# ── 싱글톤 캐시 ───────────────────────────────────────────
_profile: AnalysisProfile | None = None


def get_profile() -> AnalysisProfile:
    """현재 프로필을 반환한다 (싱글톤).

    최초 호출 시 Config.profile_id에 해당하는 프로필 JSON을 로드하고,
    이후 호출에서는 캐시된 인스턴스를 반환한다.

    Returns:
        AnalysisProfile 인스턴스

    Raises:
        FileNotFoundError: 프로필 디렉토리 또는 profile.json이 없을 때
        ValueError: profile.json 검증 실패 시
    """
    global _profile
    if _profile is not None:
        return _profile

    config = Config()
    profile_id = config.profile_id
    _profile = load_profile(profile_id)
    return _profile


def load_profile(profile_id: str) -> AnalysisProfile:
    """지정 프로필을 로드하고 검증한다.

    Args:
        profile_id: 프로필 식별자 (디렉토리명)

    Returns:
        AnalysisProfile 인스턴스

    Raises:
        FileNotFoundError: 프로필 디렉토리 또는 profile.json이 없을 때
        ValueError: profile.json 검증 실패 시
    """
    profile_dir = PROFILES_ROOT / profile_id

    if not profile_dir.exists():
        raise FileNotFoundError(
            f"프로필 디렉토리 없음: {profile_dir}"
        )

    json_path = profile_dir / "profile.json"
    if not json_path.exists():
        raise FileNotFoundError(
            f"프로필 파일 없음: {json_path}"
        )

    # JSON 로드
    raw = json.loads(json_path.read_text(encoding="utf-8"))

    # Pydantic 검증
    profile = AnalysisProfile.model_validate(raw)

    # 프롬프트 디렉토리 존재 확인
    prompts_dir = profile_dir / profile.prompts.template_dir
    if not prompts_dir.exists():
        raise FileNotFoundError(
            f"프롬프트 디렉토리 없음: {prompts_dir}"
        )

    logger.info(
        f"프로필 로드 완료: {profile.profile_id} "
        f"({profile.company.name})"
    )

    return profile


def get_profile_prompts_dir() -> Path:
    """현재 프로필의 프롬프트 디렉토리 경로를 반환한다."""
    profile = get_profile()
    return PROFILES_ROOT / profile.profile_id / profile.prompts.template_dir


def reset_profile() -> None:
    """프로필 캐시를 초기화한다 (테스트용)."""
    global _profile
    _profile = None
