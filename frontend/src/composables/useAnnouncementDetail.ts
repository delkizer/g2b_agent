import { ref, onMounted } from 'vue'
import { getAnnouncementDetail, updateAnnouncementStatus } from '@/api/announcements'
import type { Announcement, AnnouncementStatus } from '@/types'
import { useToast } from '@/utils/toast'

export function useAnnouncementDetail(id: number) {
  const { toast } = useToast()

  const announcement = ref<Announcement | null>(null)
  const loading = ref(false)
  const updating = ref(false)
  const error = ref<string | null>(null)

  async function fetchDetail() {
    loading.value = true
    error.value = null

    try {
      announcement.value = await getAnnouncementDetail(id)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '상세 정보를 불러올 수 없습니다.'
      announcement.value = null
    } finally {
      loading.value = false
    }
  }

  async function updateStatus(status: AnnouncementStatus) {
    if (!announcement.value) return

    updating.value = true

    try {
      const result = await updateAnnouncementStatus(id, status)
      announcement.value.status = result.status
      announcement.value.updated_at = result.updated_at
      toast.success(`상태가 '${status}'(으)로 변경되었습니다.`)
    } catch {
      toast.error('상태 변경에 실패했습니다.')
    } finally {
      updating.value = false
    }
  }

  onMounted(() => {
    fetchDetail()
  })

  return {
    announcement,
    loading,
    updating,
    error,
    fetchDetail,
    updateStatus,
  }
}
