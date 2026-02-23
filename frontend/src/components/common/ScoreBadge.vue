<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  score: number
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const colorClass = computed(() => {
  if (props.score >= 80) return 'bg-red-100 text-red-800'
  if (props.score >= 60) return 'bg-yellow-100 text-yellow-800'
  if (props.score >= 40) return 'bg-green-100 text-green-800'
  return 'bg-gray-100 text-gray-800'
})

const sizeClass = computed(() => {
  switch (props.size) {
    case 'sm': return 'px-1.5 py-0.5 text-xs'
    case 'lg': return 'px-4 py-2 text-lg'
    default:   return 'px-2 py-1 text-sm'
  }
})
</script>

<template>
  <span :class="['inline-flex items-center rounded-full font-semibold', colorClass, sizeClass]">
    {{ score }}
  </span>
</template>
