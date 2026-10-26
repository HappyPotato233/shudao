<template>
  <div class="nb-page dashboard-page">
    <!-- 1) 渐变欢迎卡：身份信息 + 半透明统计块 -->
    <section class="hero">
      <span class="hero-glow" aria-hidden="true"></span>
      <div class="hero-top">
        <div class="hero-identity">
          <span class="hero-avatar">蜀</span>
          <div class="hero-info">
            <div class="hero-title-row">
              <h1 class="hero-greeting">{{ greeting }}</h1>
              <span class="hero-status"><i></i>在线状态</span>
            </div>
            <div class="hero-meta">
              <span>@{{ store.user?.username || 'user' }}</span>
              <span class="sep">/</span>
              <span>{{ roleLabel }}</span>
              <template v-if="store.user?.department">
                <span class="sep">·</span>
                <span>{{ store.user?.department }}</span>
              </template>
            </div>
          </div>
        </div>
        <span class="hero-badge">
          <el-icon><CircleCheck /></el-icon>安全生产平稳运行
        </span>
      </div>
      <div class="hero-stats">
        <div v-for="s in statItems" :key="s.label" class="hero-stat">
          <div class="hero-stat-label">{{ s.label }}</div>
          <div class="hero-stat-value-line">
            <span class="hero-stat-value">{{ s.value }}</span>
            <span class="hero-stat-unit">{{ STAT_UNITS[s.label] || '' }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 2) 快捷入口网格 -->
    <section class="nb-panel">
      <div class="nb-panel-head">
        <div class="nb-panel-title">
          <h2>{{ store.role === 'admin' ? '系统核心管控快捷入口' : '快捷业务入口' }}</h2>
          <span class="panel-sub nb-mono">{{ store.role === 'admin' ? '/ SYSTEM OPERATIONS DISPATCH' : '/ QUICK ACCESS' }}</span>
        </div>
        <span class="head-meta nb-mono"><i class="meta-dot"></i>{{ quickLinks.length }} 个模块已就绪</span>
      </div>
      <div class="quick-body">
        <div
          class="quick-grid"
          :class="store.role === 'admin' ? 'quick-grid--admin' : 'quick-grid--user'"
        >
          <button
            v-for="(q, i) in quickLinks"
            :key="q.label"
            class="nb-card quick-tile"
            @click="$router.push(q.path)"
          >
            <div class="tile-head">
              <span class="tile-icon">
                <el-icon :size="20"><component :is="q.icon" /></el-icon>
              </span>
              <span class="tile-num nb-mono">{{ String(i + 1).padStart(2, '0') }}</span>
            </div>
            <div class="tile-main">
              <h3 class="tile-title">{{ q.label }}</h3>
              <p class="tile-desc">{{ q.desc }}</p>
            </div>
            <div class="tile-foot">
              <span>进入模块</span>
              <el-icon :size="14" class="tile-arrow"><ArrowRight /></el-icon>
            </div>
          </button>
          <!-- 装饰性系统状态瓷片（仅管理员，非业务入口） -->
          <div v-if="store.role === 'admin'" class="sys-tile">
            <div class="sys-top">
              <span class="sys-tag nb-mono">SYS_RUNNING</span>
              <span class="sys-code nb-mono">SEC-V4.2</span>
            </div>
            <div>
              <div class="sys-title">
                <el-icon><CircleCheck /></el-icon>蜀道高等级合规防护
              </div>
              <p class="sys-desc nb-mono">云端边端协同 · 安全管控平台在线</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 3) 最新动态时间线 + 分页条 -->
    <section class="nb-panel">
      <div class="nb-panel-head">
        <div class="nb-panel-title">
          <h2>{{ store.role === 'admin' ? '施工与监测最新动态' : '现场最新安全动态与预警' }}</h2>
          <span class="panel-sub nb-mono">{{ store.role === 'admin' ? '/ LIVE TELEMETRY LOG' : '/ LIVE FEED' }}</span>
        </div>
        <span class="head-meta">
          <span class="live-chip nb-mono"><i></i>LIVE</span>
          <span class="head-count nb-mono">共 {{ recentItems.length }} 条</span>
          <button class="ghost-btn" type="button" :disabled="loading" @click="loadData">
            <el-icon :class="{ 'spin-icon': loading }"><Refresh /></el-icon>刷新
          </button>
        </span>
      </div>

      <div class="feed-body">
        <div v-if="!recentItems.length" class="nb-empty">
          <el-icon :size="30"><Warning /></el-icon>
          <span>暂无隐患记录</span>
        </div>
        <template v-else>
          <div class="feed-list">
            <article v-for="item in pagedItems" :key="item.id" class="feed-item">
              <span
                class="feed-dot"
                :class="item.tagClass.replace('tag-', 'dot--')"
                aria-hidden="true"
              ><i></i></span>
              <div class="feed-card">
                <div class="feed-top">
                  <div class="feed-id">
                    <span class="feed-tag" :class="item.tagClass">{{ item.tagText }}</span>
                    <span class="feed-code nb-mono">#{{ item.id }}</span>
                  </div>
                  <span class="feed-time nb-mono">{{ item.time }}</span>
                </div>
                <p class="feed-text">{{ item.text }}</p>
              </div>
            </article>
          </div>
          <div class="feed-foot">
            <div class="foot-total nb-mono">
              共 <strong>{{ recentItems.length }}</strong> 条动态 · 显示第 {{ rangeStart }} - {{ rangeEnd }} 条
            </div>
            <div v-if="recentItems.length > pageSize" class="pager">
              <button
                class="pager-btn"
                type="button"
                aria-label="上一页"
                :disabled="recentPage <= 1"
                @click="recentPage--"
              >
                <el-icon><ArrowLeft /></el-icon>
              </button>
              <template v-for="(p, idx) in pagerItems" :key="idx">
                <span v-if="p === 0" class="pager-gap nb-mono">…</span>
                <button
                  v-else
                  class="pager-btn"
                  type="button"
                  :class="{ active: p === recentPage }"
                  @click="recentPage = p"
                >
                  {{ p }}
                </button>
              </template>
              <button
                class="pager-btn"
                type="button"
                aria-label="下一页"
                :disabled="recentPage >= totalPages"
                @click="recentPage++"
              >
                <el-icon><ArrowRight /></el-icon>
              </button>
            </div>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Warning, ChatDotRound, Document, BellFilled, Setting, TrendCharts, UserFilled, User, EditPen, Reading,
  ArrowLeft, ArrowRight, CircleCheck, Refresh,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'
