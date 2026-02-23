<script setup lang="ts">
import { useToast } from '@/utils/toast'
import ToastContainer from '@/components/common/ToastContainer.vue'

const { toasts, removeToast } = useToast()
</script>

<template>
  <RouterView />
  <ToastContainer :toasts="toasts" @dismiss="removeToast" />
</template>
