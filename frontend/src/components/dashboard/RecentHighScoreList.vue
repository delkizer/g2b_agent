<script setup lang="ts">
import type { AnnouncementListItem } from '@/types'
import AnnouncementCard from '@/components/announcement/AnnouncementCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

defineProps<{
  items: AnnouncementListItem[]
  loading?: boolean
}>()
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-gray-900">최근 고점수 공고</h3>
    <LoadingSpinner v-if="loading" />
    <EmptyState v-else-if="items.length === 0" message="고점수 공고가 없습니다" />
    <div v-else class="space-y-3">
      <AnnouncementCard v-for="item in items" :key="item.id" :announcement="item" />
    </div>
  </div>
</template>