import { hazardApi } from '@/api'
import http from '@/api/http'

const store = useUserStore()
const notificationStore = useNotificationStore()

const loading = ref(false)
const totalHazards = ref(0)
const pendingCount = ref(0)
const activeModelCount = ref(0)
const kbDocCount = ref(0)
const pageSize = 5
const recentPage = ref(1)
const recentItems = ref<{ id: string; tagText: string; tagClass: string; text: string; time: string }[]>([])
const pagedItems = computed(() =>
  recentItems.value.slice((recentPage.value - 1) * pageSize, recentPage.value * pageSize),
)

// 纯展示用：统计块单位
const STAT_UNITS: Record<string, string> = {
  'AI 模型可用': '个',
  '知识库文档': '篇',
  '隐患总数': '起',
  '待办隐患': '项',
  '未读通知': '条',
  '最新动态': '条',
}

// 纯展示用：欢迎语与角色标签
const greeting = computed(() =>
  store.role === 'admin' ? `你好，${store.displayName}` : `欢迎回来，${store.displayName}`,
)
const roleLabel = computed(() => (store.role === 'admin' ? '系统管理员' : '现场一线用户'))

// 纯展示用：自定义分页窗口
const totalPages = computed(() => Math.ceil(recentItems.value.length / pageSize))
const rangeStart = computed(() =>
  recentItems.value.length ? (recentPage.value - 1) * pageSize + 1 : 0,
)
const rangeEnd = computed(() => Math.min(recentPage.value * pageSize, recentItems.value.length))
const pagerItems = computed<number[]>(() => {
  const total = totalPages.value
  const cur = recentPage.value
  if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1)
  if (cur <= 3) return [1, 2, 3, 4, 0, total]
  if (cur >= total - 2) return [1, 0, total - 3, total - 2, total - 1, total]
  return [1, 0, cur - 1, cur, cur + 1, 0, total]
})

const statItems = computed(() => {
  if (store.role === 'admin') {
    return [
      { label: 'AI 模型可用', value: String(activeModelCount.value) },
      { label: '知识库文档', value: String(kbDocCount.value) },
      { label: '未读通知', value: String(notificationStore.unreadCount) },
      { label: '最新动态', value: String(recentItems.value.length) },
    ]
  }
  return [
    { label: '隐患总数', value: String(totalHazards.value) },
    { label: '待办隐患', value: String(pendingCount.value) },
    { label: '未读通知', value: String(notificationStore.unreadCount) },
    { label: '最新动态', value: String(recentItems.value.length) },
  ]
})

