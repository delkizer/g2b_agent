import apiClient from './client'

export interface FileItem {
  filename: string
  size: number
  extension: string
  type_label: string
}

export interface FileListResponse {
  bid_notice_no: string
  files: FileItem[]
}

export interface BidContextResponse {
  bid_notice_no: string
  exists: boolean
  content: string | null
}

export async function getAttachments(bidNoticeNo: string): Promise<FileListResponse> {
  const { data } = await apiClient.get<FileListResponse>(
    `/files/${bidNoticeNo}/attachments`,
  )
  return data
}

export async function getOutputFiles(bidNoticeNo: string): Promise<FileListResponse> {
  const { data } = await apiClient.get<FileListResponse>(
    `/files/${bidNoticeNo}/outputs`,
  )
  return data
}

export async function getBidContext(bidNoticeNo: string): Promise<BidContextResponse> {
  const { data } = await apiClient.get<BidContextResponse>(
    `/files/${bidNoticeNo}/bid-context`,
  )
  return data
}

export function getAttachmentDownloadUrl(bidNoticeNo: string, filename: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${base}/files/${bidNoticeNo}/attachments/${encodeURIComponent(filename)}`
}

export function getOutputDownloadUrl(bidNoticeNo: string, filename: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${base}/files/${bidNoticeNo}/outputs/${encodeURIComponent(filename)}`
}
