<script setup lang="ts">
import { computed } from 'vue'
import { Pie } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps<{
  data: Record<string, number>
}>()

const categoryColors: Record<string, string> = {
  '스포츠': '#3B82F6',
  '영상분석': '#8B5CF6',
  'AI/데이터': '#EC4899',
  '미디어': '#F97316',
  '플랫폼': '#14B8A6',
  '기타': '#6B7280',
}

const chartData = computed(() => ({
  labels: Object.keys(props.data),
  datasets: [
    {
      data: Object.values(props.data),
      backgroundColor: Object.keys(props.data).map((k) => categoryColors[k] ?? '#D1D5DB'),
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const },
  },
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-gray-900">카테고리 분포</h3>
    <div class="h-64">
      <Pie :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
