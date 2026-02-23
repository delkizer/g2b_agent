<script setup lang="ts">
import { useAnnouncements } from '@/composables/useAnnouncements'
import FilterPanel from '@/components/announcement/FilterPanel.vue'
import SortSelect from '@/components/announcement/SortSelect.vue'
import AnnouncementCard from '@/components/announcement/AnnouncementCard.vue'
import Pagination from '@/components/common/Pagination.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const {
  items,
  total,
  pages,
  loading,
  error,
  filters,
  setFilter,
  setPage,
  setSort,
  resetFilters,
} = useAnnouncements()

function handleFilterUpdate(updated: typeof filters) {
  Object.assign(filters, updated)
  filters.page = 1
}

function handleSortChange(sort: string, order: string) {
  setSort(sort as any, order as 'asc' | 'desc')
}

function handlePageChange(page: number) {
  setPage(page)
}
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">공고 목록</h1>

    <FilterPanel
      :filters="filters"
      @update:filters="handleFilterUpdate"
      @reset="resetFilters"
    />

    <div class="flex items-center justify-between">
      <p class="text-sm text-gray-500">
        총 <span class="font-semibold">{{ total }}</span>건
      </p>
      <SortSelect
        :sort="filters.sort"
        :order="filters.order"
        @change="handleSortChange"
      />
    </div>

    <ErrorAlert v-if="error" :message="error" />
    <LoadingSpinner v-else-if="loading" />
    <EmptyState v-else-if="items.length === 0" message="조건에 맞는 공고가 없습니다" />

    <div v-else class="space-y-4">
      <AnnouncementCard
        v-for="item in items"
        :key="item.id"
        :announcement="item"
      />
    </div>

    <Pagination
      v-if="pages > 1"
      :total="total"
      :page="filters.page"
      :size="filters.size"
      @page-change="handlePageChange"
    />
  </div>
</template>
