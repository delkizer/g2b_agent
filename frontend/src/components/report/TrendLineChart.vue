<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

interface TrendItem {
  month: string
  count: number
  avg_score: number
  total_budget: number
}

const props = defineProps<{
  trend: TrendItem[]
}>()

const chartData = computed(() => ({
  labels: props.trend.map((t) => t.month),
  datasets: [
    {
      label: '수집 건수',
      data: props.trend.map((t) => t.count),
      borderColor: '#3B82F6',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      yAxisID: 'y',
      tension: 0.3,
    },
    {
      label: '평균 점수',
      data: props.trend.map((t) => t.avg_score),
      borderColor: '#F59E0B',
      backgroundColor: 'rgba(245, 158, 11, 0.1)',
      yAxisID: 'y1',
      tension: 0.3,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index' as const,
    intersect: false,
  },
  scales: {
    y: {
      type: 'linear' as const,
      position: 'left' as const,
      title: { display: true, text: '건수' },
      beginAtZero: true,
    },
    y1: {
      type: 'linear' as const,
      position: 'right' as const,
      title: { display: true, text: '평균 점수' },
      min: 0,
      max: 100,
      grid: { drawOnChartArea: false },
    },
  },
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-gray-900">수집 추이</h3>
    <div class="h-72">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
