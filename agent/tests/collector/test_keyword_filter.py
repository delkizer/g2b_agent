"""KeywordFilter 단위 테스트 (15건)

순수 로직 테스트 — Mock 없음.
"""

import pytest

from class_lib.collector.keyword_filter import KeywordFilter


# ============================================================
# KF-01~02: 1차 키워드
# ============================================================


class TestPrimaryKeywords:
    def test_kf01_sports(self, make_announcement):
        """KF-01: 1차 키워드 '스포츠' 매칭 → priority=primary"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="스포츠 중계 시스템 구축")
        result = kf.filter([ann])
        assert len(result) == 1
        assert result[0].filter_meta.keyword_priority == "primary"
        assert "스포츠" in result[0].filter_meta.matched_keywords

    def test_kf02_ai(self, make_announcement):
        """KF-02: 1차 키워드 'AI' 매칭"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="AI 기반 데이터분석 시스템")
        result = kf.filter([ann])
        assert len(result) == 1
        assert "AI" in result[0].filter_meta.matched_keywords


# ============================================================
# KF-03: 2차 키워드
# ============================================================


class TestSecondaryKeywords:
    def test_kf03_platform(self, make_announcement):
        """KF-03: 2차 키워드 '플랫폼' → priority=secondary"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="통합 플랫폼 운영 사업")
        result = kf.filter([ann])
        assert len(result) == 1
        assert result[0].filter_meta.keyword_priority == "secondary"


# ============================================================
# KF-04~05: 기관 키워드
# ============================================================


class TestInstitutionalKeywords:
    def test_kf04_dminstt(self, make_announcement):
        """KF-04: 수요기관 키워드 매칭 → priority=institutional"""
        kf = KeywordFilter()
        ann = make_announcement(
            bid_notice_nm="사무용품 구매",  # 공고명에는 매칭 키워드 없음
            dminstt_nm="대한체육회",
        )
        result = kf.filter([ann])
        assert len(result) == 1
        assert result[0].filter_meta.keyword_priority == "institutional"
        assert "dminstt_nm" in result[0].filter_meta.match_fields

    def test_kf05_ntce_instt(self, make_announcement):
        """KF-05: 공고기관 키워드 매칭"""
        kf = KeywordFilter()
        ann = make_announcement(
            bid_notice_nm="시설 보수 공사",
            ntce_instt_nm="문화체육관광부",
        )
        result = kf.filter([ann])
        assert len(result) == 1
        assert "ntce_instt_nm" in result[0].filter_meta.match_fields


# ============================================================
# KF-06: 복합 키워드
# ============================================================


class TestCompoundKeywords:
    def test_kf06_compound(self, make_announcement):
        """KF-06: 복합 키워드 '스포츠 데이터' 매칭"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="스포츠 데이터 분석 용역")
        result = kf.filter([ann])
        assert len(result) == 1
        assert "스포츠 데이터" in result[0].filter_meta.matched_keywords


# ============================================================
# KF-07~08: 제외 키워드
# ============================================================


class TestExclusionKeywords:
    def test_kf07_exclusion_priority(self, make_announcement):
        """KF-07: 제외 키워드 우선 — '의료영상'이 있으면 '영상' 매칭 무시"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="의료영상 AI 진단 시스템")
        result = kf.filter([ann])
        assert len(result) == 0

    def test_kf08_exclusion_meta(self, make_announcement):
        """KF-08: 제외 시 FilterMeta.excluded=True, exclusion_keyword 설정"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="건축 BIM 데이터 플랫폼")
        # _matches를 직접 호출하여 meta 확인
        meta = kf._matches(ann)
        assert meta.excluded is True
        assert meta.exclusion_keyword is not None


# ============================================================
# KF-09: 대소문자 무시
# ============================================================


class TestCaseInsensitive:
    def test_kf09_case_insensitive(self, make_announcement):
        """KF-09: 대소문자 무시 ('ESPORTS' → 'esports')"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="ESPORTS 리그 운영 용역")
        result = kf.filter([ann])
        assert len(result) == 1


# ============================================================
# KF-10~11: 빈 입력 / 미매칭
# ============================================================


class TestEdgeCases:
    def test_kf10_empty_input(self):
        """KF-10: 빈 리스트 입력 → 빈 결과"""
        kf = KeywordFilter()
        result = kf.filter([])
        assert result == []

    def test_kf11_no_match(self, make_announcement):
        """KF-11: 매칭되지 않는 공고 → 빈 결과"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="사무용 가구 구매")
        result = kf.filter([ann])
        assert result == []


# ============================================================
# KF-12: 다중 필드 매칭
# ============================================================


class TestMultiFieldMatch:
    def test_kf12_multiple_match_fields(self, make_announcement):
        """KF-12: 공고명 + 기관명 동시 매칭 → 복수 match_fields"""
        kf = KeywordFilter()
        ann = make_announcement(
            bid_notice_nm="스포츠 데이터 분석 시스템",
            dminstt_nm="대한체육회",
        )
        result = kf.filter([ann])
        assert len(result) == 1
        fields = result[0].filter_meta.match_fields
        assert "bid_notice_nm" in fields
        assert "dminstt_nm" in fields


# ============================================================
# KF-13: 카테고리 매핑
# ============================================================


class TestCategoryMapping:
    def test_kf13_category(self, make_announcement):
        """KF-13: 매칭 키워드 → shared 스키마 카테고리 매핑"""
        kf = KeywordFilter()
        ann = make_announcement(bid_notice_nm="AI 기반 빅데이터 분석 플랫폼")
        result = kf.filter([ann])
        assert len(result) == 1
        categories = result[0].filter_meta.matched_categories
        assert "AI/데이터" in categories


# ============================================================
# KF-14~15: 배치 필터링
# ============================================================


class TestBatchFilter:
    def test_kf14_batch(self, make_announcement):
        """KF-14: 배치 필터링 — 통과/미통과/제외 혼합"""
        kf = KeywordFilter()
        announcements = [
            make_announcement(bid_notice_no="001", bid_notice_nm="스포츠 중계 시스템"),
            make_announcement(bid_notice_no="002", bid_notice_nm="사무용 가구 구매"),
            make_announcement(bid_notice_no="003", bid_notice_nm="의료영상 AI 시스템"),
            make_announcement(bid_notice_no="004", bid_notice_nm="AI 분석 플랫폼"),
        ]
        result = kf.filter(announcements)
        passed_ids = [r.bid_notice_no for r in result]
        assert "001" in passed_ids  # 통과
        assert "002" not in passed_ids  # 미매칭
        assert "003" not in passed_ids  # 제외
        assert "004" in passed_ids  # 통과

    def test_kf15_empty_list(self):
        """KF-15: 빈 리스트 배치 → 빈 결과 (에러 없음)"""
        kf = KeywordFilter()
        result = kf.filter([])
        assert result == []
