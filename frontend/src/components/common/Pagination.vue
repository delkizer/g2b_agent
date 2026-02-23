<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  total: number
  page: number
  size: number
}>()

const emit = defineEmits<{
  'page-change': [page: number]
}>()

const totalPages = computed(() => Math.ceil(props.total / props.size))

const visiblePages = computed(() => {
  const pages: number[] = []
  const start = Math.max(1, props.page - 2)
  const end = Math.min(totalPages.value, props.page + 2)
  for (let i = start; i <= end; i++) {
    pages.push(i)
  }
  return pages
})

function goToPage(p: number) {
  if (p >= 1 && p <= totalPages.value && p !== props.page) {
    emit('page-change', p)
  }
}
</script>

<template>
  <nav class="flex items-center justify-center gap-1">
    <button
      :disabled="page <= 1"
      class="rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100
             disabled:opacity-50 disabled:cursor-not-allowed"
      @click="goToPage(page - 1)"
    >
      이전
    </button>

    <button
      v-for="p in visiblePages"
      :key="p"
      :class="[
        'rounded-md px-3 py-1.5 text-sm font-medium',
        p === page
          ? 'bg-blue-600 text-white'
          : 'text-gray-600 hover:bg-gray-100',
      ]"
      @click="goToPage(p)"
    >
      {{ p }}
    </button>

    <button
      :disabled="page >= totalPages"
      class="rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100
             disabled:opacity-50 disabled:cursor-not-allowed"
      @click="goToPage(page + 1)"
    >
      다음
    </button>
  </nav>
</template>
