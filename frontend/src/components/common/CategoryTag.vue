<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  category: string
}>()

const colorMap: Record<string, string> = {
  '스포츠': 'bg-blue-100 text-blue-800',
  '영상분석': 'bg-violet-100 text-violet-800',
  'AI/데이터': 'bg-pink-100 text-pink-800',
  '미디어': 'bg-orange-100 text-orange-800',
  '플랫폼': 'bg-teal-100 text-teal-800',
  '기타': 'bg-gray-100 text-gray-800',
}

const colorClass = computed(() => colorMap[props.category] ?? 'bg-gray-100 text-gray-800')
</script>

<template>
  <span :class="['inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', colorClass]">
    {{ category }}
  </span>
</template>
