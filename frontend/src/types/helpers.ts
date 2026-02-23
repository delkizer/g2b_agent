import type { components } from './api'

// API 응답 타입 별칭
export type Announcement = components['schemas']['AnnouncementResponse']
export type AnnouncementListItem = components['schemas']['AnnouncementListItem']
export type PaginatedAnnouncements = components['schemas']['PaginatedAnnouncements']
export type StatsData = components['schemas']['StatsResponse']
export type MonthlyTrendItem = components['schemas']['MonthlyTrendItem']

// 프론트엔드 전용 파생 타입
export type AnnouncementStatus = 'pending' | 'analyzed' | 'reviewing' | 'bidding' | 'excluded' | 'archived'
export type AnnouncementCategory = '스포츠' | '영상분석' | 'AI/데이터' | '미디어' | '플랫폼' | '기타'
