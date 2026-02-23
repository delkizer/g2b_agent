<script setup lang="ts">
defineProps<{
  message: string
}>()
</script>

<template>
  <div class="rounded-md border border-red-200 bg-red-50 p-4">
    <p class="text-sm text-red-800">{{ message }}</p>
  </div>
</template>
