<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAnnouncementStats } from '@/composables/useAnnouncementStats'
import { getAnnouncements } from '@/api/announcements'
import { createDefaultFilterParams } from '@/api/types'
import { syncToEc2, type SyncEc2Response } from '@/api/agent'
import type { AnnouncementListItem } from '@/types'
import StatCard from '@/components/dashboard/StatCard.vue'
import ScoreDistributionChart from '@/components/dashboard/ScoreDistributionChart.vue'
import CategoryPieChart from '@/components/dashboard/CategoryPieChart.vue'
import RecentHighScoreList from '@/components/dashboard/RecentHighScoreList.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const { stats, loading: statsLoading, error: statsError, fetchStats } = useAnnouncementStats()
const highScoreItems = ref<AnnouncementListItem[]>([])
const listLoading = ref(false)

// EC2 동기화 (로컬 전용)
const isDev = import.meta.env.DEV
const syncing = ref(false)
const syncResult = ref<SyncEc2Response | null>(null)
const syncError = ref<string | null>(null)

async function handleSyncEc2() {
  syncing.value = true
  syncResult.value = null
  syncError.value = null
  try {
    syncResult.value = await syncToEc2()
  } catch (e: unknown) {
    syncError.value = e instanceof Error ? e.message : 'EC2 동기화 실패'
  } finally {
    syncing.value = false
  }
}

function formatBudget(budget: number): string {
  if (budget >= 100_000_000) {
    return `${(budget / 100_000_000).toFixed(0)}억`
  }
  if (budget >= 10_000) {
    return `${(budget / 10_000).toFixed(0)}만`
  }
  return String(budget)
}

onMounted(async () => {
  const params = createDefaultFilterParams()
  params.minScore = 80
  params.size = 5
  params.sort = 'created_at'
  params.order = 'desc'

  listLoading.value = true
  await Promise.all([
    fetchStats(),
    getAnnouncements(params)
      .then((result) => {
        highScoreItems.value = result.items
      })
      .catch(() => {
        highScoreItems.value = []
      })
      .finally(() => {
        listLoading.value = false
      }),
  ])
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">대시보드</h1>

      <!-- EC2 동기화 버튼 (로컬 전용) -->
      <div v-if="isDev" class="flex items-center gap-3">
        <span
          v-if="syncResult"
          class="text-sm"
          :class="syncResult.failed > 0 ? 'text-amber-600' : 'text-green-600'"
        >
          동기화 {{ syncResult.synced }}건 완료
          <template v-if="syncResult.failed > 0">, {{ syncResult.failed }}건 실패</template>
        </span>
        <span v-if="syncError" class="text-sm text-red-600">{{ syncError }}</span>
        <button
          :disabled="syncing"
          class="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="handleSyncEc2"
        >
          <svg
            v-if="syncing"
            class="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <template v-else>
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </template>
          {{ syncing ? '동기화 중...' : 'EC2 동기화' }}
        </button>
      </div>
    </div>

    <ErrorAlert v-if="statsError" :message="statsError" />
    <LoadingSpinner v-else-if="statsLoading" />

    <template v-else-if="stats">
      <!-- 요약 통계 카드 4개 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="총 공고수" :value="stats.total_count" unit="건" icon="document" />
        <StatCard
          title="고점수 공고"
          :value="stats.by_score_range['80-100'] ?? 0"
          unit="건"
          icon="fire"
          variant="danger"
        />
        <StatCard
          title="평균 적합성"
          :value="stats.avg_score.toFixed(1)"
          unit="점"
          icon="chart"
          variant="info"
        />
        <StatCard
          title="총 예산"
          :value="formatBudget(stats.total_budget)"
          unit="원"
          icon="currency"
          variant="success"
        />
      </div>

      <!-- 차트 영역 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ScoreDistributionChart :data="stats.by_score_range" />
        <CategoryPieChart :data="stats.by_category" />
      </div>

      <!-- 최근 고점수 공고 -->
      <RecentHighScoreList :items="highScoreItems" :loading="listLoading" />
    </template>
  </div>
</template>
