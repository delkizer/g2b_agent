import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { jwtDecode } from 'jwt-decode'
import apiClient from '@/api/client'

interface User {
  id: number
  username: string
  display_name: string | null
}

interface JwtPayload {
  user_id: number
  username: string
  exp: number
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isRefreshing = ref(false)
  const refreshTried = ref(false)

  const isLoggedIn = computed(() => user.value !== null)

  function hydrate() {
    const token = localStorage.getItem('access_token')
    if (!token) return

    try {
      const decoded = jwtDecode<JwtPayload>(token)
      const now = Date.now() / 1000
      if (decoded.exp < now) {
        localStorage.removeItem('access_token')
        return
      }
      user.value = {
        id: decoded.user_id,
        username: decoded.username,
        display_name: null,
      }
    } catch {
      localStorage.removeItem('access_token')
    }
  }

  function setToken(accessToken: string) {
    localStorage.setItem('access_token', accessToken)
    try {
      const decoded = jwtDecode<JwtPayload>(accessToken)
      user.value = {
        id: decoded.user_id,
        username: decoded.username,
        display_name: null,
      }
    } catch {
      // decode 실패 시 fetchCurrentUser로 복구
    }
  }

  async function fetchCurrentUser(): Promise<boolean> {
    try {
      const res = await apiClient.get('/auth/me')
      user.value = res.data
      return true
    } catch {
      user.value = null
      return false
    }
  }

  async function refreshTokens(): Promise<boolean> {
    if (isRefreshing.value) return false
    isRefreshing.value = true
    try {
      const res = await apiClient.post('/auth/refresh')
      const { access_token } = res.data
      setToken(access_token)
      await fetchCurrentUser()
      refreshTried.value = false
      return true
    } catch {
      user.value = null
      localStorage.removeItem('access_token')
      return false
    } finally {
      isRefreshing.value = false
    }
  }

  async function logout() {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // 서버 실패해도 클라이언트 상태 초기화
    }
    user.value = null
    localStorage.removeItem('access_token')
  }

  return {
    user,
    isRefreshing,
    refreshTried,
    isLoggedIn,
    hydrate,
    setToken,
    fetchCurrentUser,
    refreshTokens,
    logout,
  }
})
