<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAnnouncementDetail } from '@/composables/useAnnouncementDetail'
import type { AnnouncementStatus } from '@/types'
import ScoreBadge from '@/components/common/ScoreBadge.vue'
import CategoryTag from '@/components/common/CategoryTag.vue'
import StatusSelect from '@/components/common/StatusSelect.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'

const route = useRoute()
const id = Number(route.params.id)

const {
  announcement: detail,
  loading,
  updating,
  error,
  updateStatus,
} = useAnnouncementDetail(id)

const showAnalysisDetail = ref(false)

function handleStatusChange(newStatus: string) {
  updateStatus(newStatus as AnnouncementStatus)
}

function formatPrice(price: number | null | undefined): string {
  if (!price) return '-'
  return new Intl.NumberFormat('ko-KR').format(price) + '원'
}

function formatDate(dt: string | null | undefined): string {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('ko-KR')
}

const DIMENSION_LABELS: Record<string, string> = {
  business_relevance: '사업 관련성',
  tech_match: '기술 적합성',
  budget_fit: '예산 규모',
  qualification: '참가자격 충족',
  competition: '경쟁 환경',
}

function dimensionLabel(key: string): string {
  return DIMENSION_LABELS[key] ?? key
}

function dimensionBarColor(score: number): string {
  if (score >= 80) return 'bg-red-500'
  if (score >= 60) return 'bg-yellow-500'
  if (score >= 40) return 'bg-green-500'
  return 'bg-gray-400'
}

