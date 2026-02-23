<script setup lang="ts">
interface Props {
  title: string
  value: number | string
  unit?: string
  icon?: string
  variant?: 'default' | 'danger' | 'info' | 'success'
}

withDefaults(defineProps<Props>(), {
  unit: '',
  icon: 'document',
  variant: 'default',
})

const variantClasses: Record<string, string> = {
  default: 'bg-white border-gray-200',
  danger: 'bg-red-50 border-red-200',
  info: 'bg-blue-50 border-blue-200',
  success: 'bg-green-50 border-green-200',
}
</script>

<template>
  <div :class="['rounded-lg border p-4 shadow-sm', variantClasses[variant]]">
    <p class="text-sm font-medium text-gray-500">{{ title }}</p>
    <p class="mt-1 text-3xl font-semibold text-gray-900">
      {{ value }}<span v-if="unit" class="ml-1 text-sm text-gray-500">{{ unit }}</span>
    </p>
  </div>
</template>
