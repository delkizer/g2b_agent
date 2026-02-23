"""키워드 기반 공고 필터링

나라장터 API에서 수집된 공고 중 SPOTV 관련 가능성이 있는 공고만 선별한다.
1차/2차/기관/복합/제외 키워드를 조합한 다단계 매칭 알고리즘을 사용한다.

참조:
- docs/collector/03-filter-rules.md : 키워드 사전, 매칭 알고리즘, 클래스 상세 설계
- docs/shared/01-data-schema.md : 카테고리 값 정의
"""

import time

from loguru import logger

from config.config import Config
from class_lib.collector.schemas import (
    CollectedAnnouncement,
    FilteredAnnouncement,
    FilterMeta,
)


class KeywordFilter:
    """키워드 기반 공고 필터링

    나라장터 API에서 수집된 공고 중 SPOTV 관련 가능성이 있는 공고만 선별한다.
    1차/2차/기관/복합/제외 키워드를 조합한 다단계 매칭 알고리즘을 사용한다.

    Attributes:
        config: 설정 인스턴스 (키워드 오버라이드 등)
        logger: 로거 인스턴스
    """

    # ─── 기본 키워드 상수 (Config에서 오버라이드 가능) ─────────

    DEFAULT_PRIMARY_KEYWORDS: dict[str, list[str]] = {
        "스포츠": [
            "스포츠", "체육", "경기", "종목", "선수", "리그", "대회",
            "e스포츠", "esports",
        ],
        "영상분석": [
            "영상분석", "비디오분석", "동작분석", "영상처리",
            "영상인식", "비전",
        ],
        "AI": [
            "AI", "인공지능", "머신러닝", "딥러닝", "기계학습",
            "자연어처리", "NLP",
        ],
        "데이터": [
            "빅데이터", "데이터분석", "데이터플랫폼",
            "데이터웨어하우스", "데이터레이크",
        ],
        "미디어": [
            "중계", "방송", "OTT", "스트리밍", "콘텐츠제작",
            "라이브", "미디어",
        ],
    }

    DEFAULT_SECONDARY_KEYWORDS: dict[str, list[str]] = {
        "플랫폼": ["플랫폼", "시스템", "포털"],
        "분석": ["분석", "모니터링", "통계", "시각화", "대시보드"],
        "콘텐츠": ["콘텐츠", "미디어", "멀티미디어"],
        "영상": ["영상", "비디오", "CCTV", "카메라"],
        "데이터": ["데이터", "DB", "정보화"],
    }

    DEFAULT_INSTITUTIONAL_KEYWORDS: list[str] = [
        "체육", "스포츠", "올림픽", "경기단", "구단",
        "대한체육회", "국민체육진흥공단", "체육진흥공단",
        "스포츠산업진흥원",
        "방송", "미디어", "콘텐츠진흥원",
        "한국방송공사", "KBS", "MBC", "SBS",
        "한국콘텐츠진흥원",
        "문화체육관광부",
    ]

    DEFAULT_EXCLUSION_KEYWORDS: list[str] = [
        "의료영상", "의료AI", "의료데이터", "진료", "병원정보",
        "보건의료", "전자처방", "의약", "질병",
        "건설데이터", "건축", "토목", "시공", "측량", "BIM",
        "교통영상", "교통데이터", "도로", "교량", "신호등", "자율주행",
        "환경모니터링", "환경데이터", "하수", "상수", "폐수",
        "대기질", "미세먼지측정",
        "농업", "농산물", "산림", "축산", "어업", "스마트팜",
        "군사", "국방데이터", "무기체계",
    ]

    DEFAULT_COMPOUND_KEYWORDS: list[str] = [
        "스포츠 데이터", "스포츠 분석", "스포츠 플랫폼",
        "스포츠 영상", "스포츠 과학",
        "경기 분석", "경기 영상", "경기력 향상",
        "영상 분석", "동작 분석", "실시간 영상", "영상 데이터",
        "AI 분석", "AI 플랫폼", "AI 데이터",
        "온라인 중계", "실시간 중계",
        "방송 시스템", "중계 시스템", "콘텐츠 플랫폼",
        "데이터 분석 플랫폼", "데이터 시각화", "데이터 수집 분석",
    ]

    def __init__(self):
        self.config = Config()
        self._load_keywords()

    def _load_keywords(self) -> None:
        """키워드 사전을 로드한다.

        Phase 1: 클래스 상수(DEFAULT_*)를 사용한다.
        Phase 2: agent/config/keywords.json 외부 파일에서 로드 (향후).

        키워드는 Config(환경변수)로 관리하지 않는다.
        구조화된 데이터(dict/list)는 환경변수에 적합하지 않으므로,
        Phase 2에서 별도 JSON 파일로 분리한다.
        """
        # 1차 키워드 (dict → 플랫 리스트로 변환하여 내부 저장)
        primary_dict = self.DEFAULT_PRIMARY_KEYWORDS
        self._primary_keywords: list[str] = self._flatten_keyword_dict(primary_dict)
        self._primary_keyword_dict: dict[str, list[str]] = primary_dict

        # 2차 키워드
        secondary_dict = self.DEFAULT_SECONDARY_KEYWORDS
        self._secondary_keywords: list[str] = self._flatten_keyword_dict(secondary_dict)
        self._secondary_keyword_dict: dict[str, list[str]] = secondary_dict

        # 기관 키워드
        self._institutional_keywords: list[str] = self.DEFAULT_INSTITUTIONAL_KEYWORDS

        # 제외 키워드
        self._exclusion_keywords: list[str] = self.DEFAULT_EXCLUSION_KEYWORDS

        # 복합 키워드
        self._compound_keywords: list[str] = self.DEFAULT_COMPOUND_KEYWORDS

        # 정규화된 키워드 캐시 (성능 최적화)
        self._normalized_primary = [self._normalize(k) for k in self._primary_keywords]
        self._normalized_secondary = [self._normalize(k) for k in self._secondary_keywords]
        self._normalized_institutional = [self._normalize(k) for k in self._institutional_keywords]
        self._normalized_exclusion = [self._normalize(k) for k in self._exclusion_keywords]
        self._normalized_compound = [self._normalize(k) for k in self._compound_keywords]

        logger.info(
            f"KeywordFilter 로드 완료: "
            f"1차={len(self._primary_keywords)}, "
            f"2차={len(self._secondary_keywords)}, "
            f"기관={len(self._institutional_keywords)}, "
            f"제외={len(self._exclusion_keywords)}, "
            f"복합={len(self._compound_keywords)}"
        )

    # ─── 공개 메서드 ──────────────────────────────────────

    def filter(self, announcements: list[CollectedAnnouncement]) -> list[FilteredAnnouncement]:
        """키워드 매칭된 공고만 반환한다.

        각 공고에 대해 _matches()를 수행하고, 통과한 공고를
        FilteredAnnouncement로 변환하여 반환한다.

        성능 모니터링 포함 (처리 시간, 건수/초).

        Args:
            announcements: 나라장터 API 수집 결과 리스트 (CollectedAnnouncement)

        Returns:
            필터 통과 공고 리스트 (FilteredAnnouncement with filter_meta)
        """
        start = time.perf_counter()
        filtered = []
        stats = {"total": len(announcements), "passed": 0, "excluded": 0}

        for ann in announcements:
            meta = self._matches(ann)

            if not meta.excluded and meta.matched_keywords:
                # FilteredAnnouncement 생성 (Pydantic 모델)
                filtered_ann = FilteredAnnouncement(
                    **ann.model_dump(),
                    filter_meta=meta
                )
                filtered.append(filtered_ann)
                stats["passed"] += 1
            elif meta.excluded:
                stats["excluded"] += 1

        elapsed = time.perf_counter() - start

        logger.info(
            f"KeywordFilter 결과: "
            f"전체={stats['total']}, "
            f"통과={stats['passed']}, "
            f"제외={stats['excluded']}, "
            f"필터율={self._calc_filter_rate(stats)}%, "
            f"{elapsed*1000:.1f}ms 소요, "
            f"{len(announcements)/elapsed:.0f} 건/초"
        )

        return filtered

    # ─── 내부 메서드 ──────────────────────────────────────

    def _matches(self, announcement: CollectedAnnouncement) -> FilterMeta:
        """공고의 키워드 매칭 여부를 판정한다.

        5단계 매칭 알고리즘 (03-filter-rules.md 4.1절 흐름도 참조):
        1. 제외 키워드 체크 (공고명)
        2. 복합 키워드 매칭 (공고명)
        3. 1차 키워드 매칭 (공고명)
        4. 2차 키워드 매칭 (공고명)
        5. 기관 키워드 매칭 (수요기관명, 공고기관명)

        Args:
            announcement: CollectedAnnouncement 인스턴스

        Returns:
            FilterMeta 인스턴스 (매칭 결과)
        """
        # 텍스트 추출 및 정규화
        bid_name = self._normalize(announcement.bid_notice_nm)
        dminstt_name = self._normalize(announcement.dminstt_nm)
        ntce_instt_name = self._normalize(announcement.ntce_instt_nm)

        all_matched_keywords = []
        all_match_fields = []
        all_categories = []

        # ── Step 1: 제외 키워드 체크 ──
        for i, kw in enumerate(self._normalized_exclusion):
            if kw in bid_name:
                return FilterMeta(
                    matched_keywords=[],
                    match_fields=[],
                    keyword_priority=None,
                    matched_categories=[],
                    excluded=True,
                    exclusion_keyword=self._exclusion_keywords[i],
                )

        # ── Step 2: 복합 키워드 매칭 (공고명) ──
        compound_matched = []
        for i, kw in enumerate(self._normalized_compound):
            if kw in bid_name:
                compound_matched.append(self._compound_keywords[i])
        if compound_matched:
            all_matched_keywords.extend(compound_matched)
            all_match_fields.append("bid_notice_nm")

        # ── Step 3: 1차 키워드 매칭 (공고명) ──
        primary_matched = []
        for i, kw in enumerate(self._normalized_primary):
            if kw in bid_name:
                primary_matched.append(self._primary_keywords[i])
        if primary_matched:
            all_matched_keywords.extend(primary_matched)
            if "bid_notice_nm" not in all_match_fields:
                all_match_fields.append("bid_notice_nm")

        # ── Step 4: 2차 키워드 매칭 (공고명) ──
        secondary_matched = []
        for i, kw in enumerate(self._normalized_secondary):
            if kw in bid_name:
                secondary_matched.append(self._secondary_keywords[i])
        if secondary_matched:
            all_matched_keywords.extend(secondary_matched)
            if "bid_notice_nm" not in all_match_fields:
                all_match_fields.append("bid_notice_nm")

        # ── Step 5: 기관 키워드 매칭 (수요기관명, 공고기관명) ──
        institutional_matched = []
        for i, kw in enumerate(self._normalized_institutional):
            if kw in dminstt_name:
                institutional_matched.append(self._institutional_keywords[i])
                if "dminstt_nm" not in all_match_fields:
                    all_match_fields.append("dminstt_nm")
            if kw in ntce_instt_name:
                institutional_matched.append(self._institutional_keywords[i])
                if "ntce_instt_nm" not in all_match_fields:
                    all_match_fields.append("ntce_instt_nm")
        if institutional_matched:
            all_matched_keywords.extend(institutional_matched)

        # ── 결과 판정 ──
        if not all_matched_keywords:
            return FilterMeta(
                matched_keywords=[],
                match_fields=[],
                keyword_priority=None,
                matched_categories=[],
                excluded=False,
                exclusion_keyword=None,
            )

        # 우선순위 결정
        if compound_matched or primary_matched:
            priority = "primary"
        elif secondary_matched:
            priority = "secondary"
        else:
            priority = "institutional"

        # 카테고리 수집
        all_categories = self._resolve_categories(all_matched_keywords)

        # 중복 제거
        unique_keywords = list(dict.fromkeys(all_matched_keywords))
        unique_fields = list(dict.fromkeys(all_match_fields))
        unique_categories = list(dict.fromkeys(all_categories))

        return FilterMeta(
            matched_keywords=unique_keywords,
            match_fields=unique_fields,
            keyword_priority=priority,
            matched_categories=unique_categories,
            excluded=False,
            exclusion_keyword=None,
        )

    # ─── 유틸리티 메서드 ──────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """텍스트를 정규화한다 (소문자 변환 + strip)."""
        return text.lower().strip()

    @staticmethod
    def _flatten_keyword_dict(keyword_dict: dict[str, list[str]]) -> list[str]:
        """카테고리별 키워드 dict를 플랫 리스트로 변환한다."""
        result = []
        for keywords in keyword_dict.values():
            result.extend(keywords)
        return result

    def _resolve_categories(self, keywords: list[str]) -> list[str]:
        """키워드 목록에서 해당하는 카테고리 목록을 추출한다.

        키워드 → 카테고리 매핑:
        - 1차 키워드: 키워드 dict의 key가 카테고리
        - 2차 키워드: 키워드 dict의 key가 카테고리
        - 복합/기관 키워드: 포함된 단일 키워드의 카테고리를 상속
        """
        categories = set()

        # 1차 키워드 카테고리 매핑
        for cat, kw_list in self._primary_keyword_dict.items():
            for kw in keywords:
                if kw in kw_list:
                    categories.add(self._map_to_schema_category(cat))

        # 2차 키워드 카테고리 매핑
        for cat, kw_list in self._secondary_keyword_dict.items():
            for kw in keywords:
                if kw in kw_list:
                    categories.add(self._map_to_schema_category(cat))

        return list(categories)

    @staticmethod
    def _map_to_schema_category(filter_category: str) -> str:
        """필터 내부 카테고리를 shared 스키마 카테고리로 매핑한다.

        shared/01-data-schema.md 카테고리:
        스포츠, 영상분석, AI/데이터, 미디어, 플랫폼, 기타
        """
        mapping = {
            "스포츠": "스포츠",
            "영상분석": "영상분석",
            "AI": "AI/데이터",
            "데이터": "AI/데이터",
            "미디어": "미디어",
            "플랫폼": "플랫폼",
            "분석": "AI/데이터",
            "콘텐츠": "미디어",
            "영상": "영상분석",
        }
        return mapping.get(filter_category, "기타")

    @staticmethod
    def _calc_filter_rate(stats: dict) -> str:
        """필터율을 계산한다 (통과하지 못한 비율)."""
        if stats["total"] == 0:
            return "0.0"
        rate = (1 - stats["passed"] / stats["total"]) * 100
        return f"{rate:.1f}"
