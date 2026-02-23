import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    icon?: string
    showInMenu?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: DefaultLayout,
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

router.beforeEach((to, _from, next) => {
  const pageTitle = to.meta.title
  document.title = pageTitle ? `${pageTitle} | ${APP_NAME}` : APP_NAME
  next()
})

export default router
