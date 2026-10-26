<template>
  <div class="nb-page">
    <!-- 页头：黑色竖条标题 + 主操作 -->
    <div class="nb-page-head page-head">
      <div class="head-left">
        <span class="head-accent"></span>
        <div class="head-text">
          <h1 class="nb-title">AI 模型配置</h1>
          <p class="head-sub">集中管理工程视觉识别模型、LLM 对话引擎及 RAG 向量检索模型</p>
        </div>
      </div>
      <div class="head-actions">
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增模型</el-button>
      </div>
    </div>

    <!-- 筛选面板 -->
    <div class="nb-panel filter-panel">
      <div class="filter-grid">
        <div class="filter-field filter-field--type">
          <label class="filter-label">类型</label>
          <el-select v-model="filterForm.type" placeholder="全部类型 (ALL)">
            <el-option label="全部类型 (ALL)" value="" />
            <el-option label="chat (对话大模型)" value="chat" />
            <el-option label="vision (视觉识别)" value="vision" />
            <el-option label="embedding (向量表示)" value="embedding" />
            <el-option label="rerank (重排序引擎)" value="rerank" />
          </el-select>
        </div>
        <div class="filter-field filter-field--status">
          <label class="filter-label">状态</label>
          <el-select v-model="filterForm.status" placeholder="全部状态">
            <el-option label="全部状态" value="" />
            <el-option label="已启用" value="active" />
            <el-option label="已停用" value="disabled" />
          </el-select>
        </div>
        <div class="filter-field filter-field--keyword">
          <el-input
            v-model="filterForm.keyword"
            :prefix-icon="Search"
            placeholder="搜索模型名称、供应商或端点"
            clearable
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
        </div>
        <div class="filter-actions">
          <button type="button" class="filter-btn filter-btn--dark" @click="applyFilters">
            <el-icon><Filter /></el-icon>
            <span>筛选</span>
          </button>
          <button type="button" class="filter-btn" @click="resetFilters">
            <el-icon><RefreshLeft /></el-icon>
            <span>重置</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 扩展模型配置表格 -->
    <div class="nb-panel table-panel">
      <div class="nb-panel-head">
        <span class="nb-panel-title">扩展模型配置</span>
        <div class="panel-head-actions">
          <span class="panel-meta nb-mono">MODEL MATRIX · {{ filteredModels.length }} ROWS</span>
          <el-button size="small" @click="openEmbeddingDialog()">配置 Embedding</el-button>
          <el-button size="small" @click="openRerankDialog()">配置 CrossEncoder</el-button>
        </div>
      </div>

      <el-table :data="pagedModels" class="model-table" style="width: 100%">
        <template #empty>
          <div class="nb-empty">暂无匹配的模型配置</div>
        </template>
        <el-table-column label="模型名称" min-width="200">
          <template #default="{ row }">
            <div class="model-cell">
              <span class="model-icon" :class="`type-icon--${row.model_type}`">
                <el-icon><component :is="typeIcon(row.model_type)" /></el-icon>
              </span>
              <span class="model-name nb-mono" :title="row.model_name">
                {{ row.model_name || '（未命名）' }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <span class="nb-chip type-chip" :class="`type-chip--${row.model_type}`">
              {{ row.model_type }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="供应商 / 引擎架构" min-width="150">
          <template #default="{ row }">
            <div class="provider-cell">
              <span class="provider-name" :class="{ 'is-empty': !row.provider }">
                {{ sourceLabel(row.provider) }}
              </span>
              <span class="provider-meta nb-mono">
                置信度 {{ row.confidence ?? '-' }} · 温度 {{ row.temperature ?? '-' }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="服务接入端点" min-width="220">
          <template #default="{ row }">
            <span class="endpoint-cell nb-mono" :title="row.api_base">{{ row.api_base || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <span
              class="nb-chip status-chip"
              :class="row.is_active ? 'status-chip--on' : 'status-chip--off'"
            >
              <span class="status-dot"></span>
              {{ row.is_active ? '已启用' : '已停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="150">
          <template #default="{ row }">
            <span class="updated-cell nb-mono">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作控制" width="200" align="right">
          <template #default="{ row }">
            <div class="row-actions">
              <!-- 「测试」仅对 chat 模型开放，保持单条问答测试逻辑 -->
              <button
                v-if="row.model_type === 'chat'"
                type="button"
                class="op-test"
                @click="openTest(row)"
              >
                <el-icon><MagicStick /></el-icon>
                <span>测试</span>
              </button>
              <button type="button" class="op-link" @click="openEdit(row)">编辑</button>
              <button type="button" class="op-link op-link--danger" @click="onDelete(row.id)">删除</button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页条 -->
      <div class="table-foot">
        <div class="foot-stat">
          <span class="foot-square"></span>
          <span>
            显示第 <strong class="nb-mono">{{ rangeStart }}</strong> 至
            <strong class="nb-mono">{{ rangeEnd }}</strong> 项，总计
            <strong class="nb-mono foot-total">{{ filteredModels.length }}</strong> 个模型
          </span>
          <span class="foot-dim nb-mono">｜ 每页 {{ pageSize }} 条</span>
        </div>
        <el-pagination
          class="table-pager"
          small
          :current-page="currentPage"
          :page-size="pageSize"
          :total="filteredModels.length"
          :pager-count="5"
          layout="prev, pager, next"
          @current-change="page = $event"
        />
      </div>
    </div>

    <!-- 当前系统实际生效的模型（来自 .env / 本地部署目录） -->
    <div class="nb-panel runtime-panel">
      <div class="nb-panel-head">
        <span class="nb-panel-title">当前系统生效模型</span>
        <span class="panel-meta nb-mono">RUNTIME · .ENV / LOCAL</span>
      </div>
      <div class="runtime-tip">
        <el-icon><InfoFilled /></el-icon>
        <span>读取自 .env 与本地模型目录，修改后需重启后端</span>
      </div>
      <el-table :data="runtimeModels" size="small" class="runtime-table" style="width: 100%">
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <span class="nb-chip type-chip" :class="`type-chip--${row.model_type}`">
              {{ row.model_type }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="模型名称" min-width="180">
          <template #default="{ row }">
            <span class="runtime-name nb-mono">{{ row.model_name || '（未配置）' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="地址/目录" min-width="220">
          <template #default="{ row }">
            <span class="endpoint-cell nb-mono" :title="row.api_base">{{ row.api_base || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="API Key" width="150">
          <template #default="{ row }">
            <span class="runtime-key nb-mono">{{ row.api_key || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <span
              class="nb-chip status-chip"
              :class="row.configured ? 'status-chip--on' : 'status-chip--danger'"
            >
              <span class="status-dot"></span>
              {{ row.configured ? '已配置' : '未配置' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="说明" min-width="180" />
      </el-table>
    </div>

    <!-- 模型单条问答测试：验证 chat 模型可用性，无会话管理与点赞反馈 -->
    <el-dialog
      v-model="testVisible"
      class="test-dialog"
      width="min(760px, 94vw)"
      top="6vh"
      :show-close="false"
      @closed="resetTest"
    >
      <template #header>
        <div class="test-head">
          <div class="test-head-text">
            <div class="test-head-row">
              <el-icon class="test-head-icon"><Cpu /></el-icon>
              <h2 class="test-head-title">模型问答测试</h2>
              <span class="test-sandbox nb-mono">INTERACTIVE SANDBOX</span>
            </div>
            <p class="test-head-sub">
              被测模型：<span class="test-model nb-mono">{{ testModel?.model_name || '—' }}</span>
              <span class="test-sep">｜</span>
              检索固定使用系统生效的 Embedding / CrossEncoder
            </p>
          </div>
          <button type="button" class="test-close" aria-label="关闭" @click="testVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>

      <div class="test-thread">
        <div v-if="!messages.length" class="nb-empty test-empty">
          <el-icon class="test-empty-icon"><ChatLineSquare /></el-icon>
          <p class="test-empty-title">暂无对话</p>
          <p class="test-empty-sub">输入问题后可直接查看该模型基于知识库的回答</p>
        </div>
        <div v-for="(m, i) in messages" :key="i" class="test-msg" :class="m.role">
          <template v-if="m.role === 'user'">
            <span class="test-msg-meta nb-mono">管理员测试员 · 单轮提问</span>
            <div class="test-bubble">{{ m.content }}</div>
          </template>
          <template v-else>
            <div class="test-ai-avatar">AI</div>
            <div class="test-ai-body">
              <div class="test-bubble test-bubble--ai">
                <div class="test-md" v-html="renderTestMd(m.content, i === messages.length - 1)"></div>
              </div>
              <div
                v-if="m.sources?.length && !isStreamingLast(i)"
                class="test-sources"
              >
                <el-icon><Collection /></el-icon>
                <span>引用 <strong class="nb-mono">{{ m.sources.length }}</strong> 条依据</span>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="test-foot">
        <div class="test-foot-bar">
          <span class="test-foot-tip nb-mono">轻量单轮测试沙箱 · 无会话记忆留存</span>
          <button
            type="button"
            class="test-clear"
            :disabled="streaming || !messages.length"
            @click="clearTestChat"
          >
            <el-icon><Delete /></el-icon>
            <span>清空对话</span>
          </button>
        </div>
        <div class="test-input">
          <el-input
            v-model="testInput"
            type="textarea"
            :rows="2"
            resize="none"
            :disabled="streaming"
            placeholder="输入测试问题，Ctrl+Enter 发送"
            @keydown.ctrl.enter.prevent="sendTest"
          />
          <el-button
            type="primary"
            class="test-send"
            :icon="Promotion"
            :loading="streaming"
            @click="sendTest"
          >
            发送
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- chat / vision 模型弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模型' : '新增模型'" width="500px">
      <el-form ref="formRef" :model="form" label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="form.model_type" style="width: 100%">
            <el-option label="chat" value="chat" />
            <el-option label="vision" value="vision" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.model_name" placeholder="如 ERNIE-4.0-Turbo" />
        </el-form-item>
        <el-form-item label="API地址">
          <el-input v-model="form.api_base" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" />
        </el-form-item>
        <el-form-item label="置信度">
          <el-input-number v-model="form.confidence" :min="0" :max="1" :step="0.05" />
        </el-form-item>
        <el-form-item label="温度">
          <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="最大Token">
          <el-input-number v-model="form.max_tokens" :min="100" :step="100" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- embedding 模型独立弹窗：本地部署 / HuggingFace 下载 -->
    <el-dialog v-model="embeddingVisible" :title="embeddingEditingId ? '编辑 Embedding 模型' : '配置 Embedding 模型'" width="520px">
      <el-form ref="embedFormRef" :model="embedForm" label-width="100px">
        <el-form-item label="模型来源">
          <el-radio-group v-model="embedForm.source">
            <el-radio value="local">本地部署</el-radio>
            <el-radio value="huggingface">联入 HuggingFace 下载</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="embedForm.source === 'local'">
          <el-form-item label="模型名称">
            <el-input v-model="embedForm.model_name" placeholder="如 bge-large" />
          </el-form-item>
          <el-form-item label="本地目录">
            <el-input v-model="embedForm.path" placeholder="如 models/bge-large">
              <template #prepend>路径</template>
            </el-input>
            <div class="form-tip">填写服务器上的本地模型目录（sentence-transformers 格式）</div>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="模型 ID">
            <el-input v-model="embedForm.model_name" placeholder="如 BAAI/bge-large-zh-v1.5" />
          </el-form-item>
          <el-form-item label="镜像地址">
            <el-input v-model="embedForm.path" placeholder="如 https://hf-mirror.com（可选）">
              <template #prepend>URL</template>
            </el-input>
            <div class="form-tip">留空则直连 huggingface.co；国内网络建议填镜像地址</div>
          </el-form-item>
        </template>

        <el-form-item label="启用">
          <el-switch v-model="embedForm.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="embeddingVisible = false">取消</el-button>
        <el-button type="primary" @click="onSaveEmbedding">保存</el-button>
      </template>
    </el-dialog>

    <!-- CrossEncoder（rerank）重排模型独立弹窗：本地部署 / HuggingFace 下载 -->
    <el-dialog v-model="rerankVisible" :title="rerankEditingId ? '编辑 CrossEncoder 重排模型' : '配置 CrossEncoder 重排模型'" width="520px">
      <el-form ref="rerankFormRef" :model="rerankForm" label-width="100px">
        <el-form-item label="模型来源">
          <el-radio-group v-model="rerankForm.source">
            <el-radio value="local">本地部署</el-radio>
            <el-radio value="huggingface">联入 HuggingFace 下载</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="rerankForm.source === 'local'">
          <el-form-item label="模型名称">
            <el-input v-model="rerankForm.model_name" placeholder="如 bge-base-rerank" />
          </el-form-item>
          <el-form-item label="本地目录">
            <el-input v-model="rerankForm.path" placeholder="如 models/bge-base-rerank">
              <template #prepend>路径</template>
            </el-input>
            <div class="form-tip">填写服务器上的 CrossEncoder 模型目录（sentence-transformers CrossEncoder 格式）</div>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="模型 ID">
            <el-input v-model="rerankForm.model_name" placeholder="如 BAAI/bge-reranker-base" />
          </el-form-item>
          <el-form-item label="镜像地址">
            <el-input v-model="rerankForm.path" placeholder="如 https://hf-mirror.com（可选）">
              <template #prepend>URL</template>
            </el-input>
            <div class="form-tip">留空则直连 huggingface.co；国内网络建议填镜像地址</div>
          </el-form-item>
        </template>

        <el-form-item label="启用">
          <el-switch v-model="rerankForm.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rerankVisible = false">取消</el-button>
        <el-button type="primary" @click="onSaveRerank">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  Filter,
  RefreshLeft,
  Close,
  Cpu,
  ChatDotRound,
  View,
  Connection,
  Sort,
  MagicStick,
  ChatLineSquare,
  Collection,
  Delete,
  Promotion,
  InfoFilled,
} from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import http from '@/api/http'
import { adminApi } from '@/api'

const models = ref<any[]>([])
// 当前系统实际生效的模型（.env / 本地目录）
const runtimeModels = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ model_type: 'chat', model_name: '', api_base: '', api_key: '', confidence: 0.7, temperature: 0.3, max_tokens: 2048, is_active: 0 })

// ---------- 列表筛选 / 分页（纯前端展示） ----------
const filterForm = ref({ type: '', status: '', keyword: '' })
const appliedFilters = ref({ type: '', status: '', keyword: '' })
const page = ref(1)
const pageSize = 6

const filteredModels = computed(() =>
  models.value.filter((row) => {
    if (appliedFilters.value.type && row.model_type !== appliedFilters.value.type) return false
    if (appliedFilters.value.status === 'active' && !row.is_active) return false
    if (appliedFilters.value.status === 'disabled' && row.is_active) return false
    const keyword = appliedFilters.value.keyword.trim().toLowerCase()
    if (keyword) {
      const haystack = [
        row.model_name,
        row.model_type,
        row.api_base,
        row.provider,
        sourceLabel(row.provider),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (!haystack.includes(keyword)) return false
    }
    return true
  }),
)

const pageCount = computed(() => Math.max(1, Math.ceil(filteredModels.value.length / pageSize)))
const currentPage = computed(() => Math.min(page.value, pageCount.value))
const pagedModels = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredModels.value.slice(start, start + pageSize)
})
const rangeStart = computed(() =>
  filteredModels.value.length ? (currentPage.value - 1) * pageSize + 1 : 0,
)
const rangeEnd = computed(() => Math.min(currentPage.value * pageSize, filteredModels.value.length))

function applyFilters() {
  appliedFilters.value = { ...filterForm.value }
  page.value = 1
}

function resetFilters() {
  filterForm.value = { type: '', status: '', keyword: '' }
  appliedFilters.value = { type: '', status: '', keyword: '' }
  page.value = 1
}

// embedding 独立弹窗状态
const embeddingVisible = ref(false)
const embeddingEditingId = ref<number | null>(null)
const embedForm = ref({ source: 'local', model_name: '', path: '', is_active: 0 })

// CrossEncoder（rerank）独立弹窗状态
const rerankVisible = ref(false)
const rerankEditingId = ref<number | null>(null)
const rerankForm = ref({ source: 'local', model_name: '', path: '', is_active: 0 })

// ---------- 模型单条问答测试 ----------
const testVisible = ref(false)
const testModel = ref<any>(null)
const messages = ref<{ role: 'user' | 'assistant'; content: string; sources?: any[] }[]>([])
const testInput = ref('')
const streaming = ref(false)
let testController: AbortController | null = null

marked.setOptions({ breaks: true, gfm: true })

// AI 回复按 markdown 渲染；LLM 输出属外部内容，须经 DOMPurify 消毒
function renderTestMd(text: string, isLast: boolean) {
  const html = DOMPurify.sanitize(marked.parse(text) as string)
  const cursor = isLast && streaming.value ? '<span class="test-cursor">▌</span>' : ''
  return html + cursor
}

function isStreamingLast(index: number) {
  return streaming.value && index === messages.value.length - 1
}

function openTest(row: any) {
  testModel.value = row
  messages.value = []
  testInput.value = ''
  testVisible.value = true
}

function resetTest() {
  testController?.abort()
  testController = null
  streaming.value = false
  messages.value = []
  testInput.value = ''
  testModel.value = null
}

// 仅清空沙箱内的展示内容，不触碰模型与 SSE 状态
function clearTestChat() {
  if (streaming.value) return
  messages.value = []
  testInput.value = ''
}

async function sendTest() {
  const question = testInput.value.trim()
  if (!question || streaming.value || !testModel.value) return
  messages.value.push({ role: 'user', content: question })
  messages.value.push({ role: 'assistant', content: '' })
  testInput.value = ''
  streaming.value = true
  const reply = messages.value[messages.value.length - 1]
  const { promise, controller } = adminApi.chatTest(testModel.value.id, question, {
    onToken: (token) => { reply.content += token },
    onSources: (sources) => { reply.sources = sources },
    onError: (msg) => { if (!reply.content) reply.content = `测试失败：${msg}` },
  })
  testController = controller
  try { await promise } finally { streaming.value = false }
}

// 来源列展示：provider 仅在本地模型行有意义
function sourceLabel(provider: string) {
  if (provider === 'local') return '本地部署'
  if (provider === 'huggingface') return 'HuggingFace'
  return '-'
}

// 类型图标：chat / vision / embedding / rerank 各用语义色
const TYPE_ICONS: Record<string, any> = {
  chat: ChatDotRound,
  vision: View,
  embedding: Connection,
  rerank: Sort,
}

function typeIcon(type: string) {
  return TYPE_ICONS[type] || Cpu
}

function formatTime(value: any) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 16)
}

async function loadModels() {
  try {
    // http 拦截器已解包为 data，res 即列表本身
    const res = await http.get('/admin/models')
    models.value = Array.isArray(res) ? res : []
  } catch { ElMessage.warning('加载失败') }
}

async function loadRuntimeModels() {
  try {
    const res = await http.get('/admin/models/runtime')
    runtimeModels.value = Array.isArray(res) ? res : []
  } catch { /* 静默失败，不打扰主列表 */ }
}

function openDialog() {
  editingId.value = null
  form.value = { model_type: 'chat', model_name: '', api_base: '', api_key: '', confidence: 0.7, temperature: 0.3, max_tokens: 2048, is_active: 0 }
  dialogVisible.value = true
}

// 编辑入口：embedding / rerank 行走各自独立弹窗，其余走通用弹窗
function openEdit(row: any) {
  if (row.model_type === 'embedding') {
    openEmbeddingDialog(row)
  } else if (row.model_type === 'rerank') {
    openRerankDialog(row)
  } else {
    editingId.value = row.id
    form.value = { ...row }
    dialogVisible.value = true
  }
}

async function onSave() {
  const fd = new FormData()
  for (const [k, v] of Object.entries(form.value)) fd.append(k, String(v ?? ''))
  try {
    if (editingId.value) {
      await http.put(`/admin/models/${editingId.value}`, fd)
    } else {
      await http.post('/admin/models', fd)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadModels()
  } catch { ElMessage.warning('保存失败') }
}

function openEmbeddingDialog(row?: any) {
  if (row) {
    embeddingEditingId.value = row.id
    embedForm.value = {
      source: row.provider === 'huggingface' ? 'huggingface' : 'local',
      model_name: row.model_name || '',
      path: row.api_base || '',
      is_active: row.is_active ?? 0,
    }
  } else {
    embeddingEditingId.value = null
    embedForm.value = { source: 'local', model_name: '', path: '', is_active: 0 }
  }
  embeddingVisible.value = true
}

async function onSaveEmbedding() {
  if (!embedForm.value.model_name.trim()) {
    ElMessage.warning('请填写模型名称')
    return
  }
  const fd = new FormData()
  fd.append('model_type', 'embedding')
  fd.append('provider', embedForm.value.source)
  fd.append('model_name', embedForm.value.model_name)
  fd.append('api_base', embedForm.value.path)
  fd.append('is_active', String(embedForm.value.is_active))
  try {
    if (embeddingEditingId.value) {
      await http.put(`/admin/models/${embeddingEditingId.value}`, fd)
    } else {
      await http.post('/admin/models', fd)
    }
    ElMessage.success('Embedding 模型配置已保存')
    embeddingVisible.value = false
    loadModels()
  } catch { ElMessage.warning('保存失败') }
}

function openRerankDialog(row?: any) {
  if (row) {
    rerankEditingId.value = row.id
    rerankForm.value = {
      source: row.provider === 'huggingface' ? 'huggingface' : 'local',
      model_name: row.model_name || '',
      path: row.api_base || '',
      is_active: row.is_active ?? 0,
    }
  } else {
    rerankEditingId.value = null
    rerankForm.value = { source: 'local', model_name: '', path: '', is_active: 0 }
  }
  rerankVisible.value = true
}

async function onSaveRerank() {
  if (!rerankForm.value.model_name.trim()) {
    ElMessage.warning('请填写模型名称')
    return
  }
  const fd = new FormData()
  fd.append('model_type', 'rerank')
  fd.append('provider', rerankForm.value.source)
  fd.append('model_name', rerankForm.value.model_name)
  fd.append('api_base', rerankForm.value.path)
  fd.append('is_active', String(rerankForm.value.is_active))
  try {
    if (rerankEditingId.value) {
      await http.put(`/admin/models/${rerankEditingId.value}`, fd)
    } else {
      await http.post('/admin/models', fd)
    }
    ElMessage.success('CrossEncoder 重排模型配置已保存')
    rerankVisible.value = false
    loadModels()
  } catch { ElMessage.warning('保存失败') }
}

async function onDelete(id: number) {
  try { await ElMessageBox.confirm('确定删除？', '确认', { type: 'warning' }) } catch { return }
  try {
    await http.delete(`/admin/models/${id}`)
    ElMessage.success('已删除')
    loadModels()
  } catch { ElMessage.warning('删除失败') }
}

onMounted(() => {
  loadRuntimeModels()
  loadModels()
})
</script>

<style scoped>
/* ---------- 页头 ---------- */
.page-head {
  align-items: flex-start;
  flex-wrap: wrap;
}
.head-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.head-accent {
  flex: none;
  width: 6px;
  height: 52px;
  background: #000;
  margin-top: 2px;
}
.head-sub {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-text-muted);
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.head-actions :deep(.el-button) {
  height: 40px;
  padding: 0 20px;
  font-size: 13px;
}

/* ---------- 面板头部附加内容 ---------- */
.panel-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--color-text-muted);
  white-space: nowrap;
}
.panel-head-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.panel-head-actions :deep(.el-button) {
  height: 28px;
  padding: 0 10px;
  font-size: 11px;
  box-shadow: 2px 2px 0 #000;
}

/* ---------- 筛选面板 ---------- */
.filter-panel {
  padding: 16px;
}
.filter-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}
.filter-field {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.filter-field--type {
  flex: 0 1 250px;
}
.filter-field--status {
  flex: 0 1 190px;
}
.filter-field--keyword {
  flex: 1 1 260px;
}
.filter-label {
  flex: none;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #000;
  text-transform: uppercase;
}
.filter-field :deep(.el-select) {
  flex: 1;
  min-width: 0;
}
.filter-field :deep(.el-select__wrapper) {
  min-height: 34px;
}
.filter-field :deep(.el-input__wrapper) {
  min-height: 34px;
}
.filter-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.filter-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 34px;
  padding: 0 16px;
  border: 2px solid #000;
  border-radius: 4px;
  background: #fff;
  color: #000;
  font-family: var(--font);
  font-size: 12px;
  font-weight: 700;
  box-shadow: 2px 2px 0 #000;
  cursor: pointer;
  transition: all 0.2s ease;
}
.filter-btn:hover {
  transform: translate(-2px, -2px);
  box-shadow: 4px 4px 0 #000;
}
.filter-btn:active {
  transform: translate(1px, 1px);
  box-shadow: none;
}
.filter-btn--dark {
  background: #000;
  color: #fff;
  box-shadow: 2px 2px 0 #657786;
}
.filter-btn--dark:hover {
  box-shadow: 4px 4px 0 #657786;
}

/* ---------- 模型表格 ---------- */
.table-panel {
  display: flex;
  flex-direction: column;
}
.model-table {
  --el-table-row-hover-bg-color: #EAEEFD;
  --el-table-header-bg-color: #ffffff;
  --el-table-header-text-color: #000000;
}
.model-table :deep(th.el-table__cell) {
  border-bottom: 2px solid #000;
}
.model-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}
.model-table :deep(td.el-table__cell) {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-divider);
}
.model-table :deep(.el-table__empty-block) {
  min-height: 160px;
}
.model-cell {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}
.model-icon {
  flex: none;
  display: inline-flex;
  margin-top: 1px;
  font-size: 15px;
  color: var(--color-text-muted);
}
.type-icon--chat {
  color: var(--accent);
}
.type-icon--vision {
  color: var(--primary);
}
.type-icon--embedding,
.type-icon--rerank {
  color: var(--text-tertiary);
}
.model-name {
  min-width: 0;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  color: #000;
  word-break: break-word;
}
.provider-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.provider-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-strong);
}
.provider-name.is-empty {
  color: var(--color-text-muted);
  font-weight: 500;
}
.provider-meta {
  font-size: 10px;
  color: var(--color-text-muted);
}
.endpoint-cell {
  display: block;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: #3F4A54;
}
.updated-cell {
  font-size: 11px;
  color: var(--color-text-muted);
}

.type-chip {
  justify-content: center;
  min-width: 68px;
  border-width: 2px;
  box-shadow: 1.5px 1.5px 0 #000;
}
.type-chip--chat {
  background: var(--accent);
  color: #ffffff;
}
.type-chip--vision {
  background: var(--primary);
  color: #ffffff;
}
.type-chip--embedding,
.type-chip--rerank {
  background: #E1E8ED;
  color: #000000;
}

.status-chip {
  justify-content: center;
  border-width: 2px;
}
.status-chip--on {
  background: var(--success-light);
  color: var(--success-text);
}
.status-chip--off {
  background: #E1E8ED;
  color: #3F4A54;
}
.status-chip--danger {
  background: var(--danger-light);
  color: var(--danger-text);
}
.status-dot {
  flex: none;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}
.status-chip--off .status-dot {
  background: #657786;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}
.op-test {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border: 2px solid #000;
  border-radius: 4px;
  background: #EAEEFD;
  color: #2F54EB;
  font-family: var(--font);
  font-size: 11px;
  font-weight: 800;
  box-shadow: 2px 2px 0 #000;
  cursor: pointer;
  transition: all 0.2s ease;
}
.op-test:hover {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #000;
}
.op-test:active {
  transform: translate(1px, 1px);
  box-shadow: none;
}
.op-link {
  padding: 2px 4px;
  border: 0;
  background: none;
  color: #000;
  font-family: var(--font);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.op-link:hover {
  text-decoration: underline;
}
.op-link--danger {
  color: var(--danger-text);
}

/* ---------- 分页条 ---------- */
.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border-top: 2px solid #000;
  background: var(--color-bg);
}
.foot-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #000;
}
.foot-square {
  flex: none;
  width: 8px;
  height: 8px;
  background: #000;
}
.foot-total {
  text-decoration: underline;
}
.foot-dim {
  margin-left: 2px;
  font-size: 10px;
  font-weight: 500;
  color: var(--color-text-muted);
}
.table-pager {
  --el-pagination-button-color: #000;
}
.table-pager :deep(.el-pager li),
.table-pager :deep(button) {
  min-width: 26px;
  height: 26px;
  margin: 0 2px;
  border: 2px solid #000;
  border-radius: 4px;
  background: #fff;
  box-shadow: 2px 2px 0 #000;
  font-family: var(--font-mono);
  font-weight: 700;
}
.table-pager :deep(.el-pager li.is-active) {
  background: #000;
  background-image: none;
  color: #fff;
}
.table-pager :deep(button:disabled) {
  opacity: 0.35;
  box-shadow: none;
}

/* ---------- 系统生效模型 ---------- */
.runtime-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--color-divider);
  background: var(--color-bg);
  font-size: 11px;
  color: var(--color-text-muted);
}
.runtime-tip :deep(.el-icon) {
  color: #000;
}
.runtime-table {
  --el-table-header-bg-color: #ffffff;
  --el-table-header-text-color: #000000;
}
.runtime-table :deep(td.el-table__cell) {
  padding: 8px 0;
  border-bottom: 1px solid var(--color-divider);
}
.runtime-name {
  font-size: 11px;
  font-weight: 700;
}
.runtime-key {
  font-size: 11px;
  color: var(--color-text-muted);
}

/* ---------- 模型问答测试弹窗 ---------- */
:deep(.test-dialog) {
  padding: 0;
  overflow: hidden;
  border: 3px solid #000;
  border-radius: var(--radius-dialog);
  box-shadow: var(--shadow-dialog);
  background: #fff;
}
:deep(.test-dialog .el-dialog__header) {
  margin: 0;
  padding: 0;
  border-bottom: 0;
}
:deep(.test-dialog .el-dialog__body) {
  padding: 0;
}
.test-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 2px solid #000;
  background: #fff;
}
.test-head-text {
  min-width: 0;
}
.test-head-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.test-head-icon {
  font-size: 20px;
  color: var(--accent);
}
.test-head-title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: #000;
}
.test-sandbox {
  padding: 2px 8px;
  border: 1.5px solid #000;
  border-radius: 4px;
  background: #EAEEFD;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #000;
}
.test-head-sub {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-muted);
}
.test-model {
  font-weight: 700;
  color: #000;
}
.test-sep {
  margin: 0 4px;
  color: var(--el-text-color-placeholder);
}
.test-close {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 2px solid #000;
  border-radius: 50%;
  background: #fff;
  color: #000;
  box-shadow: 2px 2px 0 #000;
  cursor: pointer;
  transition: all 0.2s ease;
}
.test-close:hover {
  background: #FEF2F2;
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #000;
}
.test-close:active {
  transform: translate(1px, 1px);
  box-shadow: none;
}