// 快捷入口：覆盖左侧菜单全部模块（管理员端不含"隐患上报"）
const quickLinks = computed(() => {
  if (store.role === 'admin') {
    return [
      { label: 'AI模型配置', desc: '大模型接入与参数配置', path: '/admin/models', icon: Setting },
      { label: '测试集管理', desc: '测试集维护与模型评估', path: '/admin/testsets', icon: Document },
      { label: '知识库', desc: '规范文档检索与学习', path: '/knowledge', icon: Reading },
      { label: 'AI 统计', desc: 'AI 问答满意度统计', path: '/admin/ai-statistics', icon: TrendCharts },
      { label: '用户管理', desc: '系统用户与权限管理', path: '/user', icon: UserFilled },
      { label: '消息通知', desc: '隐患整改消息提醒', path: '/notification', icon: BellFilled },
      { label: '个人中心', desc: '账号信息与设置', path: '/profile', icon: User },
    ]
  }
  return [
    { label: '隐患上报', desc: '拍照识别快速上报隐患', path: '/hazard', icon: Warning },
    { label: 'AI 问答', desc: '安全生产知识智能问答', path: '/ai', icon: ChatDotRound },
    { label: '考试工坊', desc: '在线出题与练习', path: '/exam', icon: EditPen },
    { label: '消息通知', desc: '隐患整改消息提醒', path: '/notification', icon: BellFilled },
    { label: '个人中心', desc: '账号信息与设置', path: '/profile', icon: User },
  ]
})

function levelTag(level: string) {
  const map: Record<string, { tagText: string; tagClass: string }> = {
    critical: { tagText: '重大', tagClass: 'tag-danger' },
    major: { tagText: '较大', tagClass: 'tag-warning' },
    general: { tagText: '一般', tagClass: 'tag-caution' },
    minor: { tagText: '轻微', tagClass: 'tag-info' },
  }
  return map[level] || { tagText: level, tagClass: 'tag-neutral' }
}

async function loadData() {
  loading.value = true
  try {
    await notificationStore.fetchUnreadCount()
    if (store.role === 'admin') {
      // 管理员：AI 模型可用数量 + 知识库文档数量（不加载隐患列表）
      const [modelsRes, kbRes] = await Promise.all([
        http.get('/admin/models').catch(() => []),
        http.get('/knowledge/documents', { params: { page: 1, page_size: 1 } }).catch(() => ({ total: 0 })),
      ])
      const models = Array.isArray(modelsRes) ? modelsRes : (modelsRes?.data ?? [])
      activeModelCount.value = models.filter((m: any) => m.is_active === 1 || m.is_active === true).length
      kbDocCount.value = (kbRes as any)?.total ?? (kbRes as any)?.data?.total ?? 0
      // 管理员最新动态复用近期隐患（若接口可用），否则留空
      try {
        const res = await hazardApi.list({ page: 1, page_size: 100 })
        recentItems.value = (res?.items || []).map((h: any) => {
          const tag = levelTag(h.level)
          return {
            id: h.hazard_id,
            tagText: tag.tagText,
            tagClass: tag.tagClass,
            text: h.title,
            time: (h.created_at || '').slice(0, 10),
          }
        })
      } catch {
        recentItems.value = []
      }
    } else {
      // 用户：隐患总数 + 待办隐患
      const res = await hazardApi.list({ page: 1, page_size: 100 })
      totalHazards.value = res?.total || 0
      const items = res?.items || []
      pendingCount.value = items.filter(
        (h: any) => h.status === 'pending' || h.status === 'processing',
      ).length
      recentItems.value = items.map((h: any) => {
        const tag = levelTag(h.level)
        return {
          id: h.hazard_id,
          tagText: tag.tagText,
          tagClass: tag.tagClass,
          text: h.title,
          time: (h.created_at || '').slice(0, 10),
        }
      })
    }
    recentPage.value = 1
  } catch (e: any) {
    ElMessage.warning('数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* ===== 1) 渐变欢迎卡 ===== */
.hero {
  position: relative;
  overflow: hidden;
  padding: 20px;
  color: #ffffff;
  background: var(--gradient-brand);
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.hero-glow {
  position: absolute;
  top: -90px;
  right: -60px;
  width: 340px;
  height: 340px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  filter: blur(48px);
  pointer-events: none;
}

.hero-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.hero-identity {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.hero-avatar {
  flex: none;
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #000;
  box-shadow: 3px 3px 0 #000;
  font-family: var(--font-headline);
  font-size: 22px;
  font-weight: 800;
  color: #14171a;
}

.hero-info {
  min-width: 0;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-greeting {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 24px;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -0.02em;
  color: #ffffff;
}

.hero-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.35);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
}

.hero-status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  animation: nb-status-pulse 2s ease-in-out infinite;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
  min-width: 0;
}

.hero-meta .sep {
  color: rgba(255, 255, 255, 0.4);
}

.hero-badge {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #ffffff;
  color: #14171a;
  border: 2px solid #000;
  border-radius: var(--radius-tag);
  box-shadow: 2px 2px 0 #000;
  font-size: 11px;
  font-weight: 700;
}

.hero-badge .el-icon {
  color: #15803D;
}

.hero-stats {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

/* 统计卡：半透明白底 + 白描边 */
.hero-stat {
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.18);
  border: 2px solid #ffffff;
  border-radius: var(--radius-card);
  backdrop-filter: blur(6px);
  transition: background 0.2s ease, transform 0.2s ease;
}

.hero-stat:hover {
  background: rgba(255, 255, 255, 0.26);
  transform: translateY(-2px);
}

.hero-stat-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.82);
}

.hero-stat-label::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ffffff;
  flex: none;
}

