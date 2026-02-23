import { ref, reactive, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getAnnouncements } from '@/api/announcements'
import { createDefaultFilterParams, type FilterParams, type SortField } from '@/api/types'
import type { AnnouncementListItem } from '@/types'

export function useAnnouncements() {
  const router = useRouter()
  const route = useRoute()

  const items = ref<AnnouncementListItem[]>([])
  const total = ref(0)
  const pages = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const filters = reactive<FilterParams>(createDefaultFilterParams())

  function syncFromQuery() {
    const q = route.query

    if (q.category && typeof q.category === 'string') {
      filters.category = q.category.split(',').filter(Boolean) as FilterParams['category']
    }
    if (q.min_score) filters.minScore = Number(q.min_score)
    if (q.status && typeof q.status === 'string') {
      filters.status = q.status as FilterParams['status']
    }
    if (q.date_from && typeof q.date_from === 'string') filters.dateFrom = q.date_from
    if (q.date_to && typeof q.date_to === 'string') filters.dateTo = q.date_to
    if (q.search && typeof q.search === 'string') filters.search = q.search
    if (q.sort && typeof q.sort === 'string') filters.sort = q.sort as SortField
    if (q.order && typeof q.order === 'string') {
      filters.order = q.order as 'asc' | 'desc'
    }
    if (q.page) filters.page = Number(q.page)
    if (q.size) filters.size = Number(q.size)
  }

  function syncToQuery() {
    const query: Record<string, string> = {}

    if (filters.category.length > 0) query.category = filters.category.join(',')
    if (filters.minScore > 0) query.min_score = String(filters.minScore)
    if (filters.status) query.status = filters.status
    if (filters.dateFrom) query.date_from = filters.dateFrom
    if (filters.dateTo) query.date_to = filters.dateTo
    if (filters.search) query.search = filters.search
    if (filters.sort !== 'created_at') query.sort = filters.sort
    if (filters.order !== 'desc') query.order = filters.order
    if (filters.page > 1) query.page = String(filters.page)
    if (filters.size !== 20) query.size = String(filters.size)

    router.replace({ query })
  }

  async function fetchList() {
    loading.value = true
    error.value = null

    try {
      const result = await getAnnouncements(filters)
      items.value = result.items
      total.value = result.total
      pages.value = result.pages
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '목록을 불러올 수 없습니다.'
      items.value = []
      total.value = 0
      pages.value = 0
    } finally {
      loading.value = false
    }
  }

  function setFilter<K extends keyof FilterParams>(key: K, value: FilterParams[K]) {
    ;(filters as FilterParams)[key] = value
    filters.page = 1
  }

  function setPage(page: number) {
    filters.page = page
  }

  function setSort(field: SortField, order: 'asc' | 'desc' = 'desc') {
    filters.sort = field
    filters.order = order
    filters.page = 1
  }

  function resetFilters() {
    const defaults = createDefaultFilterParams()
    Object.assign(filters, defaults)
  }

  watch(
    () => ({ ...filters }),
    () => {
      syncToQuery()
      fetchList()
    },
    { deep: true },
  )

  onMounted(() => {
    syncFromQuery()
    fetchList()
  })

  return {
    items,
    total,
    pages,
    loading,
    error,
    filters,
    fetchList,
    setFilter,
    setPage,
    setSort,
    resetFilters,
  }
}
