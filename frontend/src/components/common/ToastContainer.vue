<script setup lang="ts">
import type { ToastMessage } from '@/utils/toast'

defineProps<{
  toasts: ToastMessage[]
}>()

const emit = defineEmits<{
  dismiss: [id: number]
}>()

function toastClasses(type: ToastMessage['type']): string {
  const base = 'rounded-md px-4 py-3 text-sm font-medium shadow-lg'
  switch (type) {
    case 'success': return `${base} bg-green-500 text-white`
    case 'warning': return `${base} bg-yellow-500 text-white`
    case 'error':   return `${base} bg-red-500 text-white`
    case 'info':    return `${base} bg-blue-500 text-white`
  }
}
</script>

<template>
  <div aria-live="polite" aria-atomic="true" class="fixed top-4 right-4 z-50 space-y-2">
    <TransitionGroup name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        :class="toastClasses(t.type)"
        role="alert"
        class="cursor-pointer"
        @click="emit('dismiss', t.id)"
      >
        {{ t.message }}
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
