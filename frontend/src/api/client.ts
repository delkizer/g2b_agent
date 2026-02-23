import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useToast } from '@/utils/toast'

interface ApiErrorResponse {
  detail: string
  error_code?: string
}

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 요청 인터셉터
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.params || '')
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error),
)

// 응답 인터셉터
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    const { toast } = useToast()
    const status = error.response?.status
    const errorData = error.response?.data

    if (!error.response) {
      if (error.code === 'ECONNABORTED') {
        toast.error('요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.')
      } else {
        toast.error('네트워크 연결을 확인해주세요.')
      }
      return Promise.reject(error)
    }

    switch (status) {
      case 400:
        toast.warning(errorData?.detail || '잘못된 요청입니다.')
        break
      case 401:
        toast.error('인증에 실패했습니다.')
        break
      case 403:
        toast.error('접근 권한이 없습니다.')
        break
      case 404:
        toast.warning(errorData?.detail || '요청한 데이터를 찾을 수 없습니다.')
        break
      case 422:
        toast.warning('요청 데이터 형식이 올바르지 않습니다.')
        break
      case 429:
        toast.warning('요청이 너무 많습니다. 잠시 후 다시 시도해주세요.')
        break
      case 500:
        toast.error('서버 내부 오류가 발생했습니다.')
        break
      case 503:
        toast.error('서비스를 일시적으로 사용할 수 없습니다.')
        break
      default:
        toast.error(errorData?.detail || '알 수 없는 오류가 발생했습니다.')
    }

    return Promise.reject(error)
  },
)

export default apiClient
