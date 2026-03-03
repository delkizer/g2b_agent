// 서버 Pydantic 스키마 기반 TypeScript 타입
// 서버 스키마 변경 시 이 파일을 갱신한다.

export interface components {
  schemas: {
    AnnouncementBase: {
      bid_notice_no: string
      bid_notice_nm: string
      ntce_instt_nm?: string | null
      dminstt_nm?: string | null
      presmpt_price?: number | null
      bid_begin_dt?: string | null
      bid_close_dt?: string | null
      link_url?: string | null
    }
    AnnouncementResponse: components['schemas']['AnnouncementBase'] & {
      id: number
      raw_data?: Record<string, unknown> | null
      contract_method?: string | null
      openg_dt?: string | null
      category?: string | null
      relevance_score: number
      summary?: string | null
      requirements?: string | null
      needs_research_lab: boolean
      analysis_detail?: Record<string, unknown> | null
      status: string
      notion_page_id?: string | null
      collected_at?: string | null
      analyzed_at?: string | null
      created_at: string
      updated_at: string
    }
    AnnouncementListItem: {
      id: number
      bid_notice_no: string
      bid_notice_nm: string
      ntce_instt_nm?: string | null
      dminstt_nm?: string | null
      presmpt_price?: number | null
      bid_begin_dt?: string | null
      bid_close_dt?: string | null
      contract_method?: string | null
      openg_dt?: string | null
      category?: string | null
      relevance_score: number
      summary?: string | null
      status: string
      needs_research_lab: boolean
      collected_at?: string | null
      created_at: string
    }
    PaginatedAnnouncements: {
      items: components['schemas']['AnnouncementListItem'][]
      total: number
      page: number
      size: number
      pages: number
    }
    StatsResponse: {
      total_count: number
      by_category: Record<string, number>
      by_score_range: Record<string, number>
      by_status: Record<string, number>
      avg_score: number
      total_budget: number
      trend: components['schemas']['MonthlyTrendItem'][]
    }
    MonthlyTrendItem: {
      month: string
      count: number
      avg_score: number
      total_budget: number
    }
  }
}
