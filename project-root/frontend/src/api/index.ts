import http from './http'

// ===== 认证 =====
export const authApi = {
  login: (data: { username: string; password: string }) => http.post('/auth/login', data),
  logout: () => http.post('/auth/logout'),
  me: () => http.get('/auth/me'),
  refresh: (refreshToken: string) => http.post('/auth/refresh', { refresh_token: refreshToken }),
  changePassword: (data: any) => http.put('/auth/password', data),
}

// ===== 隐患管理 =====
export const hazardApi = {
  // AI 识别（H09）：上传图片，返回标注图和检测框数组
  aiDetect: (form: FormData) =>
    // 模型识别可能耗时，放宽到 150s（后端上界 120s + 1 次重试）
    http.post('/hazards/ai-detect', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 150000,
    }),
  // 隐患列表（H02）
  list: (params?: any) => http.get('/hazards', { params }),
  // 隐患详情（H03）
  detail: (id: string) => http.get(`/hazards/${id}`),
  // 隐患上报（H01）
  submit: (form: FormData) =>
    http.post('/hazards', form, { headers: { 'Content-Type': 'multipart/form-data' } }),
  // 删除隐患
  delete: (id: string) => http.delete(`/hazards/${id}`),
}

// ===== AI 智能问答 =====
export interface AiChatHandlers {
  onToken?: (token: string) => void
  onSources?: (sources: any[]) => void
  onDone?: (meta: { session_id: string; message_id: string }) => void
  onError?: (message: string) => void
}

export interface FeedbackPayload {
  rating: 'like' | 'dislike'
  reasons: string[]
  comment?: string
}

// 通用 SSE 请求：按空行切分事件，逐帧交给 parseSseEvent
function runSse(url: string, body: unknown, handlers: AiChatHandlers) {
  const controller = new AbortController()
  const promise = (async () => {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    if (!res.ok || !res.body) {
      handlers.onError?.(`请求失败（${res.status}）`)
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE 事件以空行分隔
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        parseSseEvent(rawEvent, handlers)
      }
    }
  })()
  return { promise, controller }
}

export const aiApi = {
  sessions: (params?: any) => http.get('/ai/sessions', { params }),
  createSession: () => http.post('/ai/sessions'),
  messages: (sessionId: string) => http.get(`/ai/sessions/${sessionId}/messages`),
  deleteSession: (sessionId: string) => http.delete(`/ai/sessions/${sessionId}`),
  batchDeleteSessions: (sessionIds: string[]) => http.post('/ai/sessions/batch-delete', { session_ids: sessionIds }),
  renameSession: (sessionId: string, title: string) =>
    http.put(`/ai/sessions/${sessionId}`, { title }),
  // 消息点赞/点踩（B6）
  feedback: (messageId: string, data: FeedbackPayload) =>
    http.post(`/ai/messages/${messageId}/feedback`, data),
  cancelFeedback: (messageId: string) => http.delete(`/ai/messages/${messageId}/feedback`),

  // SSE 流式问答：解析 token / sources / done / error 事件
  chat: (data: { question: string; session_id: string | null }, handlers: AiChatHandlers) =>
    runSse('/api/v1/ai/chat', data, handlers),
}

// ===== 管理端模型测试（不落会话、无点赞与历史） =====
export const adminApi = {
  chatTest: (modelId: number, question: string, handlers: AiChatHandlers) =>
    runSse(`/api/v1/admin/models/${modelId}/chat-test`, { question }, handlers),
}

function parseSseEvent(raw: string, handlers: AiChatHandlers) {
  let event = ''
  const dataLines: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  const data = dataLines.join('\n')
  if (!data) return

  if (event === 'token') {
    handlers.onToken?.(data)
  } else if (event === 'sources') {
    try {
      handlers.onSources?.(JSON.parse(data))
    } catch {
      handlers.onSources?.([])
    }
  } else if (event === 'done') {
    try {
      handlers.onDone?.(JSON.parse(data))
    } catch {
      handlers.onDone?.({ session_id: '', message_id: '' })
    }
  } else if (event === 'error') {
    try {
      const err = JSON.parse(data)
      handlers.onError?.(err.message || '生成失败')
    } catch {
      handlers.onError?.(data)
    }
  }
}

