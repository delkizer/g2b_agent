<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from '@/layouts/AppSidebar.vue'
import AppTopNav from '@/layouts/AppTopNav.vue'

const sidebarOpen = ref(false)
</script>

<template>
  <div class="flex h-screen bg-gray-50">
    <!-- 모바일 오버레이 -->
    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-20 bg-black bg-opacity-50 lg:hidden"
      @click="sidebarOpen = false"
    />

    <!-- 사이드바 -->
    <AppSidebar
      :class="[
        'fixed inset-y-0 left-0 z-30 w-64 transform transition-transform lg:static lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full',
      ]"
      @close="sidebarOpen = false"
    />

    <!-- 메인 영역 -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <AppTopNav @toggle-sidebar="sidebarOpen = !sidebarOpen" />
      <main class="flex-1 overflow-y-auto p-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
