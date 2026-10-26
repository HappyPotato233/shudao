<template>
  <!-- 出卷工作台 -->
  <div class="nb-page exam-page">
    <!-- 页头 -->
    <header class="nb-page-head">
      <div class="head-left">
        <div class="head-icon">
          <el-icon :size="22"><School /></el-icon>
        </div>
        <div class="head-text">
          <div class="head-title-row">
            <h1 class="nb-title">出卷工作台</h1>
            <span class="nb-chip nb-chip--info">智能组卷</span>
          </div>
          <p class="head-sub">基于出题依据与附件题库的智能试卷配置 · 实时结构预览</p>
        </div>
      </div>
      <div class="head-right">
        <div class="status-pill nb-mono">
          <span class="status-dot"></span>
          历史试卷 {{ historyList.length }} 卷
        </div>
      </div>
    </header>

    <!-- 三栏工作区 -->
    <div class="workspace-grid">
      <!-- 左栏：新建出卷 + 历史试卷 -->
      <aside class="rail">
        <button type="button" class="btn-new" @click="onNewPaper">
          <el-icon><Plus /></el-icon>
          新建出卷
        </button>

        <section class="nb-panel history-panel">
          <div class="nb-panel-head">
            <div class="nb-panel-title">
              历史试卷
              <span class="count-chip nb-mono">{{ historyList.length }}</span>
            </div>
          </div>
          <div class="history-list">
            <div v-if="!historyList.length" class="nb-empty">
              <span>暂无试卷</span>
              <span class="empty-sub">完成配置后生成第一份试卷</span>
            </div>
            <div
              v-for="item in historyList"
              :key="item.id"
              class="history-item"
              :class="{ active: item.id === activeHistoryId }"
              @click="activeHistoryId = item.id"
            >
              <span class="h-code nb-mono" :title="item.id">{{ item.id }}</span>
              <span class="h-title">{{ item.title }}</span>
            </div>
          </div>
        </section>
      </aside>

      <!-- 中栏：出题配置 -->
      <section class="nb-panel center">
        <div class="nb-panel-head">
          <div class="nb-panel-title">智能出题配置</div>
          <span class="head-meta nb-mono">AI PIPELINE</span>
        </div>

        <div class="center-body">
          <el-form label-position="top" class="exam-form">
            <el-form-item label="试卷名称" required>
              <el-input v-model="paper.title" placeholder="请输入试卷名称" />
            </el-form-item>

            <el-form-item>
              <template #label>
                <span>出题依据内容</span>
                <span class="field-hint">章节 / 知识点 / 培训内容</span>
              </template>
              <el-input
                v-model="paper.basis"
                type="textarea"
                :rows="4"
                placeholder="请输入章节、知识点或培训内容……"
              />
            </el-form-item>

            <el-form-item>
              <template #label>
                <span>从附件生成考题</span>
                <span class="field-hint">支持 xlsx，最多五个附件</span>
              </template>
              <el-upload
                drag
                class="upload-zone"
                :auto-upload="false"
                :limit="5"
                accept=".xlsx"
                :on-change="onFileChange"
                :on-exceed="onExceed"
              >
                <div class="drop-inner">
                  <div class="drop-icon">
                    <el-icon :size="22"><UploadFilled /></el-icon>
                  </div>
                  <div class="drop-title">点击或拖拽上传 xlsx 文件</div>
                  <div class="drop-sub">最多 5 个附件 · 解析后用于生成考题</div>
                </div>
              </el-upload>
            </el-form-item>

            <div class="type-card">
              <div class="type-card-head">
                <div class="type-card-title">
                  <el-icon><MagicStick /></el-icon>
                  试题结构与题型设置
                </div>
                <el-checkbox v-model="paper.includeBasis">附带出题依据条款</el-checkbox>
              </div>

              <div class="type-grid">
                <div v-for="t in questionTypes" :key="t.key" class="type-item">
                  <div class="type-item-head">
                    <span class="type-label">{{ t.label }}题</span>
                    <span class="type-tag nb-mono">题量</span>
                  </div>
                  <div class="type-item-body">
                    <span class="type-total nb-mono">共 {{ paper.counts[t.key] }} 题</span>
                    <el-input-number v-model="paper.counts[t.key]" :min="0" :max="50" />
                  </div>
                </div>
              </div>

              <div class="calc-strip nb-mono">
                <span>试题总数: <b>{{ totalQuestions }}</b> 题</span>
                <span class="calc-sep">|</span>
                <span>已启用题型: <b>{{ activeTypeCount }}</b> 类</span>
              </div>
            </div>
          </el-form>
        </div>

        <div class="center-foot">
          <el-button class="action-btn" :icon="DocumentCopy">保存草稿</el-button>
          <el-button class="action-btn" type="primary" :icon="MagicStick" @click="onGenerate">
            生成试卷
          </el-button>
        </div>
      </section>

      <!-- 右栏：实时结构预览 -->
      <aside class="report">
        <div class="preview-head">
          <div class="preview-title">
            <el-icon><PieChart /></el-icon>
            试卷实时结构预览
          </div>
          <span class="live-dot" title="实时同步"></span>
        </div>

        <section class="nb-panel preview-card">
          <div class="nb-panel-head">
            <div class="nb-panel-title">基本信息概览</div>
            <span class="head-meta nb-mono">LIVE</span>
          </div>
          <div class="preview-body">
            <div class="pv-block">
              <span class="pv-label nb-mono">试卷标题</span>
              <p class="pv-title">{{ paper.title || '未命名试卷' }}</p>
            </div>
            <div class="pv-grid">
              <div class="pv-cell">
                <span class="pv-label nb-mono">总题量</span>
                <span class="pv-value nb-mono">{{ totalQuestions }} 题</span>
              </div>
              <div class="pv-cell">
                <span class="pv-label nb-mono">启用题型</span>
                <span class="pv-value nb-mono">{{ activeTypeCount }} 类</span>
              </div>
            </div>
            <div class="pv-block">
              <span class="pv-label nb-mono">出题依据</span>
              <p class="pv-text">{{ paper.basis || '暂未填写出题依据' }}</p>
            </div>
          </div>
        </section>

        <section class="nb-panel preview-card">
          <div class="nb-panel-head">
            <div class="nb-panel-title">题型与题量结构</div>
            <span class="head-meta nb-mono">{{ totalQuestions }} Q</span>
          </div>
          <div class="preview-body">
            <div v-if="!totalQuestions" class="nb-empty">
              <span>尚未配置题量</span>
              <span class="empty-sub">调整题型数量后实时统计</span>
            </div>
            <template v-else>
              <div class="ratio-track">
                <div
                  v-for="s in visibleTypeStats"
                  :key="s.key"
                  class="ratio-seg"
                  :class="s.segClass"
                  :style="{ width: s.percent + '%' }"
                >{{ s.percent }}%</div>
              </div>
              <div class="legend">
                <div v-for="s in typeStats" :key="s.key" class="legend-row">
                  <span class="legend-left">
                    <span class="swatch" :class="s.segClass"></span>
                    {{ s.label }}题
                  </span>
                  <span class="legend-count nb-mono">{{ s.count }} 题 / {{ s.percent }}%</span>
                </div>
              </div>
            </template>
          </div>
        </section>

        <section class="nb-panel preview-card">
          <div class="nb-panel-head">
            <div class="nb-panel-title">出题依据设置</div>
            <span
              class="nb-chip"
              :class="paper.includeBasis ? 'nb-chip--normal' : 'nb-chip--neutral'"
            >{{ paper.includeBasis ? '已附带' : '未附带' }}</span>
          </div>
          <div class="preview-body">
            <div class="basis-state" :class="{ on: paper.includeBasis }">
              <span>附带出题依据条款</span>
              <span class="nb-mono">{{ paper.includeBasis ? 'ON' : 'OFF' }}</span>
            </div>
            <p class="pv-hint">勾选后，生成的题目会一并输出对应出题依据条款。</p>
          </div>
        </section>
      </aside>
    </div>

    <!-- 可移动弹窗：是否进入题库 -->
    <el-dialog
      v-model="dialogVisible"
      width="420px"
      draggable
      append-to-body
      :show-close="false"
    >
      <template #header>
        <div class="dialog-head">
          <div class="dialog-head-title">
            <span class="dialog-icon">
              <el-icon><FolderOpened /></el-icon>
            </span>
            题库入库确认
          </div>
          <button type="button" class="dialog-close" @click="dialogVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>
      <p class="dialog-text">
        附件中的题目解析完成后，是否同时保存到题库？选择「否」将仅用于当前试卷。
      </p>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="onDialogChoice(false)">否，仅生成试卷</el-button>
          <el-button type="primary" @click="onDialogChoice(true)">是，同时进入题库</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import {
  Plus,
  UploadFilled,
  DocumentCopy,
  MagicStick,
  School,
  PieChart,
  FolderOpened,
  Close,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { examApi } from '@/api'

const activeHistoryId = ref('')
const dialogVisible = ref(false)
const hasAttachment = ref(false)

const historyList = ref<{ id: string; title: string }[]>([])

const questionTypes = [
  { key: 'single', label: '单选' },
  { key: 'judge', label: '判断' },
  { key: 'multi', label: '多选' },
  { key: 'essay', label: '简答' },
]

const paper = reactive({
  title: '',
  basis: '',
  includeBasis: false,
  counts: { single: 10, judge: 5, multi: 3, essay: 2 } as Record<string, number>,
})

// 纯 UI 派生数据：题量合计 / 启用题型数 / 结构占比
const totalQuestions = computed(() =>
  questionTypes.reduce((sum, t) => sum + (Number(paper.counts[t.key]) || 0), 0),
)

const activeTypeCount = computed(
  () => questionTypes.filter((t) => (Number(paper.counts[t.key]) || 0) > 0).length,
)

const typeStats = computed(() => {
  const total = totalQuestions.value
  return questionTypes.map((t, i) => {
    const count = Number(paper.counts[t.key]) || 0
    return {
      key: t.key,
      label: t.label,
      count,
      percent: total ? Math.round((count / total) * 100) : 0,
      segClass: `seg-${i}`,
    }
  })
})

const visibleTypeStats = computed(() => typeStats.value.filter((s) => s.count > 0))

async function loadPapers() {
  try {
    const res = await examApi.papers({ page: 1, page_size: 50 })
    const items = res?.items || []
    historyList.value = items.map((p: any) => ({ id: p.paper_id, title: p.title }))
  } catch (e: any) {
    ElMessage.warning('试卷列表加载失败，请稍后重试')
  }
}

function onNewPaper() {
  paper.title = ''
  paper.basis = ''
  paper.includeBasis = false
  paper.counts = { single: 10, judge: 5, multi: 3, essay: 2 }
  hasAttachment.value = false
}

function onFileChange() {
  hasAttachment.value = true
}

function onExceed() {
  ElMessage.warning('最多上传五个附件')
}

function onGenerate() {
  if (!paper.title.trim()) {
    ElMessage.warning('请输入试卷名称')
    return
  }
  // 有附件时弹出「是否进入题库」
  if (hasAttachment.value) {
    dialogVisible.value = true
  } else {
    ElMessage.success('试卷已生成')
  }
}

function onDialogChoice(enterBank: boolean) {
  dialogVisible.value = false
  ElMessage.success(enterBank ? '已保存到题库并生成试卷' : '试卷已生成')
}

onMounted(() => {
  loadPapers()
})
</script>

<style scoped>
/* ===== 页面骨架：三栏各自独立滚动 ===== */
.exam-page {
  gap: 14px;
  padding: 18px 20px 16px;
  min-height: 0;
  overflow: hidden;
}

.nb-page-head {
  flex: none;
  flex-wrap: wrap;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.head-icon {
  flex: none;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  color: var(--primary);
}

.head-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.head-sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

.head-right {
  flex: none;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--success);
  border: 1px solid #000;
}

/* ===== 三栏网格 ===== */
.workspace-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--history-width) minmax(0, 1fr) var(--panel-width);
  gap: 14px;
}

