<template>
  <div class="nb-page ai-page">
    <!-- 左栏：历史会话（新建对话 / 批量管理 / 会话条目） -->
    <aside class="nb-panel history-panel">
      <div class="history-head">
        <div class="history-head-row">
          <div class="history-title-wrap">
            <el-checkbox
              :model-value="isAllSelected"
              :indeterminate="isIndeterminate"
              @change="onToggleSelectAll"
            >
              <span class="select-all-text">全选</span>
            </el-checkbox>
            <span class="history-title">历史会话</span>
          </div>
          <el-button
            v-if="selectedIds.length"
            class="batch-del"
            type="danger"
            size="small"
            :icon="Delete"
            @click="onBatchDelete"
          >
            删除({{ selectedIds.length }})
          </el-button>
        </div>
        <button class="new-chat-btn" type="button" @click="onNewChat">
          <el-icon><Plus /></el-icon>
          <span>新建对话</span>
        </button>
      </div>

      <div class="history-list">
        <div class="list-label nb-mono">
          <span>会话列表</span>
          <span>{{ historyList.length }} 条</span>
        </div>
        <div v-if="!historyList.length" class="nb-empty">
          <span>暂无会话</span>
          <span class="empty-hint nb-mono">NO SESSION</span>
        </div>
        <div
          v-for="item in historyList"
          :key="item.id"
          class="session-item"
          :class="{ active: item.id === activeHistoryId }"
          @click="onSelectSession(item)"
        >
          <el-checkbox
            :model-value="selectedIds.includes(item.id)"
            @change="(v: any) => onToggleItem(item.id, v)"
            @click.stop
          />
          <div class="session-main">
            <div class="session-title">
              <span v-if="item.id === activeHistoryId" class="live-dot"></span>
              <span class="ellipsis">{{ item.title }}</span>
            </div>
            <div class="session-meta">
              <span class="nb-mono">#{{ item.id.slice(0, 8) }}</span>
              <el-button
                class="item-delete"
                size="small"
                text
                type="danger"
                :icon="Delete"
                title="删除会话"
                @click.stop="onDeleteItem(item)"
              />
            </div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 中栏：对话流 + 底部输入区 -->
    <section class="nb-panel chat-panel">
      <div ref="scrollRef" class="chat-scroll">
        <div class="chat-inner">
          <div v-if="!messages.length" class="nb-empty chat-empty">
            <span class="chat-empty-title">开始一次安全问答</span>
            <span class="chat-empty-hint">
              输入公路、隧道、桥梁施工安全问题，回答将引用规范库并给出溯源依据
            </span>
            <span class="empty-hint nb-mono">READY / ASK ANYTHING</span>
          </div>
          <div v-for="(msg, i) in messages" :key="i" class="msg" :class="msg.role">
            <div class="msg-avatar" :class="msg.role">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
            <div class="bubble-wrap">
              <div v-if="msg.role === 'assistant'" class="msg-head">
                <span class="ai-name">蜀道工程安全大脑</span>
                <span v-if="msg.citations?.length" class="nb-chip nb-chip--info">
                  {{ (msg.citations || []).reduce((n, g) => n + g.items.length, 0) }} 条依据
                </span>
                <span v-else class="nb-chip nb-chip--neutral">AI 生成</span>
                <span
                  v-if="streaming && i === messages.length - 1"
                  class="stream-chip nb-mono"
                >STREAMING</span>
              </div>
              <div class="bubble">
                <template v-if="msg.role === 'assistant'">
                  <!-- 整段一次性渲染 markdown，引用标记在渲染后高亮，避免切分破坏结构 -->
                  <div class="md" v-html="renderMarkdown(msg.content)"></div>
                  <!-- 流式输出中：光标跟随最后一条 AI 消息逐字打印 -->
                  <span v-if="streaming && i === messages.length - 1" class="cursor">▌</span>
                  <div v-if="msg.citations?.length" class="citations">
                    <div class="citations-head">
                      <span class="citations-label">本次回复引用规范溯源</span>
                      <span class="citations-total nb-mono">
                        {{ (msg.citations || []).reduce((n, g) => n + g.items.length, 0) }} 条
                      </span>
                    </div>
                    <div v-for="group in msg.citations" :key="group.level" class="citation-group">
                      <button class="citation-row" type="button" @click="group.open = !group.open">
                        <span class="nb-chip nb-chip--info">{{ group.level }}</span>
                        <span class="citation-count">
                          <span class="nb-mono">{{ group.items.length }} 条</span>
                          <el-icon :class="{ open: group.open }"><ArrowDown /></el-icon>
                        </span>
                      </button>
                      <div v-show="group.open" class="citation-list">
                        <div v-for="item in group.items" :key="item.name" class="citation-item">
                          <a :href="item.uri" target="_blank" rel="noopener">{{ item.name }}</a>
                          <p v-if="item.clause" class="citation-clause nb-mono">{{ item.clause }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="msg.messageId" class="feedback-bar">
                    <button
                      class="act-btn"
                      type="button"
                      :class="{ active: feedbackMap[msg.messageId] === 'like' }"
                      @click="onLike(msg)"
                    >
                      有用
                    </button>
                    <button
                      class="act-btn"
                      type="button"
                      :class="{ active: feedbackMap[msg.messageId] === 'dislike' }"
                      @click="onDislike(msg)"
                    >
                      反馈原因
                    </button>
                    <button class="act-btn" type="button" @click="copyContent(msg.content)">
                      复制回答
                    </button>
                  </div>
                </template>
                <template v-else>{{ msg.content }}</template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-inputbar">
        <div class="input-shell">
          <div class="input-main">
            <textarea
              v-model="input"
              rows="2"
              placeholder="请输入你的公路/隧道/桥梁工程安全生产问题，支持引用规范库……"
              @keydown.enter.exact.prevent="onSend"
            ></textarea>
            <div class="input-foot">
              <span class="input-hint nb-mono">Shift + Enter 换行</span>
              <span class="input-count nb-mono">{{ input.length }} 字</span>
            </div>
          </div>
          <button
            class="send-btn"
            type="button"
            title="发送"
            :disabled="!input.trim() || streaming"
            @click="onSend"
          >
            <el-icon v-if="!streaming"><Promotion /></el-icon>
            <el-icon v-else class="loading-icon"><Loading /></el-icon>
          </button>
        </div>
        <p class="disclaimer">
          回答由 AI 生成，仅供参考；涉及安全红线与验收指标，请以现行规范原文及项目安全技术交底为准。
        </p>
      </div>
    </section>

    <!-- 右栏：引用依据与实时溯源 -->
    <aside class="nb-panel ref-panel">
      <div class="nb-panel-head ref-head">
        <div class="nb-panel-title">规范依据与溯源</div>
        <span class="nb-chip nb-chip--neutral nb-mono">REF {{ latestCitationTotal }}</span>
      </div>
      <div class="ref-body">
        <div class="ref-stats">
          <div class="stat">
            <span class="stat-num nb-mono">{{ messages.length }}</span>
            <span class="stat-label">会话消息</span>
          </div>
          <div class="stat">
            <span class="stat-num nb-mono">{{ latestCitationTotal }}</span>
            <span class="stat-label">引用依据</span>
          </div>
          <div class="stat">
            <span class="stat-num nb-mono">{{ historyList.length }}</span>
            <span class="stat-label">历史会话</span>
          </div>
        </div>
        <div class="ref-section-label nb-mono">
          <span>当前回复引用</span>
          <span>/ SOURCES</span>
        </div>
        <div v-if="!latestCitationGroups.length" class="nb-empty">
          <span>暂无引用依据</span>
          <span class="empty-hint nb-mono">ASK TO LOAD REFS</span>
        </div>
        <div v-for="group in latestCitationGroups" :key="group.level" class="ref-card">
          <div class="ref-card-head">
            <span class="nb-chip nb-chip--info">{{ group.level }}</span>
            <span class="ref-count nb-mono">{{ group.items.length }} 条</span>
          </div>
          <div v-for="item in group.items" :key="item.name" class="ref-item">
            <a class="ref-name" :href="item.uri" target="_blank" rel="noopener">{{ item.name }}</a>
            <p v-if="item.clause" class="ref-clause nb-mono">{{ item.clause }}</p>
          </div>
        </div>
      </div>
    </aside>

    <!-- 点踩原因反馈对话框 -->
    <el-dialog v-model="dislikeVisible" title="反馈原因" width="420px" class="feedback-dialog">
      <div class="dislike-tip">请选择本次回答不满意的原因（至少一项）：</div>
      <el-checkbox-group v-model="dislikeReasons" class="reason-group">
        <el-checkbox v-for="r in DISLIKE_REASONS" :key="r.value" :value="r.value">
          {{ r.label }}
        </el-checkbox>
      </el-checkbox-group>
      <el-input
        v-model="dislikeComment"
        type="textarea"
        :rows="2"
        maxlength="200"
        show-word-limit
        placeholder="其他补充说明（可选）"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="dislikeVisible = false">取消</el-button>
        <el-button type="primary" :loading="feedbackSubmitting" @click="submitDislike">提交反馈</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { Plus, ArrowDown, Promotion, Loading, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { aiApi } from '@/api'

// assistant 回复按 markdown 渲染；LLM 输出属外部内容，须经 DOMPurify 消毒后再 v-html
marked.setOptions({ breaks: true, gfm: true })
function renderMarkdown(text: string): string {
  const html = marked.parse(text) as string
  const safe = DOMPurify.sanitize(html)
  // 引用标记在 markdown 渲染完成后统一包成高亮 span（先切分文本会打断标题/列表结构）
  return safe.replace(/【([^】]+)】/g, '<span class="cited">$1</span>')
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: CitationGroup[]
  // 已持久化的 assistant 消息才有 message_id（SSE 临时消息无）
  messageId?: string
}

interface CitationGroup {
  level: string
  open: boolean
  items: { name: string; clause: string; uri: string }[]
}

const input = ref('')
const streaming = ref(false)
const scrollRef = ref<HTMLElement>()
const activeHistoryId = ref('')
const currentSessionId = ref<string | null>(null)
const historyList = ref<{ id: string; title: string }[]>([])
const selectedIds = ref<string[]>([])
const messages = ref<Message[]>([])
let activeController: AbortController | null = null

// ===== 打字机流式输出：SSE token 先入队，定时器逐字渲染 =====
// 后端 token 粒度是 chunk（可能整句），直接追加无逐字效果；
// 这里缓冲后每帧出队 1 个字符，队列积压时自动提速避免落后生成进度。
let typeQueue = ''
let typeTimer: ReturnType<typeof setInterval> | null = null
let typingMsg: Message | null = null

function startTypeWriter() {
  if (typeTimer) return
  typeTimer = setInterval(() => {
    if (!typeQueue || !typingMsg) {
      stopTypeWriter()
      return
    }
    const step = Math.max(1, Math.floor(typeQueue.length / 40))
    typingMsg.content += typeQueue.slice(0, step)
    typeQueue = typeQueue.slice(step)
    // 流式期间即时跟随底部（不走 smooth，避免频繁重定向抖动）
    nextTick(() => {
      if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    })
  }, 16)
}

function stopTypeWriter(flush = false) {
  // flush：结束时一次性输出剩余字符，保证答案完整
  if (flush && typingMsg && typeQueue) typingMsg.content += typeQueue
  typeQueue = ''
  if (typeTimer) {
    clearInterval(typeTimer)
    typeTimer = null
  }
}

// ===== 消息点赞/点踩（B6） =====
const DISLIKE_REASONS = [
  { value: 'inaccurate', label: '回答不准确' },
  { value: 'incomplete', label: '回答不完整' },
  { value: 'misunderstanding', label: '理解错误' },
  { value: 'off_topic', label: '与安全无关' },
  { value: 'other', label: '其他' },
]

// 本地记录已评价状态：messageId -> 'like' | 'dislike'
const feedbackMap = reactive<Record<string, 'like' | 'dislike'>>({})
const dislikeVisible = ref(false)
const dislikeReasons = ref<string[]>([])
const dislikeComment = ref('')
const dislikeTargetId = ref('')
const feedbackSubmitting = ref(false)

function resetFeedback() {
  Object.keys(feedbackMap).forEach((key) => delete feedbackMap[key])
}

async function onLike(msg: Message) {
  const id = msg.messageId as string
  const current = feedbackMap[id]
  try {
    if (current === 'like') {
      // 再次点击点赞 -> 取消评价
      await aiApi.cancelFeedback(id)
      delete feedbackMap[id]
      ElMessage.info('已取消评价')
      return
    }
    if (current === 'dislike') {
      // 由踩切换为赞：先取消旧评价，避免重复评价（40012）
      await aiApi.cancelFeedback(id)
    }
    await aiApi.feedback(id, { rating: 'like', reasons: [] })
    feedbackMap[id] = 'like'
    ElMessage.success('感谢您的反馈')
  } catch {
    // 重复评价（40012）等错误由 http 拦截器统一 ElMessage.error 提示
  }
}

function onDislike(msg: Message) {
  const id = msg.messageId as string
  if (feedbackMap[id] === 'dislike') {
    // 再次点击点踩 -> 取消评价
    cancelFeedback(id)
    return
  }
  dislikeTargetId.value = id
  dislikeReasons.value = []
  dislikeComment.value = ''
  dislikeVisible.value = true
}

async function cancelFeedback(id: string) {
  try {
    await aiApi.cancelFeedback(id)
    delete feedbackMap[id]
    ElMessage.info('已取消评价')
  } catch {
    // 拦截器已提示
  }
}

async function submitDislike() {
  if (!dislikeReasons.value.length) {
    ElMessage.warning('请至少选择一个反馈原因')
    return
  }
  feedbackSubmitting.value = true
  try {
    await aiApi.feedback(dislikeTargetId.value, {
      rating: 'dislike',
      reasons: [...dislikeReasons.value],
      comment: dislikeComment.value.trim() || undefined,
    })
    feedbackMap[dislikeTargetId.value] = 'dislike'
    dislikeVisible.value = false
    ElMessage.success('感谢您的反馈')
  } catch {
    // 重复评价（40012）等错误由 http 拦截器统一提示
  } finally {
    feedbackSubmitting.value = false
  }
}

// 复制回答正文（纯前端剪贴板操作，不走接口）
async function copyContent(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本复制')
  }
}

// 右栏溯源面板：取最近一条带引用的 AI 回复（纯展示）
const latestCitationGroups = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role === 'assistant' && msg.citations?.length) return msg.citations
  }
  return [] as CitationGroup[]
})
const latestCitationTotal = computed(() =>
  latestCitationGroups.value.reduce((n, group) => n + group.items.length, 0),
)

