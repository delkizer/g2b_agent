<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const emit = defineEmits<{ close: [] }>()

const menuItems = [
  { path: '/', label: '대시보드', icon: 'home' },
  { path: '/announcements', label: '공고 목록', icon: 'list' },
  { path: '/report', label: '리포트', icon: 'chart-bar' },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<template>
  <aside class="flex flex-col bg-gray-900 text-white">
    <div class="flex h-16 items-center justify-between px-4">
      <span class="text-lg font-bold">G2B Intelligence</span>
      <button class="lg:hidden text-gray-400 hover:text-white" @click="emit('close')">
        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <nav class="flex-1 px-3 py-4 space-y-1">
      <RouterLink
        v-for="item in menuItems"
        :key="item.path"
        :to="item.path"
        :class="[
          'flex items-center rounded-md px-3 py-2 text-sm font-medium transition',
          isActive(item.path)
            ? 'bg-gray-800 text-white'
            : 'text-gray-300 hover:bg-gray-800 hover:text-white',
        ]"
        @click="emit('close')"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
  </aside>
</template>
