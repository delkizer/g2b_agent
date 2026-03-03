<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { AnnouncementListItem } from '@/types'
import ScoreBadge from '@/components/common/ScoreBadge.vue'
import CategoryTag from '@/components/common/CategoryTag.vue'

const props = defineProps<{
  announcement: AnnouncementListItem
}>()

const router = useRouter()

const formattedPrice = computed(() => {
  if (!props.announcement.presmpt_price) return '-'
  return new Intl.NumberFormat('ko-KR').format(props.announcement.presmpt_price) + '원'
})

const formattedBidPeriod = computed(() => {
  const begin = props.announcement.bid_begin_dt
  const close = props.announcement.bid_close_dt
  if (!begin && !close) return '-'

  const fmt = (dt: string) => {
    const d = new Date(dt)
    return `${d.getMonth() + 1}/${d.getDate()}`
  }

  if (begin && close) return `${fmt(begin)} ~ ${fmt(close)}`
  if (!begin && close) return `~ ${fmt(close)}`
  return `${fmt(begin!)} ~`
})

const dDayText = computed(() => {
  if (!props.announcement.bid_close_dt) return ''
  const now = new Date()
  const close = new Date(props.announcement.bid_close_dt)
  const diffMs = close.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return '마감'
  if (diffDays === 0) return 'D-Day'
  return `D-${diffDays}`
})

const dDayColor = computed(() => {
  if (!props.announcement.bid_close_dt) return ''
  const now = new Date()
  const close = new Date(props.announcement.bid_close_dt)
  const diffMs = close.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 'text-gray-400'
  if (diffDays <= 3) return 'text-red-600 font-semibold'
  if (diffDays <= 7) return 'text-orange-500 font-medium'
  return 'text-blue-600'
})

function goToDetail() {
  router.push(`/announcements/${props.announcement.id}`)
}
</script>

<template>
  <div
    class="cursor-pointer rounded-lg border border-gray-200 bg-white p-4 shadow-sm
           transition hover:border-blue-300 hover:shadow-md"
    @click="goToDetail"
  >
    <div class="flex items-start justify-between">
      <div class="flex-1 min-w-0">
        <h3 class="truncate text-base font-semibold text-gray-900">
          {{ announcement.bid_notice_nm }}
        </h3>
        <p class="mt-1 text-sm text-gray-500">
          {{ announcement.ntce_instt_nm ?? '' }}
          <span v-if="announcement.dminstt_nm"> / {{ announcement.dminstt_nm }}</span>
        </p>
      </div>
      <ScoreBadge :score="announcement.relevance_score" class="ml-3 flex-shrink-0" />
    </div>

    <p v-if="announcement.summary" class="mt-2 line-clamp-2 text-sm text-gray-600">
      {{ announcement.summary }}
    </p>

    <div class="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-500">
      <CategoryTag v-if="announcement.category" :category="announcement.category" />
      <span>입찰: {{ formattedBidPeriod }}</span>
      <span v-if="dDayText" :class="dDayColor">{{ dDayText }}</span>
      <span>예산: {{ formattedPrice }}</span>
    </div>
  </div>
</template>
