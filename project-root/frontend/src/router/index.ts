import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
        meta: { title: '工作台首页' },
      },
      {
        path: 'hazard',
        name: 'hazard',
        component: () => import('@/views/hazard/HazardWorkspace.vue'),
        meta: { title: '隐患管理' },
      },
      {
        path: 'ai',
        name: 'ai',
        component: () => import('@/views/ai/AiAssistantView.vue'),
        meta: { title: 'AI 智能问答', roles: ['user'] },
      },
      {
        path: 'exam',
        name: 'exam',
        component: () => import('@/views/exam/ExamWorkspace.vue'),
        meta: { title: '考试工坊' },
      },
      {
        path: 'notification',
        name: 'notification',
        component: () => import('@/views/notification/NotificationView.vue'),
        meta: { title: '消息通知' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/profile/ProfileView.vue'),
        meta: { title: '个人中心' },
      },
      {
        path: 'user',
        name: 'user',
        component: () => import('@/views/user/UserManagementView.vue'),
        meta: { title: '用户管理', roles: ['admin'] },
      },
      {
        path: 'admin/models',
        name: 'admin-models',
        component: () => import('@/views/admin/ModelConfigView.vue'),
        meta: { title: 'AI模型配置', roles: ['admin'] },
      },
      {
        path: 'admin/testsets',
        name: 'admin-testsets',
        component: () => import('@/views/admin/TestSetView.vue'),
        meta: { title: '测试集管理', roles: ['admin'] },
      },
      {
        path: 'admin/ai-statistics',
        name: 'admin-ai-statistics',
        component: () => import('@/views/admin/AiStatisticsView.vue'),
        meta: { title: 'AI 统计', roles: ['admin'] },
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('@/views/admin/KnowledgeView.vue'),
        meta: { title: '知识库管理', roles: ['admin'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach(async (to) => {
  const store = useUserStore()

  // 公开页面直接放行
  if (to.meta.public) return true

  // 未登录跳登录
  if (!store.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 拉取用户信息：失败（token 失效 / 后端不可用）时不阻塞路由，回登录页，避免白屏
  if (!store.user) {
    try {
      await store.fetchMe()
    } catch {
      return { path: '/login' }
    }
  }

  // 角色权限校验
  const roles = to.meta.roles as string[] | undefined
  if (roles && roles.length > 0 && !roles.includes(store.role as string)) {
    return { path: '/dashboard' }
  }

  return true
})

export default router