const dDayInfo = computed(() => {
  if (!detail.value || !detail.value.bid_close_dt) return null

  const now = new Date()
  const closeDate = new Date(detail.value.bid_close_dt)
  const diffMs = closeDate.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) {
    return { text: '마감', colorClass: 'bg-gray-100 text-gray-500' }
  }
  if (diffDays === 0) {
    return { text: 'D-Day', colorClass: 'bg-red-100 text-red-700' }
  }

  const text = `D-${diffDays}`
  if (diffDays <= 3) {
    return { text, colorClass: 'bg-red-100 text-red-700' }
  }
  if (diffDays <= 7) {
    return { text, colorClass: 'bg-orange-100 text-orange-700' }
  }
  return { text, colorClass: 'bg-blue-100 text-blue-700' }
})
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-6">
    <LoadingSpinner v-if="loading" />
    <ErrorAlert v-else-if="error" :message="error" />

    <template v-else-if="detail">
      <!-- 기본 정보 -->
      <div class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">{{ detail.bid_notice_nm }}</h1>
            <p class="mt-1 text-sm text-gray-500">
              공고번호: {{ detail.bid_notice_no }}
            </p>
          </div>
          <StatusSelect :status="detail.status" :disabled="updating" @change="handleStatusChange" />
        </div>

        <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <span class="font-medium text-gray-500">공고기관:</span>
            <span class="ml-2 text-gray-900">{{ detail.ntce_instt_nm ?? '-' }}</span>
          </div>
          <div>
            <span class="font-medium text-gray-500">수요기관:</span>
            <span class="ml-2 text-gray-900">{{ detail.dminstt_nm ?? '-' }}</span>
          </div>
          <div>
            <span class="font-medium text-gray-500">추정가격:</span>
            <span class="ml-2 text-gray-900">{{ formatPrice(detail.presmpt_price) }}</span>
          </div>
          <div>
            <span class="font-medium text-gray-500">입찰기간:</span>
            <span class="ml-2 text-gray-900">
              {{ formatDate(detail.bid_begin_dt) }} ~ {{ formatDate(detail.bid_close_dt) }}
            </span>
            <span
              v-if="dDayInfo"
              class="ml-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
              :class="dDayInfo.colorClass"
            >
              {{ dDayInfo.text }}
            </span>
          </div>
        </div>

        <a
          v-if="detail.link_url"
          :href="detail.link_url"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-4 inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm
                 font-medium text-white hover:bg-blue-700 transition"
        >
          나라장터 원문 보기
        </a>
      </div>

      <!-- 분석 결과 -->
      <div class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">분석 결과</h2>

        <div class="flex items-center gap-4 mb-4">
          <ScoreBadge :score="detail.relevance_score" size="lg" />
          <div class="flex-1">
            <div class="flex items-center justify-between text-sm mb-1">
              <span class="font-medium text-gray-700">적합성 점수</span>
              <span class="font-semibold">{{ detail.relevance_score }}/100</span>
            </div>
            <div class="h-3 w-full rounded-full bg-gray-200">
              <div
                class="h-3 rounded-full transition-all"
                :class="{
                  'bg-red-500': detail.relevance_score >= 80,
                  'bg-yellow-500': detail.relevance_score >= 60 && detail.relevance_score < 80,
                  'bg-green-500': detail.relevance_score >= 40 && detail.relevance_score < 60,
                  'bg-gray-400': detail.relevance_score < 40,
                }"
                :style="{ width: `${detail.relevance_score}%` }"
              />
            </div>
          </div>
        </div>

        <div class="space-y-3 text-sm">
          <div v-if="detail.category" class="flex items-center gap-2">
            <span class="font-medium text-gray-500">카테고리:</span>
            <CategoryTag :category="detail.category" />
          </div>
          <div v-if="detail.summary">
            <span class="font-medium text-gray-500">요약:</span>
            <p class="mt-1 text-gray-700">{{ detail.summary }}</p>
          </div>
          <div v-if="detail.requirements">
            <span class="font-medium text-gray-500">참가자격:</span>
            <p class="mt-1 text-gray-700">{{ detail.requirements }}</p>
          </div>
          <div>
            <span class="font-medium text-gray-500">기업부설연구소:</span>
            <span class="ml-2" :class="detail.needs_research_lab ? 'text-red-600' : 'text-green-600'">
              {{ detail.needs_research_lab ? '필요' : '불필요' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 분석 상세 (접기/펼치기) -->
      <div
        v-if="detail.analysis_detail"
        class="rounded-lg border border-gray-200 bg-white shadow-sm"
      >
        <button
          class="flex w-full items-center justify-between p-6 text-left"
          @click="showAnalysisDetail = !showAnalysisDetail"
        >
          <h2 class="text-lg font-semibold text-gray-900">분석 상세</h2>
          <span class="text-gray-400">{{ showAnalysisDetail ? '접기' : '펼치기' }}</span>
        </button>

        <div v-if="showAnalysisDetail" class="border-t border-gray-200 p-6 space-y-6 text-sm">
          <!-- 5차원 점수 -->
          <div v-if="detail.analysis_detail.dimensions">
            <h3 class="font-medium text-gray-700 mb-3">5차원 적합성 분석</h3>
            <div class="space-y-3">
              <div
                v-for="(dim, key) in (detail.analysis_detail.dimensions as Record<string, {score: number, reason: string}>)"
                :key="key"
                class="space-y-1"
              >
                <div class="flex items-center justify-between">
                  <span class="font-medium text-gray-600">{{ dimensionLabel(key as string) }}</span>
                  <span class="font-semibold text-gray-900">{{ dim.score }}/100</span>
                </div>
                <div class="h-2 w-full rounded-full bg-gray-200">
                  <div
                    class="h-2 rounded-full transition-all"
                    :class="dimensionBarColor(dim.score)"
                    :style="{ width: `${dim.score}%` }"
                  />
                </div>
                <p class="text-xs text-gray-500">{{ dim.reason }}</p>
              </div>
            </div>
          </div>

          <!-- 핵심 요인 -->
          <div v-if="(detail.analysis_detail.key_factors as string[] | undefined)?.length">
            <h3 class="font-medium text-gray-700">핵심 요인</h3>
            <ul class="mt-1 list-disc list-inside text-gray-600">
              <li v-for="(f, i) in (detail.analysis_detail.key_factors as string[])" :key="i">{{ f }}</li>
            </ul>
          </div>

          <!-- 위험 요인 -->
          <div v-if="(detail.analysis_detail.risks as string[] | undefined)?.length">
            <h3 class="font-medium text-gray-700">위험 요인</h3>
            <ul class="mt-1 list-disc list-inside text-gray-600">
              <li v-for="(r, i) in (detail.analysis_detail.risks as string[])" :key="i">{{ r }}</li>
            </ul>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
