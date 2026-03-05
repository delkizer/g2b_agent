/**
 * Agent API 클라이언트 (로컬 전용)
 *
 * Vite proxy: /api/agent/* → localhost:8100/api/internal/*
 * DEV 환경에서만 사용.
 */
import axios from 'axios'

const agentClient = axios.create({
  baseURL: '/api/agent',
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

export interface SyncEc2Response {
  status: string
  synced: number
  failed: number
  errors: Array<{ bid_notice_no: string; error: string }>
  message?: string
}

export async function syncToEc2(limit = 500): Promise<SyncEc2Response> {
  const { data } = await agentClient.post<SyncEc2Response>(
    '/pipeline/sync-ec2',
    { limit },
  )
  return data
}
