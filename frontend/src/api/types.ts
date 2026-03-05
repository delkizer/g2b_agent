import type { AnnouncementStatus, AnnouncementCategory } from '@/types'

/**
 * 정렬 가능 필드
 */
export type SortField =
  | 'bid_begin_dt'
  | 'relevance_score'
  | 'bid_close_dt'
  | 'collected_at'
  | 'presmpt_price'
  | 'created_at'

/**
 * 공고 목록 조회 필터 파라미터
 */
export type DeadlineFilter = '' | 'active' | 'closed'

export interface FilterParams {
  category: AnnouncementCategory[]
  minScore: number
  status: AnnouncementStatus | ''
  deadline: DeadlineFilter
  dateFrom: string
  dateTo: string
  search: string
  sort: SortField
  order: 'asc' | 'desc'
  page: number
  size: number
}

/**
 * 내보내기 파라미터
 */
export interface ExportParams {
  format: 'csv' | 'xlsx'
  category?: AnnouncementCategory[]
  minScore?: number
  status?: AnnouncementStatus | ''
  dateFrom?: string
  dateTo?: string
  search?: string
  sort?: SortField
  order?: 'asc' | 'desc'
}

/**
 * FilterParams 기본값 생성 팩토리
 */
export function createDefaultFilterParams(): FilterParams {
  return {
    category: [],
    minScore: 0,
    status: '',
    deadline: 'active',
    dateFrom: '',
    dateTo: '',
    search: '',
    sort: 'bid_begin_dt',
    order: 'desc',
    page: 1,
    size: 20,
  }
}
