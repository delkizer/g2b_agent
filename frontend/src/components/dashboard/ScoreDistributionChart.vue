<script setup lang="ts">
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps<{
  data: Record<string, number>
}>()

const scoreRangeColors: Record<string, string> = {
  '80-100': '#EF4444',
  '60-79': '#F59E0B',
  '40-59': '#10B981',
  '0-39': '#9CA3AF',
}

const scoreRangeLabels: Record<string, string> = {
  '80-100': '즉시검토 (80-100)',
  '60-79': '검토필요 (60-79)',
  '40-59': '부분관련 (40-59)',
  '0-39': '관련도낮음 (0-39)',
}

const chartData = computed(() => ({
  labels: Object.keys(props.data).map((k) => scoreRangeLabels[k] ?? k),
  datasets: [
    {
      data: Object.values(props.data),
      backgroundColor: Object.keys(props.data).map((k) => scoreRangeColors[k] ?? '#D1D5DB'),
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
    <h3 class="mb-4 text-lg font-semibold text-gray-900">점수 분포</h3>
    <div class="h-64">
      <Doughnut :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
