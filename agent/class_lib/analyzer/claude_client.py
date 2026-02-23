"""Analyzer 도메인 — Claude API 클라이언트

Anthropic Claude API 호출을 담당한다.
단일 공고 분석 및 배치 분석 기능을 제공한다.

참조:
- docs/analyzer/01-analyzer-overview.md §3.1 : ClaudeClient 인터페이스
- docs/analyzer/02-prompt-design.md §9.5 : PromptBuilder 연동
"""

import asyncio
import json
import time

import anthropic
from loguru import logger

from config.config import Config
from class_lib.analyzer.prompt_builder import PromptBuilder
from class_lib.analyzer.scoring import Scoring


# ── 상수 ────────────────────────────────────────────────────

# API 호출 재시도 횟수
MAX_RETRIES = 2

# 재시도 기본 대기 시간 (초)
BASE_RETRY_DELAY = 2.0

# 배치 분석 기본 동시성
DEFAULT_CONCURRENCY = 3


class ClaudeClient:
    """Claude API 클라이언트

    Anthropic Claude API를 호출하여 공고 분석을 수행한다.
    PromptBuilder로 프롬프트를 생성하고, Scoring으로 결과를 검증한다.
    """

    def __init__(self):
        self.config = Config()
        self.client = anthropic.AsyncAnthropic(
            api_key=self.config.claude_api_key
        )
        self.model = self.config.claude_model
        self.max_tokens = self.config.claude_max_tokens
        self.prompt_builder = PromptBuilder()
        self.scoring = Scoring()

        # 프롬프트 템플릿 로드
        self.prompt_builder.load_templates()

    # ── 단일 API 호출 ───────────────────────────────────────

    async def analyze(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int = None,
    ) -> dict:
        """Claude API 호출 → JSON 응답 반환

        재시도 2회, 지수 백오프 적용.

        Args:
            system_prompt: 시스템 프롬프트
            user_content: 사용자 프롬프트 (공고 데이터)
            max_tokens: 응답 최대 토큰 (미지정 시 Config 기본값)

        Returns:
            파싱된 JSON dict. 실패 시 빈 dict.

        Raises:
            anthropic.AuthenticationError: API 키 오류 (즉시 raise)
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_content}
                    ],
                )

                # 응답 텍스트 추출
                raw_text = response.content[0].text.strip()

                # JSON 파싱 (코드블록 래핑 제거)
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("\n", 1)[-1]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3].strip()

                return json.loads(raw_text)

            except anthropic.AuthenticationError:
                logger.error("Claude API 인증 실패 — API 키를 확인하세요")
                raise

            except anthropic.RateLimitError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Rate limit 도달, {delay}초 후 재시도 "
                        f"({attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(delay)
                    continue

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Claude 응답 JSON 파싱 실패: {e}"
                )
                return {}

            except anthropic.APIError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"API 오류 ({e}), {delay}초 후 재시도 "
                        f"({attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(delay)
                    continue

            except Exception as e:
                logger.error(f"Claude API 호출 중 예외: {e}")
                return {}

        # 모든 재시도 소진
        logger.error(
            f"Claude API 호출 실패 (재시도 {MAX_RETRIES}회 소진): "
            f"{last_error}"
        )
        return {}

    # ── 단일 공고 분석 ──────────────────────────────────────

    async def analyze_announcement(self, announcement: dict) -> dict:
        """단일 공고 분석

        PromptBuilder로 프롬프트를 생성하고,
        Claude API를 호출한 뒤,
        Scoring으로 결과를 검증한다.

        Args:
            announcement: 수집된 공고 데이터 dict

        Returns:
            정규화된 분석 결과 dict. 실패 시 빈 dict.
        """
        bid_notice_nm = announcement.get("bid_notice_nm", "알 수 없음")
        bid_notice_no = announcement.get("bid_notice_no", "")

        logger.info(
            f"공고 분석 시작: [{bid_notice_no}] {bid_notice_nm}"
        )
        start_time = time.perf_counter()

        # 프롬프트 생성
        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(announcement)

        # Claude API 호출
        claude_response = await self.analyze(system_prompt, user_prompt)

        if not claude_response:
            logger.warning(
                f"공고 분석 실패: [{bid_notice_no}] {bid_notice_nm}"
            )
            return {}

        # 점수 추출 및 검증
        result = self.scoring.extract_analysis(claude_response)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            f"공고 분석 완료: [{bid_notice_no}] {bid_notice_nm} "
            f"→ {result['category']} / {result['relevance_score']}점 "
            f"({elapsed_ms}ms)"
        )

        return result

    # ── 배치 분석 ───────────────────────────────────────────

    async def analyze_batch(
        self,
        announcements: list[dict],
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> list[dict]:
        """공고 일괄 분석 (동시성 제어)

        asyncio.Semaphore로 동시 API 호출 수를 제한한다.

        Args:
            announcements: 분석 대상 공고 리스트
            concurrency: 최대 동시 호출 수 (기본 3)

        Returns:
            분석 결과 리스트 (실패한 공고는 빈 dict)
        """
        if not announcements:
            return []

        logger.info(
            f"배치 분석 시작: {len(announcements)}건, "
            f"동시성 {concurrency}"
        )
        start_time = time.perf_counter()

        semaphore = asyncio.Semaphore(concurrency)

        async def _analyze_with_semaphore(announcement: dict) -> dict:
            async with semaphore:
                return await self.analyze_announcement(announcement)

        # 모든 공고를 비동기 분석
        tasks = [
            _analyze_with_semaphore(ann) for ann in announcements
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외를 빈 dict으로 변환
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                bid_notice_no = announcements[i].get(
                    "bid_notice_no", "알 수 없음"
                )
                logger.error(
                    f"공고 분석 예외: [{bid_notice_no}] {result}"
                )
                processed_results.append({})
            else:
                processed_results.append(result)

        # 배치 이상치 탐지
        scores = [
            r["relevance_score"]
            for r in processed_results
            if r and "relevance_score" in r
        ]
        self.scoring.check_batch_anomaly(scores)

        # 통계 로그
        success_count = sum(1 for r in processed_results if r)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            f"배치 분석 완료: {success_count}/{len(announcements)}건 성공 "
            f"({elapsed_ms}ms)"
        )

        return processed_results