const isAllSelected = computed(
  () => historyList.value.length > 0 && selectedIds.value.length === historyList.value.length,
)
const isIndeterminate = computed(
  () => selectedIds.value.length > 0 && selectedIds.value.length < historyList.value.length,
)

function groupSources(sources: any[]): CitationGroup[] {
  const map: Record<string, CitationGroup> = {}
  for (const s of sources) {
    const level = s.standard_level || '其他规范'
    if (!map[level]) map[level] = { level, open: false, items: [] }
    map[level].items.push({
      name: s.title || '未命名规范',
      clause: s.locator || '',
      uri: s.source_uri || '#',
    })
  }
  return Object.values(map)
}

async function loadSessions() {
  try {
    const res = await aiApi.sessions({ page: 1, page_size: 50 })
    const items = res?.items || []
    historyList.value = items.map((s: any) => ({ id: s.session_id, title: s.title || '新对话' }))
    // 清理已不存在的选中项
    const validIds = new Set(historyList.value.map((i) => i.id))
    selectedIds.value = selectedIds.value.filter((id) => validIds.has(id))
  } catch (e: any) {
    ElMessage.warning('会话列表加载失败，请稍后重试')
  }
}

function onToggleSelectAll(value: any) {
  selectedIds.value = value ? historyList.value.map((i) => i.id) : []
}

