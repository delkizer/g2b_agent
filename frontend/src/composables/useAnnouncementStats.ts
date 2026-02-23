import { ref } from 'vue'
import { getAnnouncementStats } from '@/api/announcements'
import type { StatsData } from '@/types'

// 모듈 수준 캐시 (5분)
let cachedStats: StatsData | null = null
let cacheKey: string = ''
let cacheTimestamp: number = 0
const CACHE_TTL_MS = 5 * 60 * 1000

function getCacheKey(dateFrom?: string, dateTo?: string): string {
  return `${dateFrom || 'all'}_${dateTo || 'all'}`
}

export function useAnnouncementStats() {
  const stats = ref<StatsData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchStats(dateFrom?: string, dateTo?: string) {
    const key = getCacheKey(dateFrom, dateTo)
    const now = Date.now()

    if (cachedStats && cacheKey === key && (now - cacheTimestamp) < CACHE_TTL_MS) {
      stats.value = cachedStats
      return
    }

    loading.value = true
    error.value = null

    try {
      const result = await getAnnouncementStats({ dateFrom, dateTo })
      stats.value = result

      cachedStats = result
      cacheKey = key
      cacheTimestamp = now
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '통계를 불러올 수 없습니다.'
      stats.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    stats,
    loading,
    error,
    fetchStats,
  }
}
