import apiClient from './client'
import type { components } from '@/types/api'
import type { FilterParams, ExportParams } from './types'

type PaginatedAnnouncements = components['schemas']['PaginatedAnnouncements']
type AnnouncementDetailResponse = components['schemas']['AnnouncementResponse']
type AnnouncementStatsResponse = components['schemas']['StatsResponse']
type StatusUpdateResponse = {
  id: number
  bid_notice_no: string
  status: string
  updated_at: string
}

/**
 * 공고 목록 조회 (필터 + 페이징 + 정렬)
 */
export async function getAnnouncements(params: FilterParams) {
  const query: Record<string, string | number | undefined> = {
    category: params.category.length > 0 ? params.category.join(',') : undefined,
    min_score: params.minScore > 0 ? params.minScore : undefined,
    status: params.status || undefined,
    date_from: params.dateFrom || undefined,
    date_to: params.dateTo || undefined,
    search: params.search || undefined,
    sort: params.sort,
    order: params.order,
    page: params.page,
    size: params.size,
  }

  const { data } = await apiClient.get<PaginatedAnnouncements>('/announcements', {
    params: query,
  })
  return data
}

/**
 * 공고 상세 조회
 */
export async function getAnnouncementDetail(id: number) {
  const { data } = await apiClient.get<AnnouncementDetailResponse>(
    `/announcements/${id}`,
  )
  return data
}

/**
 * 공고 통계 조회
 */
export async function getAnnouncementStats(params?: {
  dateFrom?: string
  dateTo?: string
}) {
  const query: Record<string, string | undefined> = {
    date_from: params?.dateFrom || undefined,
    date_to: params?.dateTo || undefined,
  }

  const { data } = await apiClient.get<AnnouncementStatsResponse>(
    '/announcements/stats',
    { params: query },
  )
  return data
}

/**
 * 공고 상태 변경
 */
export async function updateAnnouncementStatus(
  id: number,
  status: string,
) {
  const { data } = await apiClient.patch<StatusUpdateResponse>(
    `/announcements/${id}/status`,
    { status },
  )
  return data
}

/**
 * 공고 내보내기 (CSV/Excel)
 */
export async function exportAnnouncements(params: ExportParams) {
  const query: Record<string, string | number | undefined> = {
    format: params.format,
    category: params.category?.length ? params.category.join(',') : undefined,
    min_score: params.minScore && params.minScore > 0 ? params.minScore : undefined,
    status: params.status || undefined,
    date_from: params.dateFrom || undefined,
    date_to: params.dateTo || undefined,
    search: params.search || undefined,
    sort: params.sort || 'created_at',
    order: params.order || 'desc',
  }

  const response = await apiClient.get('/announcements/export', {
    params: query,
    responseType: 'blob',
  })

  const contentDisposition = response.headers['content-disposition'] || ''
  const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/)
  const filename = filenameMatch
    ? filenameMatch[1]
    : `announcements.${params.format}`

  return {
    blob: response.data as Blob,
    filename,
  }
}