function onToggleItem(id: string, value: any) {
  if (value) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter((i) => i !== id)
  }
}

async function onDeleteItem(item: { id: string; title: string }) {
  try {
    await ElMessageBox.confirm(`确认删除会话「${item.title}」？`, '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await aiApi.deleteSession(item.id)
    historyList.value = historyList.value.filter((i) => i.id !== item.id)
    selectedIds.value = selectedIds.value.filter((i) => i !== item.id)
    if (item.id === currentSessionId.value) {
      currentSessionId.value = null
      activeHistoryId.value = ''
      messages.value = []
    }
    ElMessage.success('已删除')
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.warning('删除失败，请稍后重试')
    }
  }
}

async function onBatchDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedIds.value.length} 个会话？`, '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await aiApi.batchDeleteSessions(selectedIds.value)
    historyList.value = historyList.value.filter((i) => !selectedIds.value.includes(i.id))
    if (selectedIds.value.includes(currentSessionId.value || '')) {
      currentSessionId.value = null
      activeHistoryId.value = ''
      messages.value = []
    }
    selectedIds.value = []
    ElMessage.success('已删除')
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.warning('删除失败，请稍后重试')
    }
  }
}

async function onSelectSession(item: { id: string; title: string }) {
  activeHistoryId.value = item.id
  currentSessionId.value = item.id
  try {
    const res = await aiApi.messages(item.id)
    const msgs = res?.messages || []
    resetFeedback()
    messages.value = msgs.map((m: any) => ({
      role: m.role,
      content: m.content,
      citations: m.sources?.length ? groupSources(m.sources) : undefined,
      messageId: m.message_id,
    }))
    // 历史会话：直接定位到最新一条消息
    scrollToBottom(true)
  } catch (e: any) {
    ElMessage.warning('消息加载失败，请稍后重试')
  }
}

async function onNewChat() {
  activeController?.abort()
  // 中断生成：丢弃未输出的字符，停掉打字机
  stopTypeWriter()
  typingMsg = null
  streaming.value = false
  messages.value = []
  resetFeedback()
  currentSessionId.value = null
  activeHistoryId.value = ''
  try {
    const res = await aiApi.createSession()
    currentSessionId.value = res.session_id
    loadSessions()
  } catch (e: any) {
    ElMessage.warning('创建会话失败')
  }
}

async function onSend() {
  const text = input.value.trim()
  if (!text || streaming.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  streaming.value = true
  await nextTick()
  scrollToBottom()

  const assistantMsg: Message = { role: 'assistant', content: '', citations: [] }
  messages.value.push(assistantMsg)
  typingMsg = assistantMsg

  const { promise, controller } = aiApi.chat(
    { question: text, session_id: currentSessionId.value },
    {
      onToken: (token) => {
        // token 入队，由打字机定时器逐字渲染到气泡
        typeQueue += token
        startTypeWriter()
      },
      onSources: (sources) => {
        assistantMsg.citations = groupSources(sources)
      },
      onDone: (meta) => {
        if (meta.session_id) {
          currentSessionId.value = meta.session_id
          loadSessions()
        }
        // 持久化完成后记录 message_id，展示点赞/点踩入口
        if (meta.message_id) assistantMsg.messageId = meta.message_id
      },
      onError: (message) => {
        ElMessage.warning(message)
      },
    },
  )
  activeController = controller
  try {
    await promise
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      ElMessage.warning('生成失败，请稍后重试')
    }
  } finally {
    // 生成结束：一次性补齐剩余字符，停掉打字机
    stopTypeWriter(true)
    typingMsg = null
    streaming.value = false
    scrollToBottom()
  }
}

function scrollToBottom(instant = false) {
  nextTick(() => {
    // instant：加载历史记录时直接跳到底部，避免 smooth 大跨度滚动中断落不到底
    scrollRef.value?.scrollTo({
      top: scrollRef.value.scrollHeight,
      behavior: instant ? 'auto' : 'smooth',
    })
  })
}

onMounted(loadSessions)
// 组件卸载：清理打字机定时器，避免内存泄漏
onUnmounted(() => stopTypeWriter())
</script>

<style scoped>
/* ===== 页面骨架：左 240 / 中自适应 / 右 360，三栏各自滚动 ===== */
.ai-page {
  display: flex;
  flex-direction: row;
  gap: 16px;
  height: 100%;
  padding: 16px;
  overflow: hidden;
  background: var(--color-bg);
}

.ai-page > .nb-panel {
  min-height: 0;
}

/* ===== 左栏：历史会话 ===== */
.history-panel {
  width: 240px;
  flex: none;
  display: flex;
  flex-direction: column;
}

.history-head {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-bottom: 2px solid #000;
  background: #f7f9fb;
}

.history-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}

.history-title-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.history-head :deep(.el-checkbox) {
  margin-right: 0;
  height: auto;
}

.history-head :deep(.el-checkbox__label) {
  padding-left: 6px;
}

.select-all-text {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-text-muted);
}

.history-title {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--color-text-strong);
  white-space: nowrap;
}

.batch-del {
  flex: none;
  height: 26px;
  padding: 0 6px;
}

.batch-del :deep(span) {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 9px 12px;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  background-image: var(--gradient-brand);
  color: #fff;
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  box-shadow: 3px 3px 0 #000;
  cursor: pointer;
  transition: all 0.2s ease;
}

.new-chat-btn:hover {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0 #000;
}

.new-chat-btn:active {
  transform: translate(2px, 2px);
  box-shadow: none;
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

.list-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 2px 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.session-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background-color: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.session-item:hover {
  transform: translate(-2px, -2px);
  box-shadow: 4px 4px 0 #000;
}

.session-item.active {
  background-image: linear-gradient(90deg, rgba(47, 84, 235, 0.14), rgba(124, 58, 237, 0.14));
  box-shadow: 3px 3px 0 #000;
}

.session-item :deep(.el-checkbox) {
  flex: none;
  height: auto;
  margin: 2px 0 0;
}

.session-item :deep(.el-checkbox__label) {
  display: none;
}

.session-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.session-title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-strong);
}

.session-title .ellipsis {
  flex: 1;
  min-width: 0;
}

.live-dot {
  width: 8px;
  height: 8px;
  flex: none;
  border-radius: 50%;
  background: var(--primary);
  animation: pulse 1.6s ease-in-out infinite;
}

.session-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 10px;
  color: var(--color-text-muted);
}

.item-delete {
  opacity: 0;
  height: 20px;
  padding: 0 4px;
  transition: opacity 0.2s ease;
}

.session-item:hover .item-delete {
  opacity: 1;
}

.history-list .nb-empty {
  padding: 24px 8px;
}

.empty-hint {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

/* ===== 中栏：对话流 ===== */
.chat-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
}

.chat-inner {
  display: flex;
  flex-direction: column;
  gap: 22px;
  max-width: 880px;
  margin: 0 auto;
}

.chat-empty {
  gap: 6px;
  padding: 60px 16px;
}

.chat-empty-title {
  font-family: var(--font-headline);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-strong);
}

.chat-empty-hint {
  max-width: 420px;
  font-size: 12px;
  line-height: 1.7;
  text-align: center;
  color: var(--color-text-muted);
}

.msg {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.msg.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  flex: none;
  width: 40px;
  height: 40px;
  border: 2px solid #000;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #fff;
  color: var(--primary);
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  box-shadow: 2px 2px 0 #000;
}

.msg-avatar.assistant {
  background-image: var(--gradient-brand);
  color: #fff;
}

.bubble-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: min(78%, 720px);
  min-width: 0;
}

.msg.user .bubble-wrap {
  max-width: min(70%, 620px);
  align-items: flex-end;
}

.msg-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.ai-name {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text-strong);
}

.msg-head .nb-chip {
  font-size: 10px;
}

.stream-chip {
  font-size: 10px;
  font-weight: 700;
  color: var(--primary);
  animation: pulse 1.6s ease-in-out infinite;
}

.bubble {
  max-width: 100%;
  padding: 14px 16px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background: #fff;
  box-shadow: 4px 4px 0 #000;
  font-size: 14px;
  line-height: 1.75;
  color: var(--color-text-strong);
  overflow-wrap: anywhere;
}

.msg.user .bubble {
  background: #eaeefd;
  font-weight: 500;
}

.cited {
  display: inline-block;
  margin: 0 2px;
  padding: 0 5px;
  border: 1.5px solid #000;
  border-radius: var(--radius-tag);
  background: var(--primary-light);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
  color: var(--primary);
}

.cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

/* markdown 渲染区：v-html 内容不受 scoped 约束，需 :deep() */
.md :deep(p) {
  margin: 0 0 10px;
}

.md :deep(p:last-child) {
  margin-bottom: 0;
}

.md :deep(h1),
.md :deep(h2),
.md :deep(h3),
.md :deep(h4) {
  margin: 12px 0 8px;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.md :deep(ul),
.md :deep(ol) {
  margin: 0 0 10px;
  padding-left: 20px;
}

.md :deep(li) {
  margin: 3px 0;
}

.md :deep(strong) {
  font-weight: 700;
}

.md :deep(code) {
  padding: 1px 5px;
  border: 1px solid rgba(0, 0, 0, 0.3);
  border-radius: var(--radius-input);
  background: #f7f9fb;
  font-family: var(--font-mono);
  font-size: 12px;
}

.md :deep(pre) {
  margin: 0 0 10px;
  padding: 10px 12px;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #f7f9fb;
  overflow-x: auto;
}

.md :deep(pre code) {
  padding: 0;
  border: 0;
  background: none;
}

.md :deep(table) {
  display: block;
  width: 100%;
  max-width: 100%;
  margin: 0 0 10px;
  border: 2px solid #000;
  border-collapse: collapse;
  box-shadow: 2px 2px 0 #000;
  overflow-x: auto;
  font-size: 13px;
}

.md :deep(th) {
  padding: 6px 8px;
  border: 1px solid #000;
  background: #EAEEFD;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  text-align: left;
}

.md :deep(td) {
  padding: 6px 8px;
  border: 1px solid rgba(0, 0, 0, 0.7);
  vertical-align: top;
}

.md :deep(blockquote) {
  margin: 0 0 10px;
  padding: 10px 12px;
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: var(--danger-light);
  color: #DC2626;
  box-shadow: 2px 2px 0 #000;
}

.md :deep(blockquote p:last-child) {
  margin-bottom: 0;
}

.md :deep(a) {
  color: var(--primary);
  font-weight: 600;
}

/* 引用溯源折叠 */
.citations {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 2px solid rgba(0, 0, 0, 0.15);
}

.citations-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.citations-label {
  font-family: var(--font-headline);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-strong);
}

.citations-total {
  font-size: 10px;
  color: var(--color-text-muted);
}

.citation-group {
  border: 2px solid #000;
  border-radius: var(--radius-input);
  background: #f7f9fb;
  overflow: hidden;
}

.citation-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s ease;
}

.citation-row:hover {
  background: var(--primary-light);
}

.citation-count {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--color-text-muted);
}

.citation-count .el-icon {
  transition: transform 0.2s ease;
}

.citation-count .el-icon.open {
  transform: rotate(180deg);
}

.citation-list {
  display: flex;
  flex-direction: column;
  border-top: 2px solid #000;
  background: #fff;
}

.citation-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.citation-item:last-child {
  border-bottom: 0;
}

.citation-item a {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  text-decoration: none;
}

.citation-item a:hover {
  text-decoration: underline;
}

.citation-clause {
  margin: 0;
  padding: 6px 8px;
  border: 1px solid rgba(0, 0, 0, 0.3);
  border-radius: var(--radius-input);
  background: #fff;
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-secondary);
}

/* 回答操作条 */
.feedback-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 2px solid #000;
}

.act-btn {
  padding: 4px 10px;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  background: #fff;
  color: var(--color-text-strong);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  box-shadow: 2px 2px 0 #000;
  cursor: pointer;
  transition: all 0.2s ease;
}

.act-btn:hover {
  transform: translate(-2px, -2px);
  box-shadow: 4px 4px 0 #000;
}

.act-btn:active {
  transform: translate(2px, 2px);
  box-shadow: none;
}

.act-btn.active {
  background-image: var(--gradient-brand);
  color: #fff;
}

/* 底部输入区 */
.chat-inputbar {
  flex: none;
  padding: 12px;
  border-top: 2px solid #000;
  background: #f7f9fb;
}

.input-shell {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background: #fff;
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s ease;
}

.input-shell:focus-within {
  box-shadow: 4px 4px 0 var(--primary);
}

.input-main {
  flex: 1;
  min-width: 0;
}

.input-main textarea {
  width: 100%;
  min-height: 52px;
  max-height: 120px;
  padding: 2px 4px;
  border: 0;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--color-text-strong);
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.7;
}

.input-main textarea::placeholder {
  color: var(--color-text-muted);
}

.input-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  padding-top: 6px;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}

.input-hint,
.input-count {
  font-size: 10px;
  color: var(--color-text-muted);
}

.send-btn {
  flex: none;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border: 2px solid #000;
  border-radius: var(--radius-btn);
  background-image: var(--gradient-brand);
  color: #fff;
  box-shadow: 3px 3px 0 #000;
  cursor: pointer;
  transition: all 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0 #000;
}

.send-btn:active:not(:disabled) {
  transform: translate(2px, 2px);
  box-shadow: none;
}

.send-btn:disabled {
  background-image: none;
  background: #E1E8ED;
  cursor: not-allowed;
  box-shadow: 2px 2px 0 #000;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.disclaimer {
  margin: 8px 2px 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-muted);
}

/* ===== 右栏：引用依据与溯源 ===== */
.ref-panel {
  width: 360px;
  flex: none;
  display: flex;
  flex-direction: column;
}

.ref-head {
  background: #f7f9fb;
}

.ref-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}

.ref-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background: #fff;
  box-shadow: 2px 2px 0 #000;
  overflow: hidden;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  border-right: 1px solid rgba(0, 0, 0, 0.15);
}

.stat:last-child {
  border-right: 0;
}

.stat-num {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--color-text-strong);
}

.stat-label {
  font-size: 10px;
  color: var(--color-text-muted);
}

.ref-section-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.ref-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background: #fff;
  box-shadow: 3px 3px 0 #000;
}

.ref-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ref-count {
  font-size: 10px;
  color: var(--color-text-muted);
}

.ref-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.15);
}

.ref-card-head + .ref-item {
  padding-top: 0;
  border-top: 0;
}

.ref-name {
  font-family: var(--font-headline);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
  color: var(--primary);
  text-decoration: none;
}

.ref-name:hover {
  text-decoration: underline;
}

.ref-clause {
  margin: 0;
  padding: 6px 8px;
  border: 1px solid rgba(0, 0, 0, 0.3);
  border-radius: var(--radius-input);
  background: #f7f9fb;
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.ref-body .nb-empty {
  padding: 28px 8px;
}

/* ===== 反馈对话框 ===== */
.feedback-dialog {
  border: 3px solid #000;
  border-radius: var(--radius-dialog);
  box-shadow: var(--shadow-dialog);
}

.feedback-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding: 12px 16px;
  border-bottom: 2px solid #000;
  background: #EAEEFD;
}

.feedback-dialog :deep(.el-dialog__title) {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text-strong);
}

.feedback-dialog :deep(.el-dialog__body) {
  padding: 16px;
}

.feedback-dialog :deep(.el-dialog__footer) {
  padding: 12px 16px;
  border-top: 2px solid #000;
  background: #f7f9fb;
}

.dislike-tip {
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--color-text-strong);
}

.reason-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  border: 2px solid #000;
  border-radius: var(--radius-card);
  background: #fff;
}

.reason-group :deep(.el-checkbox) {
  height: auto;
  margin-right: 0;
}

.reason-group :deep(.el-checkbox__label) {
  font-size: 13px;
  font-weight: 600;
}
</style>