.hero-stat:nth-child(1) .hero-stat-label::before {
  background: #C1CCF9;
}
.hero-stat:nth-child(2) .hero-stat-label::before {
  background: #EF4444;
}
.hero-stat:nth-child(3) .hero-stat-label::before {
  background: #C1CCF9;
}
.hero-stat:nth-child(4) .hero-stat-label::before {
  background: #22C55E;
}

.hero-stat-value-line {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 2px;
}

.hero-stat-value {
  font-family: var(--font-mono);
  font-size: 30px;
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: #ffffff;
}

.hero-stat-unit {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.75);
}

.hero-stat:nth-child(3) .hero-stat-value {
  color: #F5A623;
}

/* ===== 2) 面板通用补充 ===== */
.dashboard-page .nb-panel-head {
  flex-wrap: wrap;
}

.nb-panel-title h2 {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--color-text-strong);
}

.panel-sub {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--color-text-muted);
  white-space: nowrap;
}

.head-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: none;
}

.meta-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--primary);
}

.head-count {
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
}

/* ===== 快捷入口 ===== */
.quick-body {
  padding: 14px;
}

.quick-grid {
  display: grid;
  gap: 12px;
}

.quick-grid--admin {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.quick-grid--user {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.quick-tile {
  --tile-accent: var(--primary);
  --tile-tint: var(--primary-light);
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 152px;
  padding: 14px;
  background: #ffffff;
  color: var(--color-text-strong);
  font: inherit;
  text-align: left;
}

.quick-tile:nth-child(4n + 2) {
  --tile-accent: #15803d;
  --tile-tint: #F0FDF4;
}

.quick-tile:nth-child(4n + 3) {
  --tile-accent: #8A6400;
  --tile-tint: #FDF3DD;
}

.quick-tile:nth-child(4n + 4) {
  --tile-accent: #7c3aed;
  --tile-tint: #EAEEFD;
}

.tile-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.tile-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border: 2px solid #000;
  border-radius: var(--radius-tag);
  background: var(--tile-tint);
  color: var(--tile-accent);
  box-shadow: 2px 2px 0 #000;
  transition: background 0.2s ease, color 0.2s ease;
}

.tile-num {
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  color: #657786;
}

.tile-main {
  min-width: 0;
}

.tile-title {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--color-text-strong);
  transition: color 0.2s ease;
}

.tile-desc {
  margin: 2px 0 0;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tile-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--color-divider);
  font-size: 11px;
  font-weight: 700;
  color: var(--tile-accent);
}

.tile-arrow {
  transition: transform 0.2s ease;
}

.quick-tile:hover .tile-icon {
  background: var(--tile-accent);
  color: #ffffff;
}

.quick-tile:hover .tile-title {
  color: var(--tile-accent);
}

.quick-tile:hover .tile-arrow {
  transform: translateX(4px);
}

