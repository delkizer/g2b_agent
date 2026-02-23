<script setup lang="ts">
const emit = defineEmits<{ 'toggle-sidebar': [] }>()
</script>

<template>
  <header class="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 shadow-sm">
    <button
      class="rounded-md p-2 text-gray-500 hover:bg-gray-100 lg:hidden"
      aria-label="메뉴 열기"
      @click="emit('toggle-sidebar')"
    >
      <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>
    <h2 class="text-lg font-semibold text-gray-700">나라장터 마켓 인텔리전스</h2>
    <div />
  </header>
</template>
