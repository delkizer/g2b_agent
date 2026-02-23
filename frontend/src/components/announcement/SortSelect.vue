<script setup lang="ts">
defineProps<{
  sort: string
  order: string
}>()

const emit = defineEmits<{
  change: [sort: string, order: string]
}>()

const sortOptions = [
  { value: 'relevance_score:desc', label: '적합성 높은순' },
  { value: 'relevance_score:asc', label: '적합성 낮은순' },
  { value: 'bid_close_dt:asc', label: '마감일 임박순' },
  { value: 'bid_close_dt:desc', label: '마감일 늦은순' },
  { value: 'presmpt_price:desc', label: '예산 높은순' },
  { value: 'created_at:desc', label: '최신순' },
]

function handleChange(event: Event) {
  const val = (event.target as HTMLSelectElement).value
  const [s, o] = val.split(':')
  emit('change', s, o)
}
</script>

<template>
  <select
    :value="`${sort}:${order}`"
    class="rounded-md border-gray-300 text-sm"
    @change="handleChange"
  >
    <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
      {{ opt.label }}
    </option>
  </select>
</template>
