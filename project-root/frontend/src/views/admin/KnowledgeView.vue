<template>
  <div class="nb-page knowledge-page">
    <!-- 页头：标题 + RAG 版本 + 主操作 -->
    <div class="nb-page-head page-head">
      <div class="head-left">
        <div class="head-title-row">
          <span class="head-accent"></span>
          <h1 class="nb-title">知识库管理</h1>
          <span class="version-chip nb-mono">RAG v2.4</span>
        </div>
        <p class="head-sub">国家/行业交通规程、工程安全红线与典型事故案例库，支持多模态向量化切片与高精检索</p>
      </div>
      <div class="head-actions">
        <el-button :icon="FolderOpened" @click="openCategoryDialog">分类管理</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="openUploadDialog">
          上传安全规范文档
        </el-button>
      </div>
    </div>

    <!-- 筛选面板 -->
    <div class="nb-panel filter-panel">
      <div class="filter-grid">
        <div class="field">
          <label class="field-label">文档类型</label>
          <el-select v-model="filters.type" placeholder="全部类型" clearable @change="onSearch">
            <el-option v-for="(label, value) in DOC_TYPES" :key="value" :label="label" :value="value" />
          </el-select>
        </div>
        <div class="field">
          <label class="field-label">索引状态</label>
          <el-select v-model="filters.status" placeholder="全部状态" clearable @change="onSearch">
            <el-option v-for="(label, value) in DOC_STATUS" :key="value" :label="label" :value="value" />
          </el-select>
        </div>
        <div class="field field-keyword">
          <label class="field-label">综合检索</label>
          <div class="search-row">
            <el-input
              v-model="filters.keyword"
              placeholder="按规范编号、标题或关键词搜索..."
              clearable
              @keyup.enter="onSearch"
              @clear="onSearch"
            >
              <template #append>
                <el-button :icon="Search" @click="onSearch" />
              </template>
            </el-input>
            <el-button class="reset-btn" @click="resetFilters">重置</el-button>
          </div>
        </div>
      </div>

      <div class="filter-foot">
        <div class="stat-chips">
          <span class="stat-chip">
            <span class="stat-label">匹配文档</span>
            <strong class="nb-mono">{{ total }} 篇</strong>
          </span>
          <span class="stat-chip">
            <span class="stat-label">当前页切片合计</span>
            <strong class="nb-mono accent">{{ visibleChunkTotal }} 条</strong>
          </span>
          <span class="stat-chip stat-chip--state">
            <span class="dot" :class="{ 'dot--pulse': pendingCount > 0 }"></span>
            {{ pendingCount > 0 ? `解析处理中 ${pendingCount} 篇` : '当前页无进行中解析任务' }}
          </span>
        </div>
        <span class="foot-page nb-mono">
          第 {{ page }} / {{ total ? Math.ceil(total / pageSize) : 1 }} 页
        </span>
      </div>
    </div>

    <!-- 文档表格面板 -->
    <div class="nb-panel table-panel">
      <div class="nb-panel-head">
        <span class="nb-panel-title">文档列表</span>
        <span class="panel-meta nb-mono">DOCUMENTS · {{ documents.length }} ROWS</span>
      </div>

      <el-table v-loading="loading" :data="documents" style="width: 100%">
        <el-table-column label="文档标题 / 分类" min-width="300">
          <template #default="{ row }">
            <div class="doc-cell">
              <span class="doc-icon" :class="{ 'doc-icon--danger': row.status === 'failed' }">
                <el-icon><Document /></el-icon>
              </span>
              <div class="doc-text">
                <span
                  class="doc-title"
                  :class="{ 'doc-title--danger': row.status === 'failed' }"
                  :title="row.title"
                >
                  {{ row.title }}
                </span>
                <span class="doc-meta nb-mono">
                  权威等级 {{ row.authority_level }}
                </span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <span class="nb-chip nb-chip--neutral">{{ DOC_TYPES[row.doc_type] || row.doc_type }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分类" min-width="120">
          <template #default="{ row }">
            <span class="cat-cell">
              <span class="cat-dot"></span>
              <span class="cat-name" :title="categoryName(row.category_id)">
                {{ categoryName(row.category_id) }}
              </span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="索引状态" width="160">
          <template #default="{ row }">
            <div class="status-cell">
              <span
                class="nb-chip"
                :class="
                  row.status === 'indexed'
                    ? 'nb-chip--normal'
                    : row.status === 'failed'
                      ? 'nb-chip--danger'
                      : 'nb-chip--info'
                "
              >
                <span v-if="row.status !== 'indexed' && row.status !== 'failed'" class="status-dot"></span>
                {{ DOC_STATUS[row.status] || row.status }}
              </span>
              <span
                v-if="row.status === 'failed' && row.error_message"
                class="status-error"
                :title="row.error_message"
              >
                {{ row.error_message }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="切片数" width="96" align="right">
          <template #default="{ row }">
            <span class="nb-mono cell-strong">{{ row.chunk_count }}</span>
            <span class="cell-unit"> 块</span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="96" align="right">
          <template #default="{ row }">
            <span class="nb-mono cell-dim">{{ formatSize(row.file_size) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">
            <span class="nb-mono cell-dim nowrap">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="104" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <button type="button" class="act-btn" title="刷新解析状态" @click="refreshStatus(row)">
                <el-icon><Refresh /></el-icon>
              </button>
              <button type="button" class="act-btn act-btn--danger" title="删除文档" @click="onDelete(row)">
                <el-icon><Delete /></el-icon>
              </button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <div class="nb-empty">暂无匹配文档，可调整筛选条件或上传新文档</div>
        </template>
      </el-table>

      <div class="table-foot">
        <div class="foot-info">
          <span>共 <strong class="nb-mono">{{ total }}</strong> 条文档</span>
          <span class="foot-divider">|</span>
          <span class="size-box">
            每页
            <el-select v-model="pageSize" class="page-size" size="small" @change="onSearch">
              <el-option :value="10" label="10 条" />
              <el-option :value="20" label="20 条" />
              <el-option :value="50" label="50 条" />
            </el-select>
          </span>
        </div>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="loadDocuments"
        />
      </div>
    </div>

    <!-- 上传文档对话框 -->
    <el-dialog
      v-model="uploadVisible"
      class="kb-upload"
      width="580px"
      :show-close="false"
      @closed="resetUploadForm"
    >
      <template #header>
        <div class="up-head">
          <div class="up-head-title">
            <el-icon><UploadFilled /></el-icon>
            <span>上传安全规范与知识文档</span>
          </div>
          <button type="button" class="up-close" aria-label="关闭" @click="uploadVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>

      <el-form
        ref="uploadFormRef"
        :model="uploadForm"
        :rules="uploadRules"
        label-position="top"
        class="up-form"
      >
        <el-form-item label="文档文件" required>
          <el-upload
            ref="uploadRef"
            drag
            action="#"
            class="upload-dragger"
            :auto-upload="false"
            :limit="1"
            accept=".pdf,.docx,.doc,.txt,.md"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :on-exceed="onUploadExceed"
          >
            <div class="drop-inner">
              <span class="drop-icon"><el-icon><UploadFilled /></el-icon></span>
              <p class="drop-title">点击选择文件，或将规范文档拖拽至此处</p>
              <p class="drop-hint">支持 PDF / Word / TXT / Markdown，单个文件不超过 50MB</p>
              <div class="drop-chips">
                <span>OCR 图文识别</span>
                <span>多级段落分块</span>
                <span>语义嵌入</span>
              </div>
            </div>
          </el-upload>
        </el-form-item>

        <el-form-item label="标题" prop="title">
          <el-input
            v-model="uploadForm.title"
            maxlength="200"
            placeholder="例如：《高速公路改扩建施工交通组织安全规范》"
          />
        </el-form-item>

        <div class="up-grid">
          <el-form-item label="文档类型" prop="doc_type">
            <el-select v-model="uploadForm.doc_type" placeholder="请选择" style="width: 100%">
              <el-option v-for="(label, value) in DOC_TYPES" :key="value" :label="label" :value="value" />
            </el-select>
          </el-form-item>
          <el-form-item label="分类" prop="category_id">
            <el-select v-model="uploadForm.category_id" clearable placeholder="可选" style="width: 100%">
              <el-option
                v-for="c in fixedCategoryOptions"
                :key="c.category_id"
                :label="c.name"
                :value="c.category_id"
              />
            </el-select>
          </el-form-item>
        </div>

        <div class="up-grid">
          <el-form-item label="标签" prop="tags">
            <el-select
              v-model="uploadForm.tags"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="输入后回车创建标签"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="权威等级" prop="authority_level">
            <el-radio-group v-model="uploadForm.authority_level">
              <el-radio value="A">A</el-radio>
              <el-radio value="B">B</el-radio>
              <el-radio value="C">C</el-radio>
            </el-radio-group>
          </el-form-item>
        </div>

        <div class="parse-note">
          <el-icon><Setting /></el-icon>
          <span>切片策略：服务端统一配置（智能层级断句 · 语义嵌入）</span>
        </div>
      </el-form>

      <template #footer>
        <div class="up-foot">
          <el-button @click="uploadVisible = false">取消</el-button>
          <el-button type="primary" :loading="uploading" :disabled="!uploadFile" @click="onUpload">
            开始解析与上传
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 分类管理对话框：固定三类，只读展示 -->
    <el-dialog v-model="categoryVisible" title="分类管理" width="480px">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
        <p>知识库分类为固定体系，仅支持：国家规定、地方规定、内部规定。</p>
      </el-alert>
      <el-table :data="fixedCategoryOptions" border>
        <el-table-column prop="name" label="分类名称" min-width="160" />
        <el-table-column label="说明" min-width="220">
          <template #default="{ row }">{{ FIXED_CATEGORY_DESC[row.name] || '' }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadFile,
  type UploadInstance,
} from 'element-plus'
import {
  Search,
  UploadFilled,
  FolderOpened,
  Document,
  Refresh,
  Delete,
  Close,
  Setting,
} from '@element-plus/icons-vue'
import { knowledgeApi, type KnowledgeDocument, type KnowledgeCategory } from '@/api'

const DOC_TYPES: Record<string, string> = {
  regulation: '法规',
  procedure: '规程',
  case: '案例',
  emergency: '应急',
  other: '其他',
}
const DOC_STATUS: Record<string, string> = {
  parsing: '解析中',
  chunking: '分块中',
  indexing: '索引中',
  indexed: '已索引',
  failed: '失败',
}
const PENDING_STATUS = ['parsing', 'chunking', 'indexing']
const MAX_FILE_SIZE = 50 * 1024 * 1024
const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.txt', '.md']

const loading = ref(false)
const documents = ref<KnowledgeDocument[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const filters = reactive({ type: '', status: '', keyword: '' })
const categories = ref<KnowledgeCategory[]>([])

// 固定分类体系：仅支持三类（后端 GET /categories 会自动补齐这三类）
const FIXED_CATEGORY_NAMES = ['国家规定', '地方规定', '内部规定'] as const
const FIXED_CATEGORY_DESC: Record<string, string> = {
  国家规定: '国家法律法规、部门规章及国家标准',
  地方规定: '四川省及地方性行业规定与标准',
  内部规定: '蜀道集团内部安全管理制度与规程',
}

// 固定分类下拉选项（从分类树中按名称匹配，保证提交的是真实 category_id）
const fixedCategoryOptions = computed(() => {
  const roots = categories.value.filter((c) => FIXED_CATEGORY_NAMES.includes(c.name as any))
  return FIXED_CATEGORY_NAMES
    .map((name) => roots.find((c) => c.name === name))
    .filter((c): c is KnowledgeCategory => !!c)
})

// 分类 id -> 名称映射
const categoryNameMap = computed(() => {
  const map: Record<number, string> = {}
  const walk = (list: KnowledgeCategory[]) => {
    for (const c of list) {
      map[c.category_id] = c.name
      if (c.children?.length) walk(c.children)
    }
  }
  walk(categories.value)
  return map
})

function categoryName(id: number | null) {
  return id != null ? categoryNameMap.value[id] || '-' : '-'
}

function statusTagType(status: string) {
  if (status === 'indexed') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

function formatSize(size: number) {
  if (!size) return '-'
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`
  return `${(size / 1024).toFixed(1)} KB`
}

function formatTime(value: string) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

// 当前页切片合计、进行中解析数量：仅用于页内统计展示
const visibleChunkTotal = computed(() =>
  documents.value.reduce((sum, d) => sum + (d.chunk_count || 0), 0),
)
const pendingCount = computed(() => documents.value.filter((d) => PENDING_STATUS.includes(d.status)).length)

function resetFilters() {
  filters.type = ''
  filters.status = ''
  filters.keyword = ''
  onSearch()
}

async function loadDocuments() {
  loading.value = true
  try {
    const res = await knowledgeApi.documents({
      page: page.value,
      page_size: pageSize.value,
      type: filters.type || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword.trim() || undefined,
    })
    documents.value = res?.items || []
    total.value = res?.total || 0
  } catch (e: any) {
    ElMessage.warning('文档列表加载失败，请稍后重试')
  } finally {
    loading.value = false
    syncPolling()
  }
}

async function loadCategories() {
  try {
    const res = await knowledgeApi.categories()
    categories.value = res || []
  } catch {
    // 分类加载失败不阻断文档列表
  }
}

function onSearch() {
  page.value = 1
  loadDocuments()
}

// ===== 解析状态轮询：存在进行中文档时每 5s 刷新 =====
let pollTimer: number | null = null

function syncPolling() {
  const pending = documents.value.some((d) => PENDING_STATUS.includes(d.status))
  if (pending && pollTimer === null) {
    pollTimer = window.setInterval(pollPendingStatus, 5000)
  } else if (!pending && pollTimer !== null) {
    stopPolling()
  }
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollPendingStatus() {
  const pendingRows = documents.value.filter((d) => PENDING_STATUS.includes(d.status))
  if (!pendingRows.length) {
    stopPolling()
    return
  }
  await Promise.all(
    pendingRows.map(async (row) => {
      try {
        const res = await knowledgeApi.documentStatus(row.document_id)
        if (res) {
          row.status = res.status
          row.chunk_count = res.chunk_count
          row.error_message = res.error_message
        }
      } catch {
        // 单行查询失败忽略，下轮重试
      }
    }),
  )
  syncPolling()
}

async function refreshStatus(row: KnowledgeDocument) {
  try {
    const res = await knowledgeApi.documentStatus(row.document_id)
    if (res) {
      row.status = res.status
      row.chunk_count = res.chunk_count
      row.error_message = res.error_message
      ElMessage.success(`当前状态：${DOC_STATUS[res.status] || res.status}`)
    }
    syncPolling()
  } catch {
    // 拦截器已提示
  }
}

// ===== 删除文档 =====
async function onDelete(row: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm('删除后将同时清除向量与分块数据，不可恢复', '警告', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await knowledgeApi.deleteDocument(row.document_id)
    ElMessage.success('文档已删除')
    if (documents.value.length === 1 && page.value > 1) page.value -= 1
    loadDocuments()
  } catch {
    // 拦截器已提示
  }
}

// ===== 上传文档 =====
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadRef = ref<UploadInstance>()
const uploadFormRef = ref<FormInstance>()
const uploadFile = ref<File | null>(null)

const uploadForm = reactive({
  title: '',
  doc_type: '',
  category_id: undefined as number | undefined,
  tags: [] as string[],
  authority_level: 'B',
})

const uploadRules: FormRules = {
  title: [{ required: true, message: '请输入文档标题', trigger: 'blur' }],
  doc_type: [{ required: true, message: '请选择文档类型', trigger: 'change' }],
}

function openUploadDialog() {
  uploadVisible.value = true
}

function resetUploadForm() {
  uploadForm.title = ''
  uploadForm.doc_type = ''
  uploadForm.category_id = undefined
  uploadForm.tags = []
  uploadForm.authority_level = 'B'
  uploadFile.value = null
  uploadRef.value?.clearFiles()
}

function onFileRemove() {
  uploadFile.value = null
}

function onUploadExceed() {
  ElMessage.warning('一次仅支持上传一个文件，请先移除已选文件')
}

// 选择文件时校验扩展名与大小（el-upload auto-upload 关闭，统一在提交时上传）
function onFileChange(file: UploadFile) {
  if (file.status !== 'ready') return
  const raw = file.raw
  if (!raw) return
  const ext = `.${(raw.name.split('.').pop() || '').toLowerCase()}`
  if (!ALLOWED_EXTS.includes(ext)) {
    ElMessage.error('仅支持 PDF / Word(.docx,.doc) / TXT / Markdown 文件')
    uploadRef.value?.clearFiles()
    uploadFile.value = null
    return
  }
  if (raw.size > MAX_FILE_SIZE) {
    ElMessage.error('文件大小不能超过 50MB')
    uploadRef.value?.clearFiles()
    uploadFile.value = null
    return
  }
  uploadFile.value = raw
  // 一旦选择文件，标题自动识别为文件名（不含后缀）
  uploadForm.title = raw.name.replace(/\.[^.]+$/, '')
}

async function onUpload() {
  if (!uploadFile.value) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  await uploadFormRef.value?.validate()
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', uploadFile.value)
    fd.append('title', uploadForm.title.trim())
    fd.append('doc_type', uploadForm.doc_type)
    if (uploadForm.category_id != null) fd.append('category_id', String(uploadForm.category_id))
    if (uploadForm.tags.length) fd.append('tags', uploadForm.tags.join(','))
    fd.append('authority_level', uploadForm.authority_level)
    const res = await knowledgeApi.uploadDocument(fd)
    ElMessage.success(res?.message || '上传成功，正在解析处理')
    uploadVisible.value = false
    page.value = 1
    loadDocuments()
  } catch {
    // 拦截器已提示
  } finally {
    uploading.value = false
  }
}

// ===== 分类管理（固定三类，只读展示） =====
const categoryVisible = ref(false)

function openCategoryDialog() {
  categoryVisible.value = true
  loadCategories()
}

onMounted(() => {
  loadDocuments()
  loadCategories()
})

onUnmounted(stopPolling)
</script>

<style scoped>
.knowledge-page {
  align-items: stretch;
}

/* ---------- 页头 ---------- */
.head-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.head-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.head-accent {
  width: 6px;
  height: 24px;
  flex: none;
  border: 2px solid #000;
  border-radius: 2px;
  background: var(--gradient-brand);
}
.version-chip {
  padding: 1px 8px;
  border: 1.5px solid #000;
  border-radius: var(--radius-tag);
  background: #EAEEFD;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.head-sub {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.head-actions {
  display: flex;
  gap: 10px;
  flex: none;
}

/* ---------- 筛选面板 ---------- */
.filter-panel {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.filter-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 3fr) minmax(0, 6fr);
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.field :deep(.el-select),
.field :deep(.el-input) {
  width: 100%;
}
.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-strong);
}
.field-label::before {
  content: "";
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: #000;
}
.search-row {
  display: flex;
  gap: 8px;
  min-width: 0;
}
.search-row :deep(.el-input) {
  flex: 1;
  min-width: 0;
}
.search-row :deep(.el-input-group__append) {
  background: #ffffff;
  border: none;
  border-left: 2px solid #000;
  border-radius: 0 var(--radius-input) var(--radius-input) 0;
  box-shadow: none;
  padding: 0;
}
.search-row :deep(.el-input-group__append .el-button) {
  border: none;
  border-radius: 0;
  box-shadow: none;
  margin: 0;
  height: 100%;
}
.reset-btn {
  flex: none;
  background: #EAEEFD;
  font-family: var(--font-mono);
  font-size: 12px;
}
.filter-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 10px;
  border-top: 1px solid var(--color-divider);
}
.stat-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.stat-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border: 1.5px solid #000;
  border-radius: var(--radius-tag);
  background: #f7f9fb;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
}
.stat-chip strong {
  font-size: 12px;
  color: var(--color-text-strong);
}
.stat-chip strong.accent {
  color: var(--accent);
}
.stat-chip--state {
  background: var(--success-light);
  color: var(--success-text);
}
.dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: var(--success-text);
}
.dot--pulse {
  animation: kb-pulse 1.5s ease-out infinite;
}
@keyframes kb-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(21, 128, 61, 0.45);
  }
  70% {
    box-shadow: 0 0 0 5px rgba(21, 128, 61, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(21, 128, 61, 0);
  }
}
.foot-page {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

/* ---------- 表格面板 ---------- */
.table-panel {
  display: flex;
  flex-direction: column;
}
.panel-meta {
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
}
.table-panel :deep(.el-table) {
  --el-table-border-color: var(--color-divider);
  --el-table-header-bg-color: #f7f9fb;
  --el-table-row-hover-bg-color: #eaeefd;
  border-radius: 0;
}
.table-panel :deep(.el-table th.el-table__cell) {
  padding: 10px 12px;
}
.table-panel :deep(.el-table td.el-table__cell) {
  padding: 12px;
}
.table-panel :deep(.el-table__inner-wrapper::before) {
  display: none;
}
.doc-cell {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}
.doc-icon {
  width: 28px;
  height: 28px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #000;
  border-radius: var(--radius-input);
  background: var(--primary-light);
  color: var(--primary);
  font-size: 15px;
}
.doc-icon--danger {
  background: var(--danger-light);
  color: var(--danger-text);
}
.doc-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.doc-title {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--color-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.doc-title--danger {
  color: var(--danger-text);
}
.doc-meta {
  font-size: 10.5px;
  color: var(--text-tertiary);
}
.cat-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-strong);
}
.cat-dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: var(--primary);
}
.cat-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}
.status-dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: currentColor;
}
.status-error {
  max-width: 140px;
  font-size: 10px;
  font-weight: 500;
  color: var(--danger-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-strong {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-strong);
}
.cell-unit {
  font-size: 11px;
  color: var(--text-tertiary);
}
.cell-dim {
  font-size: 11px;
  color: var(--text-tertiary);
}
.nowrap {
  white-space: nowrap;
}
.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.act-btn {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #000;
  border-radius: var(--radius-input);
  background: #ffffff;
  box-shadow: 2px 2px 0 #000;
  color: var(--color-text-strong);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.act-btn:hover {
  background: var(--primary-light);
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #000;
}
.act-btn:active {
  transform: translate(1px, 1px);
  box-shadow: none;
}
.act-btn--danger {
  color: var(--danger-text);
}
.act-btn--danger:hover {
  background: var(--danger-light);
}

/* ---------- 表格底部：分页 ---------- */
.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  border-top: 2px solid #000;
  background: #f7f9fb;
}
.foot-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}
.foot-divider {
  color: #E1E8ED;
}
.size-box {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.page-size {
  width: 92px;
}
.page-size :deep(.el-select__wrapper) {
  min-height: 26px;
  box-shadow: 0 0 0 1.5px #000 inset;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
}
.table-foot :deep(.el-pagination) {
  gap: 4px;
}
.table-foot :deep(.el-pagination .el-pager li),
.table-foot :deep(.el-pagination button) {
  min-width: 28px;
  height: 28px;
  padding: 0 4px;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #ffffff;
  box-shadow: 2px 2px 0 #000;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}
.table-foot :deep(.el-pagination .el-pager li.is-active) {
  background-image: var(--gradient-brand);
  color: #ffffff;
}
.table-foot :deep(.el-pagination button:disabled) {
  background: #EAEEFD;
  color: #9aa4ae;
  box-shadow: none;
  cursor: not-allowed;
}
.table-foot :deep(.el-pagination .el-pager li:hover),
.table-foot :deep(.el-pagination button:not(:disabled):hover) {
  background: #eaeefd;
  color: var(--accent);
}

/* ---------- 上传对话框 ---------- */
:deep(.kb-upload.el-dialog) {
  padding: 0;
  border: 3px solid #000;
  border-radius: var(--radius-dialog);
  box-shadow: var(--shadow-dialog);
  overflow: hidden;
}
:deep(.kb-upload .el-dialog__header) {
  margin: 0;
  padding: 0;
  border-bottom: 0;
}
:deep(.kb-upload .el-dialog__body) {
  padding: 0;
}
:deep(.kb-upload .el-dialog__footer) {
  padding: 0;
  border-top: 0;
}
.up-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--gradient-brand);
  border-bottom: 3px solid #000;
  color: #ffffff;
}
.up-head-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
}
.up-close {
  width: 28px;
  height: 28px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #ffffff;
  color: #000;
  cursor: pointer;
  transition: all 0.15s ease;
}
.up-close:hover {
  background: var(--danger-light);
  color: var(--danger-text);
  transform: translate(1px, 1px);
}
.up-form {
  padding: 16px 18px;
}
:deep(.up-form .el-form-item) {
  margin-bottom: 12px;
}
:deep(.up-form .el-form-item__label) {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-text-strong);
  padding-bottom: 4px;
  line-height: 1.4;
}
.up-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 14px;
}
.upload-dragger :deep(.el-upload) {
  width: 100%;
}
.upload-dragger :deep(.el-upload-dragger) {
  width: 100%;
  padding: 18px 16px;
  background: #F7F9FB;
  border: 2.5px dashed #000;
  border-radius: var(--radius-card);
  transition: all 0.15s ease;
}
.upload-dragger :deep(.el-upload-dragger:hover) {
  background: #eaeefd;
  border-color: #000;
}
.upload-dragger :deep(.el-upload-list__item) {
  border: 1.5px solid #000;
  border-radius: var(--radius-input);
  margin-top: 8px;
  font-size: 12px;
}
.drop-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  line-height: 1.5;
}
.drop-icon {
  width: 44px;
  height: 44px;
  margin-bottom: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #000;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 2px 2px 0 #000;
  color: var(--primary);
  font-size: 22px;
}
.drop-title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-strong);
}
.drop-hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-tertiary);
}
.drop-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 6px;
}
.drop-chips span {
  padding: 1px 6px;
  border: 1px solid #000;
  border-radius: 3px;
  background: #ffffff;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-strong);
}
.parse-note {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid #000;
  border-radius: var(--radius-input);
  background: #f7f9fb;
  font-size: 11px;
  color: var(--text-secondary);
}
.up-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 18px;
  background: #EAEEFD;
  border-top: 2.5px solid #000;
}

/* ---------- 窄屏 ---------- */
@media (max-width: 900px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }
  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
@media (max-width: 520px) {
  .up-grid {
    grid-template-columns: 1fr;
  }
}
</style>
