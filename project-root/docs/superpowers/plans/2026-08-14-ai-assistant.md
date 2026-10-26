# AI 智能助手模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `project-root` 后端实现 AI 智能助手（A01–A07），采用本地 BGE + Chroma 向量 RAG + OpenAI 兼容大模型。

**Architecture:** SQLite `transport_safety_kb.sqlite3` 作为事实源，`bge-large` 做向量化存入 Chroma，`bge-base-rerank` 重排，`LLM_*` 大模型流式生成；新增 6 张 APP 表持久化会话/消息/反馈/快捷问题/审计/敏感词。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite、sentence-transformers、chromadb、openai、pytest。

## Global Constraints

- 项目根目录：`D:\实习\shudao\test\project-root`。
- 统一响应 `{code,message,data,timestamp}`；SSE 例外。
- 认证：Bearer JWT；登录以外接口需鉴权。
- 本地模型路径：`models/bge-large`、`models/bge-base-rerank`（已复制）。
- 事实库：`database/transport_safety_kb.sqlite3`（只读）。
- 测试环境：`D:\Anaconda\envs\shixi\python.exe`。
- 大模型配置：`.env` 的 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME`；留空则 `/ai/chat` 返回 40203。
- 每个任务遵循 TDD。

---

### Task 0: 配置与依赖

**Files:** Modify `backend/app/core/config.py`、`.env`、`backend/requirements.txt`

**Interfaces:** `settings.LLM_API_KEY/LLM_BASE_URL/LLM_MODEL_NAME`、`settings.EMBEDDING_MODEL_DIR`、`settings.RERANK_MODEL_DIR`、`settings.CHROMA_PERSIST_DIR`、`settings.AI_RATE_LIMIT_PER_MIN`

- [ ] 在 `.env` 追加（先留空，用户填）：

```text
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL_NAME=
```

- [ ] `config.py` 增加：

```python
LLM_API_KEY: str = ""
LLM_BASE_URL: str = ""
LLM_MODEL_NAME: str = ""
EMBEDDING_MODEL_DIR: str = str(_PROJECT_ROOT / "models" / "bge-large")
RERANK_MODEL_DIR: str = str(_PROJECT_ROOT / "models" / "bge-base-rerank")
CHROMA_PERSIST_DIR: str = str(_PROJECT_ROOT / "chroma_data")
AI_RATE_LIMIT_PER_MIN: int = 10
```

- [ ] `requirements.txt` 追加 `sentence-transformers>=2.5.0`、`chromadb>=0.4.0`（环境已装，记录在案）。
- [ ] 验证：`python -c "from app.core.config import settings; print(settings.EMBEDDING_MODEL_DIR)"`。

---

### Task 1: AI 六张表 + ORM + 敏感词预置

**Files:** Modify `database/schema.sql`、`database/init_data.sql`；Create `backend/app/models/ai_orm.py`；Modify `backend/app/models/__init__.py`

**Interfaces:** ORM 类 `Conversation/Message/MessageFeedback/QuickQuestion/AiAuditLog/SensitiveWord`

- [ ] `schema.sql` 增加 6 张表（字段严格对齐 DATABASE.md §3.10–3.13、3.23–3.24）。
- [ ] `init_data.sql` 用 `INSERT OR IGNORE` 预置少量敏感词（如 `政治敏感/暴力/色情` 示例）。
- [ ] `ai_orm.py` 定义 ORM；`models/__init__.py` 导出。
- [ ] 测试：`init_db()` 后这 6 张表存在且敏感词已预置。

---

### Task 2: 敏感词 DFA 过滤

**Files:** Create `backend/app/services/sensitive_word.py`；Test `backend/tests/test_ai.py`

**Interfaces:** `SensitiveWordFilter(db).filter_input(text) -> FilterResult`、`filter_output(text) -> FilterResult`

- [ ] 写失败测试：命中敏感词 → `passed=False`；未命中 → `passed=True`；输出过滤把命中词替换为 `***`。
- [ ] 实现：从 `sensitive_words` 表加载词库构建 DFA trie，`match/replace`（参考 ARCHITECTURE.md §8.2）。
- [ ] 运行测试通过。

---

### Task 3: Embedding 与 Rerank 封装

**Files:** Create `backend/app/services/embedding.py`；Test `backend/tests/test_ai.py`

**Interfaces:** `EmbeddingService.embed(texts) -> list[list[float]]`、`RerankService.rerank(query, candidates) -> list[tuple[doc,score]]`

- [ ] 写失败测试：用本地 `bge-large` 对两个句子编码，向量维度 1024 且相似句更近；`bge-base-rerank` 对候选打分排序。
- [ ] 实现：`SentenceTransformer(settings.EMBEDDING_MODEL_DIR)`；`CrossEncoder(settings.RERANK_MODEL_DIR)`。
- [ ] 运行测试通过（首次加载模型较慢）。

---

### Task 4: RAG 索引构建

**Files:** Create `backend/app/services/rag.py`；Test `backend/tests/test_ai.py`

**Interfaces:** `RagService.build_index()`、`RagService.retrieve(query, top_k=5) -> list[dict]`

- [ ] 写失败测试：`build_index()` 后 Chroma 集合 `safety_evidence_v1` 记录数 = 可准入 `evidence_units` 数；`retrieve("安全生产法")` 返回带 `title/locator/source_uri/text` 的结果。
- [ ] 实现：读 `transport_safety_kb.sqlite3`（只读），过滤 `invalidated=0` 且 `text` 非空，拼接 embedding 文本（标题+类型+主题+位置+正文），批量 embed 写入 Chroma（幂等，用 `schema_metadata` 记录已索引版本）。
- [ ] 运行测试通过。

---

### Task 5: 大模型流式调用

**Files:** Create `backend/app/services/llm.py`；Test `backend/tests/test_ai.py`

**Interfaces:** `LlmService.is_configured()`、`async stream_chat(messages) -> AsyncGenerator[str]`

- [ ] 写失败测试：未配置返回 40203；配置后（monkeypatch OpenAI client）按 token 流式 yield。
- [ ] 实现：`OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)`，`chat.completions.create(stream=True)` 逐 chunk yield。
- [ ] 运行测试通过。

---

### Task 6: 会话管理（A02）

**Files:** Create `backend/app/schemas/ai.py`、`backend/app/services/ai_chat.py`、`backend/app/api/v1/ai.py`；Modify `router.py`

**Interfaces:** `create_session`、`list_sessions`、`list_messages`、`rename_session`、`delete_session`、`batch_delete_sessions`

- [ ] 写失败测试：新建会话、列表、取消息、改标题、删除、批量删除、超 100 会话返回 40204。
- [ ] 实现 REST 接口（`/ai/sessions` 系列），会话标题首问自动生成。
- [ ] 运行测试通过。

---

### Task 7: 智能问答 + SSE + 停止（A01/A03/A05/A06）

**Files:** Modify `backend/app/services/ai_chat.py`、`backend/app/api/v1/ai.py`

**Interfaces:** `POST /ai/chat`（SSE：`token/done/sources/error`）、`POST /ai/chat/{message_id}/stop`

- [ ] 写失败测试：提问后返回 `session_id/message_id` 与来源；停止后消息 `interrupted`；无依据时拒答。
- [ ] 实现：敏感词过滤 → RAG 检索 → 组装 Prompt（含 5 轮历史）→ SSE 流式 → 保存消息 + 来源 + 审计日志。
- [ ] 运行测试通过。

---

### Task 8: 快捷提问（A04）

**Files:** Modify `backend/app/api/v1/ai.py`

**Interfaces:** `GET /ai/quick-questions`、管理端 `GET/POST/PUT/DELETE /ai/quick-questions`

- [ ] 写失败测试：按角色返回可见问题；Admin 可增删改查。
- [ ] 实现：`quick_questions` 表 CRUD + `roles_json/is_hot/is_active` 过滤。
- [ ] 运行测试通过。

---

### Task 9: 点赞/踩（A07）

**Files:** Modify `backend/app/api/v1/ai.py`

**Interfaces:** `POST/DELETE /ai/messages/{message_id}/feedback`

- [ ] 写失败测试：点赞/踩、重复评价 40012、取消后重评。
- [ ] 实现：`message_feedback` 表，`UNIQUE(message_id,user_id)`。
- [ ] 运行测试通过。

---

### Task 10: 审计日志 + 限流

**Files:** Modify `backend/app/services/ai_chat.py`、`backend/app/core/config.py`

**Interfaces:** 每次问答写 `ai_audit_log`；单用户超过 10 次/分钟返回 42901。

- [ ] 写失败测试：问答后 `ai_audit_log` 有记录；同一用户快速超限返回 42901。
- [ ] 实现：滑动窗口限流（内存）；审计字段（session/user/question/answer/model/耗时/sources/filter_action/token）。
- [ ] 运行测试通过。

---

### Task 11: 路由聚合 + 全量回归

**Files:** Modify `backend/app/api/v1/router.py`

- [ ] `api_router.include_router(ai.router)`。
- [ ] 运行 `pytest backend/tests/ -q` 全绿。

---

## Self-Review

- 覆盖：A01(T7)、A02(T6)、A03(T7)、A04(T8)、A05(T4/T7)、A06(T7)、A07(T9)、安全(T2/T10)。
- 未覆盖（明确延后）：知识库文档上传/解析/向量化（Phase 2）、考试出题（另一模块）。
- 占位符：无 TBD；跨任务接口名一致。

---

## 实施状态（2026-08-14）

- 已完成 Task 0–11，AI 智能助手后端主链路全部实现。
- 测试：`backend/tests/test_ai.py` 新增 13 个测试，全量 `59 passed`。
- 真实模型验证：本地 `bge-large` 向量化（1024 维）与 `bge-base-rerank` 重排均加载成功；完整 RAG 索引已构建 2008 条，检索返回高分命中。
- 已知注意事项：当前 Chroma 1.5.9 对大向量集合持久化后重新打开会出现 HNSW 加载错误；`RagService` 已加入同进程懒重建兜底。首次查询会触发重建（约 1–2 分钟），后续同进程查询走缓存。