.test-thread {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 340px;
  overflow-y: auto;
  padding: 16px;
  background: #f7f9fb;
}
.test-empty {
  flex: 1;
  padding: 0 16px;
}
.test-empty-icon {
  font-size: 30px;
  color: #000;
}
.test-empty-title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #000;
}
.test-empty-sub {
  margin: 0;
  font-size: 11px;
}
.test-msg {
  display: flex;
  max-width: 85%;
}
.test-msg.user {
  flex-direction: column;
  align-items: flex-end;
  align-self: flex-end;
  gap: 4px;
}
.test-msg.assistant {
  align-items: flex-start;
  align-self: flex-start;
  gap: 10px;
  max-width: 92%;
}
.test-msg-meta {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-muted);
}
.test-bubble {
  padding: 12px 14px;
  border: 2px solid #000;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-word;
}
.test-msg.user .test-bubble {
  background-image: var(--gradient-brand);
  color: #fff;
  box-shadow: 3px 3px 0 #000;
}
.test-ai-avatar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 2px solid #000;
  border-radius: 50%;
  background: #000;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  box-shadow: 1px 1px 0 #657786;
}
.test-ai-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.test-bubble--ai {
  background: #fff;
  color: var(--color-text-strong);
  box-shadow: 3px 3px 0 #000;
}
.test-sources {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 6px;
  border-top: 1px solid var(--color-divider);
  font-size: 11px;
  font-weight: 700;
  color: var(--info-text);
}