// ===== 考试工坊 =====
export const examApi = {
  papers: (params?: any) => http.get('/exam/papers', { params }),
  createPaper: (data: any) => http.post('/exam/papers', data),
  paperDetail: (id: string) => http.get(`/exam/papers/${id}`),
  aiGenerate: (data: any) => http.post('/exam/ai/generate', data),
  importQuestions: (form: FormData, enterBank: boolean) =>
    http.post(`/exam/questions/import?enter_bank=${enterBank}`, form),
}

// ===== 消息通知 =====
export const notificationApi = {
  list: (params?: any) => http.get('/notifications', { params }),
  unreadCount: () => http.get('/notifications/unread-count'),
  readAll: () => http.post('/notifications/read-all'),
  markRead: (id: string) => http.put(`/notifications/${id}/read`),
  delete: (id: string) => http.delete(`/notifications/${id}`),
  batchDelete: (ids: string[]) => http.post('/notifications/batch-delete', { notification_ids: ids }),
  // 管理员推送消息
  send: (data: { user_ids: string[]; title: string; content: string }) =>
    http.post('/notifications/send', data),
}

// ===== 用户管理 =====
export const userApi = {
  list: (params?: any) => http.get('/users', { params }),
  create: (data: any) => http.post('/users', data),
  update: (id: string, data: any) => http.put(`/users/${id}`, data),
  delete: (id: string) => http.delete(`/users/${id}`),
}

// ===== 知识库管理（B4） =====
export interface KnowledgeDocument {
  document_id: number
  title: string
  doc_type: string
  category_id: number | null
  tags: string[]
  authority_level: string
  file_path?: string
  file_size: number
  status: 'parsing' | 'chunking' | 'indexing' | 'indexed' | 'failed' | string
  chunk_count: number
  error_message: string | null
  created_by?: string
  created_at: string
  updated_at?: string
}

export interface DocumentPage {
  items: KnowledgeDocument[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface KnowledgeCategory {
  category_id: number
  name: string
  parent_id: number | null
  level?: number
  sort_order?: number
  children: KnowledgeCategory[]
}

export const knowledgeApi = {
  // 文档列表（分页 + 类型/状态/关键词筛选）
  documents: (params?: {
    page?: number
    page_size?: number
    type?: string
    status?: string
    keyword?: string
  }) => http.get<DocumentPage>('/knowledge/documents', { params }),
  // 上传文档（multipart: file/title/doc_type/category_id/tags/authority_level）
  uploadDocument: (form: FormData) =>
    http.post('/knowledge/documents', form, { headers: { 'Content-Type': 'multipart/form-data' } }),
  // 单个文档解析状态
  documentStatus: (docId: number) =>
    http.get<{ document_id: number; status: string; chunk_count: number; error_message: string | null }>(
      `/knowledge/documents/${docId}/status`,
    ),
  // 删除文档（同步清理向量与分块）
  deleteDocument: (docId: number) => http.delete(`/knowledge/documents/${docId}`),
  // 分类树（固定三类：国家规定/地方规定/内部规定，后端自动补齐）
  categories: () => http.get<KnowledgeCategory[]>('/knowledge/categories'),
}

// ===== 统计（B5） =====
export interface AiSatisfaction {
  total_feedback_count: number
  like_count: number
  dislike_count: number
  like_rate: number
  dislike_reasons: {
    inaccurate: number
    incomplete: number
    misunderstanding: number
    off_topic: number
    other: number
  }
  total_questions: number
  avg_response_time_ms: number
  model_usage: { model: string; count: number }[]
}

export const statisticsApi = {
  aiSatisfaction: (params?: { days?: number }) =>
    http.get<AiSatisfaction>('/statistics/ai-satisfaction', { params }),
}
