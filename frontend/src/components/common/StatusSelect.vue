<script setup lang="ts">
defineProps<{
  status: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  change: [status: string]
}>()

const statusOptions = [
  { value: 'pending', label: '대기' },
  { value: 'analyzed', label: '분석완료' },
  { value: 'reviewing', label: '검토중' },
  { value: 'bidding', label: '입찰준비' },
  { value: 'excluded', label: '제외' },
  { value: 'archived', label: '종료' },
]

function handleChange(event: Event) {
  emit('change', (event.target as HTMLSelectElement).value)
}
</script>

<template>
  <select
    :value="status"
    :disabled="disabled"
    class="rounded-md border-gray-300 text-sm font-medium disabled:opacity-50"
    @change="handleChange"
  >
    <option
      v-for="opt in statusOptions"
      :key="opt.value"
      :value="opt.value"
    >
      {{ opt.label }}
    </option>
  </select>
</template>
