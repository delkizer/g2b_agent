<script setup lang="ts">
import type { FilterParams } from '@/api/types'

const props = defineProps<{
  filters: FilterParams
}>()

const emit = defineEmits<{
  'update:filters': [filters: FilterParams]
  reset: []
}>()

const categories = ['스포츠', '영상분석', 'AI/데이터', '미디어', 'CCTV', '플랫폼', '기타']
const statuses = [
  { value: '', label: '전체' },
  { value: 'pending', label: '대기' },
  { value: 'analyzed', label: '분석완료' },
  { value: 'reviewing', label: '검토중' },
  { value: 'bidding', label: '입찰준비' },
  { value: 'excluded', label: '제외' },
  { value: 'archived', label: '종료' },
]

const deadlines = [
  { value: '', label: '전체' },
  { value: 'active', label: '진행중' },
  { value: 'closed', label: '마감' },
]

function updateFilter<K extends keyof FilterParams>(key: K, value: FilterParams[K]) {
  emit('update:filters', { ...props.filters, [key]: value })
}

function toggleCategory(cat: string) {
  const current = [...props.filters.category]
  const idx = current.indexOf(cat as any)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(cat as any)
  }
  updateFilter('category', current)
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      <!-- 카테고리 멀티셀렉트 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">카테고리</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="cat in categories"
            :key="cat"
            :class="[
              'rounded-full px-3 py-1 text-xs font-medium transition',
              filters.category.includes(cat as any)
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
            ]"
            @click="toggleCategory(cat)"
          >
            {{ cat }}
          </button>
        </div>
      </div>

      <!-- 최소 점수 슬라이더 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">
          최소 점수: {{ filters.minScore }}
        </label>
        <input
          type="range"
          min="0"
          max="100"
          step="10"
          :value="filters.minScore"
          class="w-full"
          @input="updateFilter('minScore', Number(($event.target as HTMLInputElement).value))"
        />
      </div>

      <!-- 상태 필터 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">상태</label>
        <select
          :value="filters.status"
          class="w-full rounded-md border-gray-300 text-sm"
          @change="updateFilter('status', ($event.target as HTMLSelectElement).value as any)"
        >
          <option v-for="s in statuses" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>

      <!-- 마감 여부 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">마감 여부</label>
        <select
          :value="filters.deadline"
          class="w-full rounded-md border-gray-300 text-sm"
          @change="updateFilter('deadline', ($event.target as HTMLSelectElement).value as any)"
        >
          <option v-for="d in deadlines" :key="d.value" :value="d.value">{{ d.label }}</option>
        </select>
      </div>

      <!-- 텍스트 검색 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">검색</label>
        <input
          type="text"
          :value="filters.search"
          placeholder="공고명, 요약 검색..."
          class="w-full rounded-md border-gray-300 text-sm"
          @input="updateFilter('search', ($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>

    <!-- 기간 필터 + 초기화 -->
    <div class="mt-4 flex items-end gap-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">기간 (시작)</label>
        <input
          type="date"
          :value="filters.dateFrom"
          class="rounded-md border-gray-300 text-sm"
          @change="updateFilter('dateFrom', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">기간 (종료)</label>
        <input
          type="date"
          :value="filters.dateTo"
          class="rounded-md border-gray-300 text-sm"
          @change="updateFilter('dateTo', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <button
        class="rounded-md bg-gray-100 px-4 py-2 text-sm text-gray-600 hover:bg-gray-200"
        @click="$emit('reset')"
      >
        초기화
      </button>
    </div>
  </div>
</template>
