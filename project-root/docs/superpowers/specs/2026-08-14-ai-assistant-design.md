# AI 智能助手模块设计文档

> 日期：2026-08-14
> 范围：project-root 后端，AI 智能助手（PRD A01–A07）

## 1. 目标

实现基于企业安全知识库的 AI 智能问答：

- A01 智能问答（RAG + 大模型）
- A02 会话管理
- A03 SSE 流式输出 + 停止生成
- A04 快捷提问
- A05 知识检索（RAG）
- A06 回答引用
- A07 点赞/踩反馈

## 2. 关键技术决策

1. **检索 = 向量 + FTS5 混合，向量离线本地**：
   - 事实源：`database/transport_safety_kb.sqlite3` 的 `evidence_units`（2008 条）
   - Embedding：本地 `models/bge-large`（sentence-transformers）
   - 向量库：Chroma（本地持久化，`chroma_data/`）
   - 重排：本地 `models/bge-base-rerank`（CrossEncoder）
   - 关键字：SQLite `knowledge_fts`（FTS5）
2. **大模型**：OpenAI 兼容接口，`.env` 新增 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME`（与视觉模型 `VISULIZATION_*` 分开）。
3. **流式**：SSE 逐字输出，支持停止。
4. **知识库管理接口（文档上传/解析/向量化）本轮不做**，只做检索 + 回答。
5. **安全**：敏感词 DFA 过滤（输入前置 + 输出后置）、AI 审计日志、单用户限流 10 次/分钟、会话上限 100、5 轮上下文。

## 3. 数据流

```
用户提问
  → 敏感词检测(DFA)
  → 查询向量化(bge-large)
  → Chroma 向量检索 Top-10
  → bge-base-rerank 重排 Top-5
  → 组装受控上下文(证据 + 历史5轮)
  → 大模型流式生成(SSE)
  → 敏感词后置过滤
  → 保存消息 + 引用 + AI 审计日志
```

## 4. 数据库（新增 APP 表）

对齐 DATABASE.md §3.10–3.13、3.23–3.24：

- `conversations`（会话，用户 ≤100）
- `messages`（消息，role/sources/status）
- `message_feedback`（点赞/踩）
- `quick_questions`（快捷提问）
- `ai_audit_log`（AI 审计）
- `sensitive_words`（敏感词库）

## 5. 文件结构

```
project-root/
├── .env                              # +LLM_* / EMBEDDING/RERANK/CHROMA 路径
├── models/bge-large                   # 已复制
├── models/bge-base-rerank            # 已复制
├── chroma_data/                      # 运行期生成
├── database/schema.sql               # +AI 6 张表
├── backend/app/
│   ├── core/config.py                # +LLM/embedding/rerank/chroma/限流配置
│   ├── models/ai_orm.py              # +6 个 ORM
│   ├── schemas/ai.py                 # +AI 相关 Schema
│   ├── services/sensitive_word.py    # +DFA 过滤
│   ├── services/embedding.py         # +bge-large 封装
│   ├── services/rag.py               # +索引构建 + 检索
│   ├── services/llm.py               # +OpenAI 兼容流式调用
│   ├── services/ai_chat.py           # +问答编排
│   └── api/v1/ai.py                  # +AI 路由
└── backend/tests/test_ai.py
```

## 6. 接口（对齐 API.md §4）

- `POST /ai/chat`（SSE）
- `POST /ai/chat/{message_id}/stop`
- `GET/POST /ai/sessions`
- `GET /ai/sessions/{session_id}/messages`
- `PUT /ai/sessions/{session_id}`（改标题）
- `DELETE /ai/sessions/{session_id}`
- `POST /ai/sessions/batch-delete`
- `GET /ai/quick-questions`
- `GET/POST/PUT/DELETE /ai/quick-questions`（管理端）
- `POST /ai/messages/{message_id}/feedback`
- `DELETE /ai/messages/{message_id}/feedback`

## 7. 验收口径

- 全部新接口有测试，`pytest` 全绿。
- 回答引用带 `title/locator/source_uri`；无依据时明确拒答。
- SSE 首字返回；停止后消息 `interrupted` 且保留已输出内容。
- 敏感词拦截、限流 429、审计日志全量落库。

## 8. 实施记录（2026-08-14）

按本设计完成实现。新增文件：

- `backend/app/models/ai_orm.py`
- `backend/app/schemas/ai.py`
- `backend/app/services/{sensitive_word,embedding,rag,llm,ai_chat}.py`
- `backend/app/api/v1/ai.py`
- `backend/scripts/build_rag_index.py`
- `backend/tests/test_ai.py`

修改文件：`core/config.py`、`core/response.py`、`models/__init__.py`、`api/v1/router.py`、`database/schema.sql`、`database/init_data.sql`、`.env`、`requirements.txt`、`docs/接口测试文档.md`。

全量测试：`59 passed`。RAG 索引已用本地模型构建完成（2008 条向量，`chroma_data/`）。