/* ===== 左栏：新建 + 历史试卷 ===== */
.rail {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
}

.btn-new {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  padding: 0 14px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background-image: var(--gradient-brand);
  color: #ffffff;
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-new:hover {
  transform: translate(-2px, -2px);
  box-shadow: var(--shadow-hover);
}

.btn-new:active {
  transform: translate(2px, 2px);
  box-shadow: none;
}

.history-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.history-panel .nb-panel-head {
  flex: none;
  padding: 8px 10px;
  gap: 6px;
}

.count-chip {
  padding: 0 6px;
  border-radius: var(--radius-tag);
  background: #14171a;
  color: #ffffff;
  font-size: 10px;
  line-height: 1.7;
}

.history-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}

.history-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 9px 10px;
  background: #ffffff;
  border: 2px solid #000;
  border-left-width: 5px;
  border-left-color: #E1E8ED;
  border-radius: var(--radius-card);
  cursor: pointer;
  transition: all 0.2s ease;
}

.history-item:hover {
  transform: translate(-2px, -2px);
  box-shadow: var(--shadow-card);
}

.history-item.active {
  border-left-color: var(--primary);
  background: linear-gradient(135deg, var(--primary-light), #EAEEFD);
  box-shadow: 3px 3px 0 #000;
}

.h-code {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item.active .h-code {
  color: var(--primary);
}

.h-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--text-primary);
  word-break: break-word;
}

