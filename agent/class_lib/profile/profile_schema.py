"""Analysis Profile Pydantic 스키마

프로필 JSON 파일의 구조를 정의하고 검증한다.

참조:
- CLAUDE.md : Analysis Profile 시스템 설계
"""

import typing

from pydantic import BaseModel, Field, model_validator


class CompanyCapability(BaseModel):
    """회사 역량 항목"""
    domain: str = Field(..., description="역량 도메인")
    details: str = Field(..., description="역량 상세 설명")


class CompanyInfo(BaseModel):
    """회사 정보"""
    name: str = Field(..., description="회사명")
    description: str = Field(..., description="회사 소개")
    capabilities: list[CompanyCapability] = Field(
        ..., description="핵심 역량 목록", min_length=1
    )


class KeywordsConfig(BaseModel):
    """키워드 설정"""
    primary: dict[str, list[str]] = Field(
        ..., description="1차 키워드 (카테고리: [키워드 목록])"
    )
    secondary: dict[str, list[str]] = Field(
        ..., description="2차 키워드 (카테고리: [키워드 목록])"
    )
    institutional: list[str] = Field(
        ..., description="기관 키워드 목록"
    )
    exclusion: list[str] = Field(
        ..., description="제외 키워드 목록"
    )
    compound: list[str] = Field(
        ..., description="복합 키워드 목록"
    )


class CategoriesConfig(BaseModel):
    """카테고리 설정"""
    categories: typing.List[str] = Field(
        ..., alias="list", description="카테고리 목록", min_length=1
    )
    keyword_to_category_map: dict[str, str] = Field(
        ..., description="필터 키워드 카테고리 → 스키마 카테고리 매핑"
    )
    priority_order: typing.List[str] = Field(
        ..., description="카테고리 우선순위 (높은 순서)"
    )

    model_config = {"populate_by_name": True}


class ScoringDimension(BaseModel):
    """점수 차원 정의"""
    weight: float = Field(..., description="가중치 (0.0 ~ 1.0)", ge=0.0, le=1.0)
    label: str = Field(..., description="차원 표시 이름")


class ScoringConfig(BaseModel):
    """점수 산출 설정"""
    dimensions: dict[str, ScoringDimension] = Field(
        ..., description="차원별 가중치 정의"
    )
    default_score: int = Field(
        50, description="누락 차원 기본 점수", ge=0, le=100
    )
    score_tolerance: int = Field(
        5, description="Claude 보고값과 가중합산 허용 오차", ge=0
    )

    @model_validator(mode="after")
    def validate_weights_sum(self):
        total = sum(d.weight for d in self.dimensions.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"차원 가중치 합이 1.0이어야 합니다 (현재: {total:.2f})"
            )
        return self


class PromptsConfig(BaseModel):
    """프롬프트 설정"""
    template_dir: str = Field(
        "prompts", description="프롬프트 디렉토리 (프로필 디렉토리 기준 상대 경로)"
    )
    system_files: list[str] = Field(
        ..., description="시스템 프롬프트 파일 목록 (결합 순서)"
    )
    examples_file: str = Field(
        "examples.md", description="Few-shot 예시 파일명"
    )


class AnalysisProfile(BaseModel):
    """Analysis Profile 전체 스키마"""
    profile_id: str = Field(..., description="프로필 식별자")
    company: CompanyInfo
    keywords: KeywordsConfig
    categories: CategoriesConfig
    scoring: ScoringConfig
    prompts: PromptsConfig