/* AI 回复 Markdown */
.test-md :deep(p) {
  margin: 0 0 6px;
}
.test-md :deep(p:last-child) {
  margin-bottom: 0;
}
.test-md :deep(strong) {
  font-weight: 800;
  color: #000;
}
.test-md :deep(ul),
.test-md :deep(ol) {
  margin: 0 0 6px;
  padding-left: 18px;
}
.test-md :deep(li) {
  margin: 2px 0;
}
.test-md :deep(h1),
.test-md :deep(h2),
.test-md :deep(h3),
.test-md :deep(h4) {
  margin: 6px 0;
  font-size: 13px;
}
.test-md :deep(code) {
  padding: 0 3px;
  border: 1px solid #E1E8ED;
  border-radius: 3px;
  background: #F7F9FB;
  font-family: var(--font-mono);
  font-size: 11px;
}
.test-md :deep(pre) {
  margin: 6px 0;
  padding: 8px;
  overflow-x: auto;
  border: 1px solid #000;
  border-radius: 4px;
  background: #F7F9FB;
}
.test-md :deep(pre code) {
  padding: 0;
  border: 0;
  background: transparent;
}
.test-md :deep(table) {
  margin: 6px 0;
  border-collapse: collapse;
  font-size: 11px;
}
.test-md :deep(th),
.test-md :deep(td) {
  padding: 4px 6px;
  border: 1px solid #000;
}
.test-md :deep(th) {
  background: #F7F9FB;
}
.test-md :deep(blockquote) {
  margin: 6px 0;
  padding-left: 8px;
  border-left: 3px solid #000;
  color: var(--text-secondary);
}
.test-md :deep(a) {
  color: var(--primary);
}
.test-md :deep(.test-cursor) {
  display: inline-block;
  width: 6px;
  height: 13px;
  margin-left: 2px;
  overflow: hidden;
  background: #000;
  color: transparent;
  vertical-align: -2px;
  animation: test-cursor-blink 1s step-end infinite;
}
@keyframes test-cursor-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.test-foot {
  padding: 12px 16px;
  border-top: 2px solid #000;
  background: #fff;
}
.test-foot-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.test-foot-tip {
  font-size: 11px;
  color: var(--color-text-muted);
}
.test-clear {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 0;
  border: 0;
  background: none;
  color: #000;
  font-family: var(--font);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: color 0.2s ease;
}
.test-clear:hover:not(:disabled) {
  color: var(--danger-text);
}
.test-clear:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.test-input {
  display: flex;
  align-items: stretch;
  gap: 10px;
}
.test-input :deep(.el-textarea) {
  flex: 1;
}
.test-send {
  min-width: 84px;
  padding: 0 16px;
  font-weight: 800;
  align-self: stretch;
  height: auto;
}

/* ---------- 表单提示 ---------- */
.form-tip {
  font-size: 12px;
  color: #657786;
  line-height: 1.4;
  margin-top: 4px;
}

@media (max-width: 900px) {
  .filter-field--type,
  .filter-field--status {
    flex: 1 1 180px;
  }
  .filter-actions {
    margin-left: 0;
  }
  .panel-meta {
    display: none;
  }
}
</style>