.empty-sub {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* ===== 中栏：出题配置 ===== */
.center {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.center .nb-panel-head {
  flex: none;
}

.head-meta {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.center-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

.exam-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.exam-form :deep(.el-form-item__label) {
  padding-bottom: 6px;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--text-primary);
}

.field-hint {
  margin-left: 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  color: var(--text-tertiary);
}

/* 附件上传：设计稿虚线投放区 */
.upload-zone {
  width: 100%;
}

.upload-zone :deep(.el-upload) {
  display: block;
  width: 100%;
}

.upload-zone :deep(.el-upload-dragger) {
  width: 100%;
  padding: 18px 14px;
  background: var(--page-bg);
  border: 2px dashed #000;
  border-radius: var(--radius-card);
  box-shadow: 2px 2px 0 #000;
  transition: all 0.2s ease;
}

.upload-zone :deep(.el-upload-dragger:hover) {
  background: var(--primary-light);
  transform: translate(-2px, -2px);
  box-shadow: var(--shadow-card);
}

.upload-zone :deep(.el-upload-list) {
  margin-top: 8px;
}

.drop-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
}

.drop-icon {
  width: 44px;
  height: 44px;
  margin-bottom: 4px;
  display: grid;
  place-items: center;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  color: var(--primary);
}

.drop-title {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.drop-sub {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* 题型结构卡片 */
.type-card {
  padding: 12px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.type-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  margin-bottom: 12px;
  border-bottom: 2px solid #000;
}

.type-card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.type-card-title .el-icon {
  color: var(--primary);
}

.type-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.type-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  background: var(--page-bg);
  border: 2px solid #000;
  border-radius: var(--radius-input);
}

.type-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.type-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.type-tag {
  padding: 0 5px;
  background: #ffffff;
  border: 1px solid #000;
  border-radius: var(--radius-tag);
  font-size: 10px;
  color: var(--text-secondary);
}

.type-item-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.type-total {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.type-item :deep(.el-input-number) {
  width: 120px;
  flex: none;
}

.type-item :deep(.el-input-number .el-input__wrapper) {
  padding-left: 30px;
  padding-right: 30px;
  box-shadow: 0 0 0 2px #000 inset;
}

.type-item :deep(.el-input-number .el-input__inner) {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.type-item :deep(.el-input-number__decrease),
.type-item :deep(.el-input-number__increase) {
  width: 26px;
  background: #ffffff;
  color: #000000;
  border-color: #000;
  font-weight: 700;
}

.calc-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding: 8px 10px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.calc-strip b {
  color: var(--primary);
}

.calc-sep {
  color: rgba(0, 0, 0, 0.25);
}

.center-foot {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 16px;
  border-top: 2px solid #000;
  background: #ffffff;
}

.action-btn {
  height: 40px;
  padding: 0 18px;
}

/* ===== 右栏：实时预览 ===== */
.report {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
}

.preview-head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.preview-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.preview-title .el-icon {
  color: var(--primary);
}

.live-dot {
  flex: none;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--success);
  border: 1px solid #000;
}

.preview-card {
  flex: none;
}

.preview-card .nb-panel-head {
  padding: 8px 12px;
  background: var(--page-bg);
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}

.pv-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.pv-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.pv-title {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--text-primary);
  word-break: break-word;
}

.pv-text {
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  word-break: break-word;
}

.pv-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--divider);
}