/* 装饰性系统状态瓷片 */
.sys-tile {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12px;
  min-height: 152px;
  padding: 14px;
  background: #EAEEFD;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.sys-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sys-tag {
  padding: 1px 6px;
  background: #000;
  color: #ffffff;
  border-radius: var(--radius-tag);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.sys-code {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-muted);
}

.sys-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 800;
  color: var(--color-text-strong);
}

.sys-title .el-icon {
  color: var(--primary);
}

.sys-desc {
  margin: 4px 0 0;
  font-size: 10px;
  font-weight: 500;
  color: var(--color-text-muted);
}

/* ===== 3) 最新动态时间线 ===== */
.live-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 1px 8px;
  background: var(--danger-light);
  color: var(--danger-text);
  border: 2px solid #000;
  border-radius: var(--radius-tag);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.live-chip i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--danger-text);
  animation: nb-status-pulse 2s ease-in-out infinite;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  box-shadow: 2px 2px 0 #000;
  font-family: var(--font);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-strong);
  cursor: pointer;
  transition: all 0.2s ease;
}

.ghost-btn:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #000;
}

.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin-icon {
  animation: nb-spin 1s linear infinite;
}

.feed-body {
  min-height: 240px;
  padding: 16px 14px 12px;
}

.feed-list {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-left: 22px;
}

.feed-list::before {
  content: "";
  position: absolute;
  left: 9px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  background: #000;
}

.feed-item {
  position: relative;
}

.feed-dot {
  position: absolute;
  left: -22px;
  top: 4px;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #000;
  box-shadow: 2px 2px 0 #000;
}

.feed-dot i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-text-muted);
}

.feed-dot.dot--danger {
  background: var(--danger);
}
.feed-dot.dot--danger i {
  background: #ffffff;
}

.feed-dot.dot--warning {
  background: #F5A623;
}
.feed-dot.dot--warning i {
  background: #000000;
}

.feed-dot.dot--caution {
  background: #F5A623;
}
.feed-dot.dot--caution i {
  background: #000000;
}

.feed-dot.dot--info {
  background: var(--info);
}
.feed-dot.dot--info i {
  background: #ffffff;
}

.feed-dot.dot--neutral {
  background: #ffffff;
}

.feed-card {
  padding: 10px 12px;
  background: #f7f9fb;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  transition: background 0.2s ease;
}

.feed-card:hover {
  background: #ffffff;
}

.feed-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.feed-id {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.feed-tag {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  padding: 1px 7px;
  border: 2px solid #000;
  border-radius: var(--radius-tag);
  box-shadow: 1px 1px 0 #000;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.5;
  white-space: nowrap;
}

.feed-tag.tag-danger {
  background: var(--danger-text);
  color: #ffffff;
}

.feed-tag.tag-warning {
  background: #F5A623;
  color: #000000;
}

.feed-tag.tag-caution {
  background: #F5A623;
  color: #000000;
}

.feed-tag.tag-info {
  background: var(--info);
  color: #ffffff;
}

.feed-tag.tag-neutral {
  background: #ffffff;
  color: var(--color-text-muted);
}

.feed-code {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-time {
  flex: none;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
}

.feed-text {
  margin: 6px 0 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--color-text-strong);
}

.feed-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 14px;
  padding: 10px 4px 0;
  border-top: 2px solid var(--color-divider);
}

.foot-total {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
}

.foot-total strong {
  font-size: 13px;
  font-weight: 800;
  color: var(--primary);
}

.pager {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pager-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-tag);
  box-shadow: 2px 2px 0 #000;
  color: var(--color-text-strong);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.2s ease;
}

.pager-btn:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #000;
}

.pager-btn.active {
  background-image: var(--gradient-brand);
  color: #ffffff;
}

.pager-btn:disabled {
  opacity: 0.4;
  box-shadow: none;
  cursor: not-allowed;
}

.pager-gap {
  padding: 0 2px;
  font-size: 11px;
  font-weight: 800;
  color: var(--color-text-muted);
}

@keyframes nb-status-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

@keyframes nb-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ===== 响应式 ===== */
@media (max-width: 1180px) {
  .quick-grid--admin,
  .quick-grid--user {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .quick-grid--admin,
  .quick-grid--user {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .quick-grid--admin,
  .quick-grid--user {
    grid-template-columns: minmax(0, 1fr);
  }

  .hero {
    padding: 16px;
  }

  .hero-greeting {
    font-size: 20px;
  }
}
</style>
