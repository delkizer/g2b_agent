import { ref } from 'vue'
import {
  getAttachments,
  getOutputFiles,
  getBidContext,
  type FileItem,
} from '@/api/files'

export function useAnnouncementFiles() {
  const attachments = ref<FileItem[]>([])
  const outputFiles = ref<FileItem[]>([])
  const bidContextContent = ref<string | null>(null)
  const bidContextExists = ref(false)
  const loadingFiles = ref(false)
  const loadingBidContext = ref(false)

  async function fetchFiles(bidNoticeNo: string) {
    loadingFiles.value = true
    try {
      const [attachRes, outputRes] = await Promise.all([
        getAttachments(bidNoticeNo),
        getOutputFiles(bidNoticeNo),
      ])
      attachments.value = attachRes.files
      outputFiles.value = outputRes.files
    } catch {
      attachments.value = []
      outputFiles.value = []
    } finally {
      loadingFiles.value = false
    }
  }

  async function fetchBidContext(bidNoticeNo: string) {
    loadingBidContext.value = true
    try {
      const res = await getBidContext(bidNoticeNo)
      bidContextExists.value = res.exists
      bidContextContent.value = res.content
    } catch {
      bidContextExists.value = false
      bidContextContent.value = null
    } finally {
      loadingBidContext.value = false
    }
  }

  return {
    attachments,
    outputFiles,
    bidContextContent,
    bidContextExists,
    loadingFiles,
    loadingBidContext,
    fetchFiles,
    fetchBidContext,
  }
}
