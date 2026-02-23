import { reactive } from 'vue'

export interface ToastMessage {
  id: number
  type: 'success' | 'warning' | 'error' | 'info'
  message: string
}

const state = reactive({
  toasts: [] as ToastMessage[],
  nextId: 1,
})

function addToast(
  type: ToastMessage['type'],
  message: string,
  duration: number = type === 'success' || type === 'info' ? 3000 : 5000,
) {
  const id = state.nextId++
  state.toasts.push({ id, type, message })
  setTimeout(() => removeToast(id), duration)
}

function removeToast(id: number) {
  const idx = state.toasts.findIndex((t) => t.id === id)
  if (idx >= 0) {
    state.toasts.splice(idx, 1)
  }
}

const toast = {
  success: (msg: string) => addToast('success', msg),
  warning: (msg: string) => addToast('warning', msg),
  error: (msg: string) => addToast('error', msg),
  info: (msg: string) => addToast('info', msg),
}

export function useToast() {
  return { toasts: state.toasts, toast, removeToast }
}
