<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAnnouncementStats } from '@/composables/useAnnouncementStats'
import { getAnnouncements } from '@/api/announcements'
import { createDefaultFilterParams } from '@/api/types'
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
    <h1 class="text-2xl font-bold text-gray-900">대시보드</h1>

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
