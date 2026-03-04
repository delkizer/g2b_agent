"""Analyzer 도메인 — 프롬프트 생성기

프로필의 프롬프트 디렉토리에서 .md 파일을 로드하고,
시스템/사용자 프롬프트를 생성한다.
시스템 프롬프트는 캐싱하여 동일 배치 내 재사용한다.

참조:
- docs/analyzer/02-prompt-design.md §9 : PromptBuilder 클래스 설계
- docs/analyzer/02-prompt-design.md §7 : 사용자 프롬프트 설계
"""

import json
from pathlib import Path

from loguru import logger

from config.config import Config
from class_lib.profile.profile_loader import get_profile, get_profile_prompts_dir


# ── 상수 ────────────────────────────────────────────────────

# 원문 최대 길이 (자)
MAX_RAW_CONTENT_LENGTH = 3000

# 파일 결합 구분자
FILE_SEPARATOR = "\n\n---\n\n"


class PromptBuilder:
    """프롬프트 생성기

    프로필의 프롬프트 디렉토리에서 .md 파일을 로드하고,
    시스템/사용자 프롬프트를 생성한다.
    """

    def __init__(self):
        self.config = Config()
        self._templates: dict[str, str] = {}
        self._system_prompt_cache: str | None = None

        # 프로필에서 프롬프트 설정 로드
        profile = get_profile()
        self._system_prompt_files: list[str] = profile.prompts.system_files
        self._examples_file: str = profile.prompts.examples_file

    # ── 템플릿 로드 ─────────────────────────────────────────

    def load_templates(self, prompts_dir: str = None) -> None:
        """프롬프트 .md 파일 로드 + 메모리 캐싱

        Args:
            prompts_dir: 프롬프트 디렉토리 경로. 미지정 시 프로필 prompts 디렉토리 사용.
        """
        if prompts_dir is None:
            prompts_dir = str(get_profile_prompts_dir())

        prompts_path = Path(prompts_dir)

        if not prompts_path.exists():
            logger.error(f"프롬프트 디렉토리 없음: {prompts_dir}")
            return

        # 필수 파일 로드
        for filename in self._system_prompt_files:
            filepath = prompts_path / filename
            if filepath.exists():
                self._templates[filename] = filepath.read_text(
                    encoding="utf-8"
                )
                logger.info(
                    f"프롬프트 로드: {filename} "
                    f"({len(self._templates[filename])}자)"
                )
            else:
                logger.warning(f"프롬프트 파일 없음: {filepath}")

        # 선택적 Few-shot 파일 로드
        examples_path = prompts_path / self._examples_file
        if examples_path.exists():
            self._templates[self._examples_file] = examples_path.read_text(
                encoding="utf-8"
            )
            logger.info(
                f"프롬프트 로드: {self._examples_file} "
                f"({len(self._templates[self._examples_file])}자)"
            )

        # 캐시 초기화 (재로드 시 기존 캐시 무효화)
        self._system_prompt_cache = None

    # ── 시스템 프롬프트 생성 ─────────────────────────────────

    def build_system_prompt(self, include_examples: bool = True) -> str:
        """시스템 프롬프트 생성 (파일 결합)

        Args:
            include_examples: Few-shot 예시 포함 여부 (토큰 예산에 따라 조절)

        Returns:
            결합된 시스템 프롬프트 문자열
        """
        # 캐시 반환 (동일 배치 내 재사용)
        if self._system_prompt_cache is not None:
            return self._system_prompt_cache

        if not self._templates:
            logger.warning(
                "로드된 프롬프트 템플릿 없음. load_templates()를 먼저 호출하세요."
            )
            return ""

        parts = []

        # 필수 파일 결합
        for filename in self._system_prompt_files:
            if filename in self._templates:
                parts.append(self._templates[filename])

        # 선택적 Few-shot 예시 추가
        if include_examples and self._examples_file in self._templates:
            parts.append(self._templates[self._examples_file])

        system_prompt = FILE_SEPARATOR.join(parts)
        self._system_prompt_cache = system_prompt

        logger.info(
            f"시스템 프롬프트 생성: {len(parts)}개 파일 결합, "
            f"총 {len(system_prompt)}자"
        )
        return system_prompt

    # ── 사용자 프롬프트 생성 ─────────────────────────────────

    def build_user_prompt(self, announcement: dict) -> str:
        """공고 데이터를 사용자 프롬프트로 변환

        Args:
            announcement: 수집된 공고 데이터 dict

        Returns:
            사용자 프롬프트 문자열
        """
        # 필드 추출
        bid_notice_nm = announcement.get("bid_notice_nm", "")
        bid_notice_no = announcement.get("bid_notice_no", "")
        ntce_instt_nm = announcement.get("ntce_instt_nm", "미상")
        dminstt_nm = announcement.get("dminstt_nm", "미상")
        presmpt_price = announcement.get("presmpt_price", 0)
        bid_begin_dt = announcement.get("bid_begin_dt", "미정")
        bid_close_dt = announcement.get("bid_close_dt", "미정")

        # 추정가격 포맷
        price_formatted = self._format_price(presmpt_price)

        # 원문 내용 추출
        raw_content = self._extract_raw_content(announcement)

        # 프롬프트 조립
        prompt = (
            "아래 나라장터 공고를 분석하세요.\n"
            "\n"
            "---\n"
            "\n"
            "## 공고 정보\n"
            "\n"
            f"- **공고명**: {bid_notice_nm}\n"
            f"- **공고번호**: {bid_notice_no}\n"
            f"- **공고기관**: {ntce_instt_nm}\n"
            f"- **수요기관**: {dminstt_nm}\n"
            f"- **추정가격**: {price_formatted}\n"
            f"- **입찰개시일**: {bid_begin_dt}\n"
            f"- **입찰마감일**: {bid_close_dt}\n"
            "\n"
            "## 공고 상세 내용\n"
            "\n"
            f"{raw_content}\n"
            "\n"
            "---\n"
            "\n"
            "위 공고를 분석하여 JSON으로 응답하세요."
        )

        return prompt

    # ── 캐시 관리 ───────────────────────────────────────────

    def invalidate_cache(self) -> None:
        """시스템 프롬프트 캐시 무효화

        프롬프트 파일 재로드 후 호출하거나,
        다른 설정으로 재생성이 필요할 때 사용.
        """
        self._system_prompt_cache = None

    # ── 내부 유틸리티 ───────────────────────────────────────

    def _format_price(self, price: int) -> str:
        """추정가격을 읽기 쉬운 형식으로 변환

        Args:
            price: 추정가격 (원)

        Returns:
            포맷된 가격 문자열 (예: "5.0억 원 (500,000,000원)")
        """
        if not isinstance(price, (int, float)) or price <= 0:
            return "미공개"

        price = int(price)
        raw = f"{price:,}원"

        if price >= 100_000_000:  # 1억 이상
            eok = price / 100_000_000
            return f"{eok:.1f}억 원 ({raw})"
        elif price >= 10_000:  # 1만 이상
            man = price / 10_000
            return f"{man:.0f}만 원 ({raw})"
        else:
            return raw

    def _extract_raw_content(self, announcement: dict) -> str:
        """공고 원문 내용 추출

        raw_data에서 상세 내용을 추출하며, 최대 3000자로 제한한다.

        우선순위:
        1. raw_data.bidNtceDtl — 입찰공고 상세 내용
        2. raw_data.ntceInsttOfclNm + purchsObjPrdctList — 조달 물품 목록
        3. raw_data 전체 JSON 폴백

        Args:
            announcement: 공고 데이터 dict

        Returns:
            추출된 원문 내용 문자열
        """
        raw_data = announcement.get("raw_data", {})

        # 우선순위 1: 입찰공고 상세 내용
        content = raw_data.get("bidNtceDtl", "")

        # 우선순위 2: 조달 물품 목록 등 조합
        if not content:
            parts = []
            if raw_data.get("ntceInsttOfclNm"):
                parts.append(f"담당자: {raw_data['ntceInsttOfclNm']}")
            if raw_data.get("purchsObjPrdctList"):
                parts.append(
                    f"조달품목: {raw_data['purchsObjPrdctList']}"
                )
            content = "\n".join(parts)

        # 우선순위 3: raw_data 전체 JSON 폴백
        if not content and raw_data:
            content = json.dumps(raw_data, ensure_ascii=False, indent=2)

        # 빈 내용 처리
        if not content:
            return "(공고 상세 내용 없음)"

        # 길이 제한
        if len(content) > MAX_RAW_CONTENT_LENGTH:
            total_len = len(content)
            content = content[:MAX_RAW_CONTENT_LENGTH]
            content += (
                f"\n\n[... 원문 일부 생략 "
                f"(전체 {total_len}자 중 "
                f"{MAX_RAW_CONTENT_LENGTH}자까지 표시)]"
            )

        return content
