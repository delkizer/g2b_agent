import { ref } from 'vue'
import { exportAnnouncements } from '@/api/announcements'
import type { ExportParams } from '@/api/types'
import { useToast } from '@/utils/toast'

export function useExport() {
  const { toast } = useToast()
  const exporting = ref(false)

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  async function doExport(format: 'csv' | 'xlsx', filterOverrides?: Partial<ExportParams>) {
    exporting.value = true

    try {
      const params: ExportParams = {
        format,
        ...filterOverrides,
      }

      const { blob, filename } = await exportAnnouncements(params)
      downloadBlob(blob, filename)
      toast.success(`${format.toUpperCase()} 파일을 다운로드했습니다.`)
    } catch {
      toast.error('내보내기에 실패했습니다.')
    } finally {
      exporting.value = false
    }
  }

  function exportCsv(filterOverrides?: Partial<ExportParams>) {
    return doExport('csv', filterOverrides)
  }

  function exportExcel(filterOverrides?: Partial<ExportParams>) {
    return doExport('xlsx', filterOverrides)
  }

  return {
    exporting,
    exportCsv,
    exportExcel,
  }
}
