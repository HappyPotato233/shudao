<template>
  <div class="app">
    <!-- 顶栏 -->
    <header class="topbar">
      <div class="topbar-left">
        <span class="logo"><span class="logo-mark">蜀</span>蜀道安全助手</span>
        <span class="module-crumb">/ 安全管控平台</span>
      </div>
      <div class="topbar-right">
        <el-badge :value="unreadCount" :hidden="!unreadCount" :max="99">
          <span class="bell-btn" aria-label="消息通知" @click="$router.push('/notification')">
            <el-icon :size="16"><Bell /></el-icon>
          </span>
        </el-badge>
        <el-dropdown trigger="click" @command="onUserCommand">
          <span class="avatar">{{ store.initial }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="body">
      <!-- 全局导航（所有页面共用） -->
      <aside class="sidebar">
        <div class="nav-label">系统导航 / OPS</div>
        <el-menu :default-active="activeModule" class="module-nav" @select="onModuleSelect">
          <el-menu-item v-for="item in modules" :key="item.key" :index="item.key">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>
        <div class="net-card">
          <div class="net-title">蜀道运营专网</div>
          <div class="net-level">SEC-LEVEL: L4</div>
        </div>
      </aside>

      <!-- page-main：业务内容容器，内部由各页面自行组织三栏 -->
      <main class="page-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell, Warning, ChatDotRound, Document, BellFilled, User, UserFilled, DataBoard, Setting, Reading, TrendCharts,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'

const store = useUserStore()
const notificationStore = useNotificationStore()
const route = useRoute()
const router = useRouter()

const activeModule = computed(() => {
  const path = route.path
  if (path.startsWith('/hazard')) return 'hazard'
  if (path.startsWith('/ai')) return 'ai'
  if (path.startsWith('/exam')) return 'exam'
  if (path.startsWith('/notification')) return 'notification'
  if (path.startsWith('/profile')) return 'profile'
  if (path.startsWith('/user')) return 'user'
  if (path.startsWith('/admin/models')) return 'models'
  if (path.startsWith('/admin/testsets')) return 'testsets'
  if (path.startsWith('/admin/ai-statistics')) return 'aiStatistics'
  if (path.startsWith('/knowledge')) return 'knowledge'
  return 'dashboard'
})

const unreadCount = computed(() => notificationStore.unreadCount)

const modules = computed(() => {
  const role = store.role
  // Admin: 管理端 - 配置、知识库、测试、用户管理
  if (role === 'admin') {
    return [
      { key: 'dashboard', path: '/dashboard', label: '工作台首页', icon: DataBoard },
      { key: 'models', path: '/admin/models', label: 'AI模型配置', icon: Setting },
      { key: 'testsets', path: '/admin/testsets', label: '测试集管理', icon: Document },
      { key: 'knowledge', path: '/knowledge', label: '知识库管理', icon: Reading },
      { key: 'aiStatistics', path: '/admin/ai-statistics', label: 'AI 统计', icon: TrendCharts },
      { key: 'user', path: '/user', label: '用户管理', icon: UserFilled },
      { key: 'notification', path: '/notification', label: '消息通知', icon: BellFilled },
      { key: 'profile', path: '/profile', label: '个人中心', icon: User },
    ]
  }
  // 普通用户（User）：隐患管理、AI问答、考试工坊
  return [
    { key: 'dashboard', path: '/dashboard', label: '工作台首页', icon: DataBoard },
    { key: 'hazard', path: '/hazard', label: '隐患管理', icon: Warning },
    { key: 'ai', path: '/ai', label: 'AI 智能问答', icon: ChatDotRound },
    { key: 'exam', path: '/exam', label: '考试工坊', icon: Document },
    { key: 'notification', path: '/notification', label: '消息通知', icon: BellFilled },
    { key: 'profile', path: '/profile', label: '个人中心', icon: User },
  ]
})

function onModuleSelect(key: string) {
  const target = modules.value.find((m) => m.key === key)
  if (target) router.push(target.path)
}

function onUserCommand(command: string) {
  if (command === 'logout') {
    store.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  }
}

onMounted(() => {
  if (store.isLoggedIn) notificationStore.fetchUnreadCount()
})

// 路由变化时刷新未读计数（例如从消息通知页返回）
watch(
  () => route.fullPath,
  () => {
    if (store.isLoggedIn) notificationStore.fetchUnreadCount()
  },
)
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--color-bg);
}

/* 顶栏：蓝紫渐变品牌头部 + 3px 黑底描边 */
.topbar {
  height: var(--topbar-height, 56px);
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--gradient-brand);
  border-bottom: 3px solid #000;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-headline);
  font-weight: bold;
  font-size: 17px;
  letter-spacing: -0.3px;
  color: #ffffff;
}

/* 品牌图标：白色圆标（指南 .brand-icon） */
.logo-mark {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #ffffff;
  color: #14171a;
  display: grid;
  place-items: center;
  font-size: 14px;
  font-weight: bold;
}

.module-crumb {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: none;
}

/* 头像：白底黑描边圆 */
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #000;
  color: #14171a;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 2px 2px 0 #000;
  transition: all 0.2s ease;
}

.avatar:hover {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #000;
}

/* 消息铃铛：与右侧"系"字头像同款白底圆形 + 黑描边 */
.bell-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #000;
  color: #14171a;
  cursor: pointer;
  transition: all 0.2s ease;
  vertical-align: middle;
}

.bell-btn:hover {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #000;
}

.body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* 侧栏：白底 + 3px 黑右边描边 */
.sidebar {
  width: var(--sidebar-width, 208px);
  flex: none;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  background: #ffffff;
  border-right: 3px solid #000;
  padding: 10px 0;
  overflow-y: auto;
}

/* 导航分组标题 */
.nav-label {
  margin: 0 16px 6px;
  padding-bottom: 6px;
  border-bottom: 2px solid #000;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
}

/* 底部专网信息卡：靠 margin-top:auto 压到最底部 */
.net-card {
  margin: auto 8px 4px;
  padding: 10px;
  background: #EAEEFD;
  border: 2px solid #000;
  border-radius: var(--radius-input);
}

.net-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-strong);
}

.net-level {
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-muted);
}

.module-nav {
  border-right: none;
  padding: 0 0 10px;
}

.page-main {
  flex: 1;
  display: flex;
  min-width: 0;
  overflow: hidden;
  background: var(--color-bg);
}
</style>
