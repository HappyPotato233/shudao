<template>
  <div class="stats-page">
    <div class="stats-inner">
      <div class="page-head">
        <h1 class="page-title">AI 统计</h1>
      </div>

      <div class="card filter-card">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 280px"
          @change="onDateRangeChange"
        />
        <el-radio-group v-model="quickDays" @change="onQuickDaysChange">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="loading" @click="loadStats">查询</el-button>
      </div>

      <div class="stat-cards">
        <div class="card stat-card">
          <div class="stat-value">{{ stats?.total_feedback_count ?? 0 }}</div>
          <div class="stat-label">总反馈数</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value like">{{ stats?.like_count ?? 0 }}</div>
          <div class="stat-label">点赞数</div>
          <div class="stat-sub">点踩 {{ stats?.dislike_count ?? 0 }} 次</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{{ likeRateText }}</div>
          <div class="stat-label">点赞率</div>
          <div class="stat-sub">共 {{ stats?.total_feedback_count ?? 0 }} 次反馈</div>
        </div>
        <div class="card stat-card">
          <div class="stat-value">{{ stats?.total_questions ?? 0 }}</div>
          <div class="stat-label">总提问数</div>
          <div class="stat-sub">平均响应 {{ formatMs(stats?.avg_response_time_ms) }}</div>
        </div>
      </div>

      <div class="card chart-card">
        <div class="card-title">点踩原因分布</div>
        <div ref="chartRef" class="chart"></div>
        <el-empty v-if="!hasDislikeReason" description="暂无点踩数据" :image-size="60" />
      </div>

      <div class="card">
        <div class="card-title">模型调用统计</div>
        <el-table v-loading="loading" :data="stats?.model_usage || []" stripe>
          <el-table-column prop="model" label="模型名称" min-width="220" />
          <el-table-column prop="count" label="调用次数" width="140" />
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { statisticsApi, type AiSatisfaction } from '@/api'

const DISLIKE_REASONS: { key: keyof AiSatisfaction['dislike_reasons']; label: string }[] = [
  { key: 'inaccurate', label: '回答不准确' },
  { key: 'incomplete', label: '回答不完整' },
  { key: 'misunderstanding', label: '理解错误' },
  { key: 'off_topic', label: '与安全无关' },
  { key: 'other', label: '其他' },
]

const loading = ref(false)
const stats = ref<AiSatisfaction | null>(null)
const dateRange = ref<[string, string] | null>(null)
const quickDays = ref<number | null>(30)
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const likeRateText = computed(() => `${((stats.value?.like_rate ?? 0) * 100).toFixed(1)}%`)
const hasDislikeReason = computed(() =>
  DISLIKE_REASONS.some((r) => (stats.value?.dislike_reasons?.[r.key] ?? 0) > 0),
)

// 日期范围与天数快捷互斥
function onDateRangeChange(value: [string, string] | null) {
  if (value) quickDays.value = null
}

function onQuickDaysChange(value: number | null) {
  if (value) dateRange.value = null
}

// 计算查询参数：优先日期范围（换算为天数），其次快捷天数，都不选则查全部
function currentDays(): number | undefined {
  if (dateRange.value?.[0]) {
    const [y, m, d] = dateRange.value[0].split('-').map(Number)
    const from = new Date(y!, m! - 1, d!).getTime()
    const now = new Date()
    const to = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    const days = Math.floor((to - from) / 86400000) + 1
    return Math.min(Math.max(days, 1), 365)
  }
  return quickDays.value ?? undefined
}

function formatMs(ms?: number) {
  if (!ms) return '-'
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms} ms`
}

async function loadStats() {
  loading.value = true
  try {
    const params: { days?: number } = {}
    const days = currentDays()
    if (days) params.days = days
    stats.value = await statisticsApi.aiSatisfaction(params)
    await nextTick()
    renderChart()
  } catch (e: any) {
    ElMessage.warning('统计数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const labels = DISLIKE_REASONS.map((r) => r.label)
  const values = DISLIKE_REASONS.map((r) => stats.value?.dislike_reasons?.[r.key] ?? 0)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '点踩次数',
        type: 'bar',
        barWidth: 36,
        data: values,
        itemStyle: { color: '#2F54EB', borderRadius: [4, 4, 0, 0] },
      },
    ],
  })
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.stats-page {
  flex: 1;
  overflow: auto;
}
.stats-inner {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}
.page-head {
  margin-bottom: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 16px;
}
.filter-card {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
}
.stat-value.like {
  color: var(--success);
}
.stat-label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}
.stat-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-primary);
}
.chart-card {
  margin-bottom: 16px;
}
.chart {
  width: 100%;
  height: 300px;
}
</style>
