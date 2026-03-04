"""Analyzer 도메인 — 적합성 점수 처리

Claude 분석 결과에서 점수를 추출/검증/보정한다.
점수 산출 자체는 Claude가 수행하며, 이 클래스는 결과를 검증한다.

참조:
- docs/analyzer/03-scoring-model.md §8 : 클래스 설계
- docs/analyzer/02-prompt-design.md §6 : JSON 스키마 정의
"""

from collections import Counter

from loguru import logger

from config.config import Config
from class_lib.profile.profile_loader import get_profile


class Scoring:
    """적합성 점수 처리

    Claude 분석 결과에서 점수를 추출/검증/보정한다.
    점수 산출 자체는 Claude가 수행하며, 이 클래스는 결과를 검증한다.
    """

    def __init__(self):
        self.config = Config()

        # 프로필에서 점수 설정 로드
        profile = get_profile()
        scoring = profile.scoring

        self._dimension_weights: dict[str, float] = {
            key: dim.weight
            for key, dim in scoring.dimensions.items()
        }
        self._dimension_keys: list[str] = list(self._dimension_weights.keys())
        self._default_score: int = scoring.default_score
        self._score_tolerance: int = scoring.score_tolerance

    # ── 점수 범위 검증 ──────────────────────────────────────

    def validate_score(self, score: int) -> int:
        """점수 범위 검증 (0-100)

        Args:
            score: 검증 대상 점수

        Returns:
            0-100 범위 내로 클램핑된 점수
        """
        clamped = max(0, min(100, score))
        if clamped != score:
            logger.warning(f"점수 범위 초과 보정: {score} → {clamped}")
        return clamped

    # ── Claude 응답 파싱 + 정규화 ────────────────────────────

    def extract_analysis(self, claude_response: dict) -> dict:
        """Claude 응답에서 구조화된 분석 결과 추출

        차원별 점수 검증, 가중합산 교차검증, 범위 클램핑을 수행한다.

        Args:
            claude_response: Claude API JSON 응답

        Returns:
            정규화된 분석 결과 dict
        """
        # 차원별 점수 추출 및 검증
        dimensions = claude_response.get(
            "analysis_detail", {}
        ).get("dimensions", {})
        validated_dimensions = self._validate_dimensions(dimensions)

        # 최종 점수: Claude 보고값 vs 가중합산 비교 검증
        reported_score = claude_response.get("relevance_score", 0)
        final_score = self.verify_weighted_sum(
            validated_dimensions, reported_score
        )
        final_score = self.validate_score(final_score)

        return {
            "category": claude_response.get("category", "기타"),
            "relevance_score": final_score,
            "summary": claude_response.get("summary", ""),
            "requirements": claude_response.get("requirements", ""),
            "needs_research_lab": claude_response.get(
                "needs_research_lab", False
            ),
            "analysis_detail": {
                "dimensions": validated_dimensions,
                "key_factors": claude_response.get(
                    "analysis_detail", {}
                ).get("key_factors", []),
                "risks": claude_response.get(
                    "analysis_detail", {}
                ).get("risks", []),
            },
        }

    # ── 가중합산 교차 검증 ───────────────────────────────────

    def verify_weighted_sum(
        self, dimensions: dict, reported_score: int
    ) -> int:
        """차원별 가중 합산 결과와 Claude 보고 점수 비교

        차이가 score_tolerance 초과 시 가중합산 결과를 우선 사용한다.

        Args:
            dimensions: 검증 완료된 차원별 점수 dict
            reported_score: Claude가 보고한 relevance_score

        Returns:
            최종 사용할 점수
        """
        calculated = sum(
            dimensions.get(key, {}).get("score", self._default_score)
            * weight
            for key, weight in self._dimension_weights.items()
        )
        calculated = round(calculated)

        if abs(calculated - reported_score) > self._score_tolerance:
            logger.warning(
                f"점수 불일치 — Claude 보고: {reported_score}, "
                f"가중합산: {calculated}. 가중합산 값 사용"
            )
            return calculated
        return reported_score

    # ── 배치 이상치 탐지 ─────────────────────────────────────

    def check_batch_anomaly(self, scores: list[int]) -> None:
        """배치 단위 점수 이상치 탐지

        동일 점수 집중, 극단값 편중 패턴을 감시한다.

        Args:
            scores: 배치 내 전체 relevance_score 목록
        """
        if not scores:
            return

        counter = Counter(scores)
        most_common_count = counter.most_common(1)[0][1]

        # 동일 점수 집중 (80% 이상이 동일 점수)
        if most_common_count / len(scores) >= 0.8:
            logger.warning(
                f"점수 이상: 배치 {len(scores)}건 중 "
                f"{most_common_count}건이 동일 점수"
            )

        # 극단값 편중 (70% 이상이 90+ 또는 10-)
        extreme_count = sum(1 for s in scores if s >= 90 or s <= 10)
        if extreme_count / len(scores) >= 0.7:
            logger.warning(
                f"점수 이상: 배치 {len(scores)}건 중 "
                f"{extreme_count}건이 극단값 (90+ 또는 10-)"
            )

    # ── 차원별 검증 (내부) ───────────────────────────────────

    def _validate_dimensions(self, dimensions: dict) -> dict:
        """차원별 점수 검증 및 누락 보정

        프로필에 정의된 차원 모두 존재하는지 확인하고,
        누락 시 기본값을 적용한다.

        Args:
            dimensions: Claude 응답의 dimensions 객체

        Returns:
            검증/보정된 dimensions dict
        """
        validated = {}
        for key in self._dimension_keys:
            if key in dimensions:
                dim = dimensions[key]
                validated[key] = {
                    "score": self.validate_score(
                        dim.get("score", self._default_score)
                    ),
                    "reason": dim.get("reason", ""),
                }
            else:
                logger.warning(
                    f"차원 누락: {key} → 기본값 {self._default_score} 적용"
                )
                validated[key] = {
                    "score": self._default_score,
                    "reason": "차원 누락으로 기본값 적용",
                }
        return validated
