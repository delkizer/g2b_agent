import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    icon?: string
    showInMenu?: boolean
    requiresAuth?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: {
      title: '로그인',
      requiresAuth: false,
    },
  },
  {
    path: '/',
    component: DefaultLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/pages/DashboardPage.vue'),
        meta: {
          title: '대시보드',
          icon: 'home',
          showInMenu: true,
        },
      },
      {
        path: 'announcements',
        name: 'AnnouncementList',
        component: () => import('@/pages/AnnouncementListPage.vue'),
        meta: {
          title: '공고 목록',
          icon: 'list',
          showInMenu: true,
        },
      },
      {
        path: 'announcements/:id',
        name: 'AnnouncementDetail',
        component: () => import('@/pages/AnnouncementDetailPage.vue'),
        props: true,
        meta: {
          title: '공고 상세',
          showInMenu: false,
        },
      },
      {
        path: 'report',
        name: 'Report',
        component: () => import('@/pages/ReportPage.vue'),
        meta: {
          title: '리포트',
          icon: 'chart-bar',
          showInMenu: true,
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: {
      title: '페이지를 찾을 수 없습니다',
    },
  },
]

const APP_NAME = '나라장터 마켓 인텔리전스'

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  },
})

router.beforeEach(async (to, _from, next) => {
  const pageTitle = to.meta.title
  document.title = pageTitle ? `${pageTitle} | ${APP_NAME}` : APP_NAME

  const auth = useAuthStore()

  // requiresAuth가 명시적으로 false인 경우 (로그인 페이지)
  if (to.meta.requiresAuth === false) {
    if (auth.isLoggedIn) {
      return next('/')
    }
    return next()
  }

  // 인증 필요한 페이지 — 부모 라우트의 meta도 확인
  const needsAuth = to.matched.some((record) => record.meta.requiresAuth !== false)
  if (!needsAuth) {
    return next()
  }

  // 이미 로그인된 상태
  if (auth.isLoggedIn) {
    return next()
  }

  // fetchCurrentUser로 세션 확인 (쿠키 기반)
  const ok = await auth.fetchCurrentUser()
  if (ok) {
    return next()
  }

  // refresh 시도
  if (!auth.refreshTried) {
    auth.refreshTried = true
    const refreshed = await auth.refreshTokens()
    if (refreshed) {
      return next()
    }
  }

  return next('/login')
})

export default router
