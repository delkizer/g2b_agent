<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useAnnouncementStats } from '@/composables/useAnnouncementStats'
import { getAnnouncements } from '@/api/announcements'
import { createDefaultFilterParams } from '@/api/types'
import type { AnnouncementListItem } from '@/types'
import TrendLineChart from '@/components/report/TrendLineChart.vue'
import ExportButton from '@/components/report/ExportButton.vue'
import CategoryTag from '@/components/common/CategoryTag.vue'
import ScoreBadge from '@/components/common/ScoreBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const dateFrom = ref('')
const dateTo = ref('')
const activePreset = ref('all')
const { stats, loading: statsLoading, error: statsError, fetchStats } = useAnnouncementStats()
const topItems = ref<AnnouncementListItem[]>([])
const topLoading = ref(false)

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function selectPreset(preset: string) {
  activePreset.value = preset
  switch (preset) {
    case 'week':
      dateFrom.value = daysAgo(7)
      dateTo.value = today()
      break
    case 'month':
      dateFrom.value = daysAgo(30)
      dateTo.value = today()
      break
    case 'quarter':
      dateFrom.value = daysAgo(90)
      dateTo.value = today()
      break
    case 'all':
      dateFrom.value = ''
      dateTo.value = ''
      break
  }
}

const presets = [
  { value: 'week', label: '최근 1주' },
  { value: 'month', label: '최근 1개월' },
  { value: 'quarter', label: '최근 3개월' },
  { value: 'all', label: '전체' },
]

async function loadData() {
  const params = createDefaultFilterParams()
  params.sort = 'relevance_score'
  params.order = 'desc'
  params.size = 10
  if (dateFrom.value) params.dateFrom = dateFrom.value
  if (dateTo.value) params.dateTo = dateTo.value

  topLoading.value = true
  await Promise.all([
    fetchStats(dateFrom.value || undefined, dateTo.value || undefined),
    getAnnouncements(params)
      .then((result) => { topItems.value = result.items })
      .catch(() => { topItems.value = [] })
      .finally(() => { topLoading.value = false }),
  ])
}

onMounted(() => loadData())
watch([dateFrom, dateTo], () => loadData())

// 카테고리 테이블 헬퍼
function categoryTotal(byCategory: Record<string, number>): number {
  return Object.values(byCategory).reduce((sum, v) => sum + v, 0)
}

function categoryRows(byCategory: Record<string, number>) {
  const total = categoryTotal(byCategory)
  return Object.entries(byCategory)
    .sort(([, a], [, b]) => b - a)
    .map(([category, count]) => ({
      category,
      count,
      percent: total > 0 ? ((count / total) * 100).toFixed(1) : '0.0',
    }))
}

function formatPrice(price: number | null | undefined): string {
  if (!price) return '-'
  return new Intl.NumberFormat('ko-KR').format(price) + '원'
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">리포트</h1>
      <ExportButton :date-from="dateFrom" :date-to="dateTo" />
    </div>

    <!-- 기간 선택기 -->
    <div class="flex flex-wrap items-center gap-3">
      <button
        v-for="p in presets"
        :key="p.value"
        :class="[
          'rounded-md px-3 py-1.5 text-sm font-medium transition',
          activePreset === p.value
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
        ]"
        @click="selectPreset(p.value)"
      >
        {{ p.label }}
      </button>
    </div>

    <ErrorAlert v-if="statsError" :message="statsError" />
    <LoadingSpinner v-else-if="statsLoading" />

    <template v-else-if="stats">
      <TrendLineChart :trend="stats.trend" />

      <!-- 카테고리별 현황 테이블 -->
      <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-gray-900">카테고리별 현황</h3>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200 text-left text-gray-500">
              <th class="py-2">카테고리</th>
              <th class="py-2 text-right">건수</th>
              <th class="py-2 text-right">비율</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in categoryRows(stats.by_category)" :key="row.category" class="border-b border-gray-100">
              <td class="py-2"><CategoryTag :category="row.category" /></td>
              <td class="py-2 text-right font-medium">{{ row.count }}</td>
              <td class="py-2 text-right text-gray-500">{{ row.percent }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Top 10 공고 -->
    <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h3 class="mb-4 text-lg font-semibold text-gray-900">Top 10 공고</h3>
      <LoadingSpinner v-if="topLoading" />
      <EmptyState v-else-if="topItems.length === 0" message="해당 기간 공고가 없습니다" />
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200 text-left text-gray-500">
              <th class="py-2">#</th>
              <th class="py-2">공고명</th>
              <th class="py-2">기관</th>
              <th class="py-2">카테고리</th>
              <th class="py-2 text-right">점수</th>
              <th class="py-2 text-right">예산</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, idx) in topItems"
              :key="item.id"
              class="cursor-pointer border-b border-gray-100 hover:bg-gray-50"
              @click="$router.push(`/announcements/${item.id}`)"
            >
              <td class="py-2 text-gray-400">{{ idx + 1 }}</td>
              <td class="py-2 font-medium text-gray-900 max-w-xs truncate">
                {{ item.bid_notice_nm }}
              </td>
              <td class="py-2 text-gray-600">{{ item.ntce_instt_nm ?? '-' }}</td>
              <td class="py-2">
                <CategoryTag v-if="item.category" :category="item.category" />
              </td>
              <td class="py-2 text-right">
                <ScoreBadge :score="item.relevance_score" />
              </td>
              <td class="py-2 text-right text-gray-600">{{ formatPrice(item.presmpt_price) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
