"""Collector 도메인 Pydantic 스키마

나라장터 API 응답 파싱, 내부 스키마 변환, 키워드 필터 결과를 위한 Pydantic 모델 정의.

참조:
- docs/collector/02-api-spec.md : API 응답 필드 (5.5절 53개 필드)
- docs/shared/01-data-schema.md : AnalyzedAnnouncement 스키마
- docs/collector/03-filter-rules.md : FilterMeta 구조 (5.1절)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 그룹 1: G2B API 응답 파싱 모델
# ============================================================


class G2BApiHeader(BaseModel):
    """API 응답 헤더

    나라장터 API 호출 결과 상태 정보.
    """
    resultCode: str = ""
    resultMsg: str = ""


class G2BApiItem(BaseModel):
    """나라장터 API 원본 응답 항목

    02-api-spec.md 5.5절 전체 53개 필드 중 주요 필드를 명시 정의.
    나머지 필드는 extra="allow"로 수용.

    주요 필드:
    - bidNtceNo: 입찰공고번호 (고유키)
    - bidNtceNm: 공고명 (키워드 필터링 핵심 대상)
    - ntceInsttNm: 공고기관명
    - dmndInsttNm: 수요기관명
    - presmptPrce: 추정가격 (문자열)
    - bidBeginDate/bidBeginTm: 입찰개시 일시
    - bidClseDate/bidClseTm: 입찰마감 일시
    - bidNtceUrl: 공고 URL
    """
    bidNtceNo: str = ""          # 입찰공고번호 (고유키)
    bidNtceOrd: str = "00"       # 입찰공고차수
    bidNtceNm: str = ""          # 공고명
    bidNtceSttusNm: str = ""     # 공고상태 (일반공고/긴급공고/정정공고/재공고/취소공고)
    bidNtceDate: str = ""        # 공고일자 (YYYY-MM-DD)
    bidNtceBgn: str = ""         # 공고시각 (HH:MM)
    bsnsDivNm: str = ""          # 업무구분 (물품/용역/공사/외자)
    intrntnlBidYn: str = ""      # 국제입찰여부
    cmmnCntrctYn: str = ""       # 공동계약여부
    elctrnBidYn: str = ""        # 전자입찰여부
    cntrctCnclsSttusNm: str = "" # 계약체결형태명
    cntrctCnclsMthdNm: str = ""  # 계약체결방법명
    bidwinrDcsnMthdNm: str = ""  # 낙찰자결정방법명
    ntceInsttNm: str = ""        # 공고기관명
    ntceInsttCd: str = ""        # 공고기관코드
    ntceInsttOfclDeptNm: str = ""    # 공고기관담당부서명
    ntceInsttOfclNm: str = ""        # 공고기관담당자명
    ntceInsttOfclTel: str = ""       # 공고기관담당자전화번호
    ntceInsttOfclEmailAdrs: str = "" # 공고기관담당자이메일
    dmndInsttNm: str = ""        # 수요기관명
    dmndInsttCd: str = ""        # 수요기관코드
    dmndInsttOfclDeptNm: str = ""    # 수요기관담당부서명
    dmndInsttOfclNm: str = ""        # 수요기관담당자명
    dmndInsttOfclTel: str = ""       # 수요기관담당자전화번호
    dmndInsttOfclEmailAdrs: str = "" # 수요기관담당자이메일
    presnatnOprtnYn: str = ""        # 설명회실시여부
    presnatnOprtnDate: str = ""      # 설명회실시일자
    presnatnOprtnTm: str = ""        # 설명회실시시각
    presnatnOprtnPlce: str = ""      # 설명회실시장소
    bidPrtcptQlfctRgstClseDate: str = ""  # 입찰참가자격등록마감일자
    bidPrtcptQlfctRgstClseTm: str = ""    # 입찰참가자격등록마감시각
    cmmnReciptAgrmntClseDate: str = ""    # 공동수급협정마감일자
    cmmnReciptAgrmntClseTm: str = ""      # 공동수급협정마감시각
    bidBeginDate: str = ""       # 입찰개시일자 (YYYY-MM-DD)
    bidBeginTm: str = ""         # 입찰개시시각 (HH:MM)
    bidClseDate: str = ""        # 입찰마감일자
    bidClseTm: str = ""          # 입찰마감시각
    opengDate: str = ""          # 개찰일자
    opengTm: str = ""            # 개찰시각
    opengPlce: str = ""          # 개찰장소
    asignBdgtAmt: str = ""       # 배정예산금액 (문자열)
    presmptPrce: str = ""        # 추정가격 (문자열)
    rsrvtnPrceDcsnMthdNm: str = "" # 예정가격결정방법명
    rgnLmtYn: str = ""           # 지역제한여부
    prtcptPsblRgnNm: str = ""    # 참가가능지역명
    indstrytyLmtYn: str = ""     # 업종제한여부
    bidprcPsblIndstrytyNm: str = ""  # 투찰가능업종명
    bidNtceUrl: str = ""         # 공고 URL
    ppsNtceYn: str = ""          # 나라장터공고여부
    dataBssDate: str = ""        # 데이터기준일자
    refNtceNo: str = ""          # 참조공고번호
    refNtceOrd: str = ""         # 참조공고차수
    cmmnReciptMethdNm: str = ""  # 공동수급방식명

    model_config = ConfigDict(extra="allow")


class G2BApiBody(BaseModel):
    """API 응답 body

    items 필드는 list 또는 {"item": [...]} 형태 모두 수용.
    단건 결과일 때 {"item": {...}} 형태도 발생 가능.
    """
    items: list | dict | None = None   # list 또는 {"item": [...]} 형태 모두 수용
    totalCount: int = 0
    numOfRows: int = 0
    pageNo: int = 0


class G2BApiResponseWrapper(BaseModel):
    """response 래퍼"""
    header: G2BApiHeader = Field(default_factory=G2BApiHeader)
    body: G2BApiBody = Field(default_factory=G2BApiBody)


class G2BApiResponse(BaseModel):
    """API 응답 최상위 구조: {"response": {"header": {...}, "body": {...}}}"""
    response: G2BApiResponseWrapper = Field(default_factory=G2BApiResponseWrapper)


# ============================================================
# 그룹 2: 내부 스키마 (API → 내부 매핑 결과)
# ============================================================


class CollectedAnnouncement(BaseModel):
    """수집 + 매핑된 공고 (shared/01-data-schema.md 기준)

    나라장터 API 응답을 내부 스키마로 변환한 결과.
    Analyzer가 설정하는 필드(category, relevance_score 등)는 미포함.

    필드 매핑:
    - bidNtceNo → bid_notice_no (고유키)
    - bidNtceNm → bid_notice_nm (공고명)
    - ntceInsttNm → ntce_instt_nm (공고기관명)
    - dmndInsttNm → dminstt_nm (수요기관명)
    - presmptPrce → presmpt_price (추정가격, int 변환)
    - bidBeginDate + bidBeginTm → bid_begin_dt (ISO 8601)
    - bidClseDate + bidClseTm → bid_close_dt (ISO 8601)
    - bidNtceUrl → link_url (공고 URL)
    - (전체 응답) → raw_data (원본 JSON 전체)
    - (수집 시각) → collected_at (ISO 8601)
    """
    bid_notice_no: str                            # 고유키
    bid_notice_nm: str                            # 공고명
    ntce_instt_nm: str = ""                       # 공고기관명
    dminstt_nm: str = ""                          # 수요기관명
    presmpt_price: int = 0                        # 추정가격 (원)
    bid_begin_dt: str = ""                        # ISO 8601
    bid_close_dt: str = ""                        # ISO 8601
    link_url: str = ""                            # 공고 URL
    raw_data: dict = Field(default_factory=dict)  # 원본 JSON 전체
    collected_at: str = ""                        # 수집 시각 ISO 8601


# ============================================================
# 그룹 3: 키워드 필터 결과
# ============================================================


class FilterMeta(BaseModel):
    """키워드 필터 결과 메타데이터 (03-filter-rules.md 5.1절)

    필터를 통과한 각 공고에 부여되는 메타데이터.
    Analyzer에서 분석 우선순위를 결정하고, 대시보드에서 필터링 근거를 표시하는 데 활용.

    필드:
    - matched_keywords: 매칭된 키워드 목록 (복합/단일 키워드 모두 포함)
    - match_fields: 키워드가 발견된 원본 필드명 목록 (bid_notice_nm, dminstt_nm, ntce_instt_nm)
    - keyword_priority: 가장 높은 우선순위 매칭 결과 (primary > secondary > institutional)
    - matched_categories: 매칭된 키워드가 속한 카테고리 목록 (스포츠, 영상분석, AI/데이터, 미디어, 플랫폼)
    - excluded: 제외 키워드에 의해 제외되었는지
    - exclusion_keyword: 제외 사유 키워드 (제외된 경우)
    """
    matched_keywords: list[str] = Field(default_factory=list)
    match_fields: list[str] = Field(default_factory=list)
    keyword_priority: str | None = None    # "primary" | "secondary" | "institutional"
    matched_categories: list[str] = Field(default_factory=list)
    excluded: bool = False
    exclusion_keyword: str | None = None


class FilteredAnnouncement(CollectedAnnouncement):
    """필터 통과 공고 (메타데이터 포함)

    CollectedAnnouncement를 상속하고 filter_meta 필드를 추가.
    Analyzer로 전달되는 최종 형태.
    """
    filter_meta: FilterMeta = Field(default_factory=FilterMeta)


# ============================================================
# 그룹 4: 수집 이력 (DB 모델)
# ============================================================


class CollectorHistory(BaseModel):
    """수집 이력 (g2b.collector_history 테이블 매핑)

    기존 collector_watermarks + collector_logs를 통합.
    - 수집 실행 이력 기록 (매 수집마다 1행)
    - 마지막 수집 시점 조회: status='success'인 최신 레코드의 collected_end_dt

    필드:
    - id: 레코드 ID (auto-increment)
    - operation: API 오퍼레이션명 (예: 'bid_announcement')
    - collected_at: 수집 실행 시각
    - collected_end_dt: API 조회 종료 시점 (다음 수집의 시작점)
    - total_count: 수집 건수
    - filtered_count: 필터 통과 건수
    - duration_ms: 처리 소요시간 (ms)
    - status: "success" | "failure"
    - error_message: 실패 시 에러 메시지
    """
    id: int | None = None
    operation: str                    # API 오퍼레이션명 (예: 'bid_announcement')
    collected_at: datetime            # 수집 실행 시각
    collected_end_dt: datetime        # API 조회 종료 시점 (다음 수집의 시작점)
    total_count: int = 0             # 수집 건수
    filtered_count: int = 0          # 필터 통과 건수
    duration_ms: int = 0             # 처리 소요시간 (ms)
    status: str = "success"          # "success" | "failure"
    error_message: str = ""          # 실패 시 에러 메시지
