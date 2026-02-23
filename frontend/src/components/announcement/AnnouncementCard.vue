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

const formattedCloseDate = computed(() => {
  if (!props.announcement.bid_close_dt) return '-'
  return new Date(props.announcement.bid_close_dt).toLocaleDateString('ko-KR')
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
      <span>마감: {{ formattedCloseDate }}</span>
      <span>예산: {{ formattedPrice }}</span>
    </div>
  </div>
</template>
