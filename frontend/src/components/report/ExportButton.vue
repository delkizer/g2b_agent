<script setup lang="ts">
import { ref } from 'vue'
import { useExport } from '@/composables/useExport'

const props = defineProps<{
  dateFrom?: string
  dateTo?: string
}>()

const { exporting, exportCsv, exportExcel } = useExport()
const showDropdown = ref(false)

function handleExport(format: 'csv' | 'xlsx') {
  showDropdown.value = false
  const overrides = {
    dateFrom: props.dateFrom || undefined,
    dateTo: props.dateTo || undefined,
  }
  if (format === 'csv') {
    exportCsv(overrides)
  } else {
    exportExcel(overrides)
  }
}
</script>

<template>
  <div class="relative">
    <button
      :disabled="exporting"
      class="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white
             hover:bg-green-700 disabled:opacity-50 transition"
      @click="showDropdown = !showDropdown"
    >
      {{ exporting ? '내보내는 중...' : '내보내기' }}
    </button>
    <div
      v-if="showDropdown"
      class="absolute right-0 mt-1 w-32 rounded-md border border-gray-200
             bg-white shadow-lg z-10"
    >
      <button
        class="block w-full px-4 py-2 text-left text-sm hover:bg-gray-100"
        @click="handleExport('csv')"
      >
        CSV
      </button>
      <button
        class="block w-full px-4 py-2 text-left text-sm hover:bg-gray-100"
        @click="handleExport('xlsx')"
      >
        Excel
      </button>
    </div>
  </div>
</template>
