<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome() {
  router.push('/')
}

function goBack() {
  router.back()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="text-center">
      <p class="text-6xl font-bold text-gray-300">404</p>
      <h1 class="mt-4 text-2xl font-semibold text-gray-900">
        페이지를 찾을 수 없습니다
      </h1>
      <p class="mt-2 text-gray-500">
        요청하신 페이지가 존재하지 않거나 이동되었습니다.
      </p>
      <div class="mt-6 flex justify-center gap-3">
        <button
          class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white
                 hover:bg-blue-700 transition"
          @click="goHome"
        >
          대시보드로 이동
        </button>
        <button
          class="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-600
                 hover:bg-gray-200 transition"
          @click="goBack"
        >
          이전 페이지
        </button>
      </div>
    </div>
  </div>
</template>