.pv-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.pv-value {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

/* 题量结构条 */
.ratio-track {
  display: flex;
  height: 22px;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  overflow: hidden;
}

.ratio-seg {
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  color: #ffffff;
  border-right: 1px solid #000;
  overflow: hidden;
  white-space: nowrap;
}

.ratio-seg:last-child {
  border-right: none;
}

.seg-0 {
  background: var(--primary);
}

.seg-1 {
  background: #15803d;
}

.seg-2 {
  background: #7c3aed;
}

.seg-3 {
  background: #8A6400;
}

.legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.legend-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.swatch {
  flex: none;
  width: 10px;
  height: 10px;
  border: 1px solid #000;
  border-radius: 2px;
}

.legend-count {
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.basis-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  background: var(--page-bg);
  border: 2px solid #000;
  border-radius: var(--radius-input);
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}

.basis-state.on {
  background: var(--success-light);
  color: var(--success-text);
}

.pv-hint {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

/* ===== 弹窗 ===== */
.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: -16px -20px;
  padding: 12px 14px;
  background-image: var(--gradient-brand);
  border-bottom: 3px solid #000;
  border-radius: 5px 5px 0 0;
}

.dialog-head-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
}

.dialog-icon {
  flex: none;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  color: var(--primary);
}

.dialog-close {
  flex: none;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  padding: 0;
  background: #ffffff;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  color: #000000;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dialog-close:hover {
  background: var(--danger-light);
}

.dialog-text {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

/* ===== 窄屏兜底 ===== */
@media (max-width: 1080px) {
  .exam-page {
    overflow-y: auto;
  }

  .workspace-grid {
    grid-template-columns: minmax(0, 1fr);
    min-height: auto;
  }

  .rail,
  .report {
    overflow: visible;
    min-height: auto;
  }

  .center-body {
    overflow: visible;
  }
}
</style>
