# 全链路 async 化 + PostgreSQL 迁移实施计划

> 日期：2026-08-21
> 分支：docs/liangchangzhen/docs_v1（工作区较脏，不做 worktree，直接推进）
> 决策：全链路 async / 本机安装 PG / 全量数据迁移 / 测试用 aiosqlite / KB 文件保留只读备份

## 目标架构

```
FastAPI (async def 路由, 全模块)
    │
    ├── AsyncSession (SQLAlchemy 2.0 async)
    │     └── create_async_engine
    │           ├── 生产: postgresql+asyncpg://localhost:5432/shudao
    │           └── 测试: sqlite+aiosqlite:///{tmp}/test.db
    │
    ├── LLM 调用 → AsyncOpenAI（流式 SSE 纯异步）
    ├── embedding/rerank（CPU 阻塞）→ anyio.to_thread 包装
    ├── KB 数据 → ORM 表（kb_documents / kb_evidence_units），启动时载入内存索引
    └── main.py 催办线程 → asyncio 原生后台任务
```

## 关键约束（调查结论）

1. **渐进式共存**：base.py 同时保留 sync engine（未转换模块用）+ async engine（已转换模块用），两者指向同一 SQLite 文件，每转一个模块跑一次全量 pytest 保持绿色，最后删除 sync 引擎
2. **`db.query()` 必须重写**：AsyncSession 不支持 legacy Query，全部改 `await db.execute(select())` + `.scalars().all()`
3. **strftime 默认值**：所有模型的 `server_default=text("strftime(...)")` 改为 Python 端 `default=now_cst`
4. **schema.sql 退役**：init_db 改用 `Base.metadata.create_all()`（跨库通用），种子数据改为"先查后插"幂等写法
5. **KB 迁移**：transport_safety_kb.sqlite3 的 documents/evidence_units 建 ORM 表并入主库；rag.py/exam_service.py 的 sqlite3 直连改 ORM 查询；原文件保留只读备份
6. **Chroma 不动**：chunk_id 迁移时保持不变，向量索引继续可用

## 通用转换模式（所有模块遵循）

```python
# 路由: def → async def，Session → AsyncSession
@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db_async)):
    data = await auth_service.login(db, req.username, req.password)
    return success(data)

# 服务: db.query(X).filter(...).all() →
rows = (await db.execute(select(X).where(...))).scalars().all()
# db.query(X).count() →
(await db.execute(select(func.count()).select_from(X).where(...))).scalar()
# db.get(X, id) → await db.get(X, id)
# db.commit() → await db.commit(); db.refresh(x) → await db.refresh(x)
# db.add() 不变（无 IO）
```

---

## P0 环境准备

### Task 0.1 安装依赖
```powershell
D:\Anaconda\envs\shixi\python.exe -m pip install asyncpg aiosqlite greenlet
```
验证：`python -c "import asyncpg, aiosqlite, greenlet; print('ok')"`

### Task 0.2 PostgreSQL 安装（用户手动）
用户安装 PG 16（Windows 安装包），设好 postgres 密码。之后：
```powershell
psql -U postgres -c "CREATE DATABASE shudao ENCODING 'UTF8';"
```

---

## P1 基础层（共存期开始）

### Task 1.1 base.py 增加 async 引擎
文件：`backend/app/models/base.py`
- 保留现有 sync engine/SessionLocal/get_db（未转换模块继续用）
- 新增：`async_engine = create_async_engine(settings.DATABASE_URL_ASYNC)`、`async_session_factory = async_sessionmaker(...)`、`get_db_async`（async generator 依赖）
- DATABASE_URL_ASYNC 由 config.py 推导：sqlite:///X → sqlite+aiosqlite:///X；postgresql+asyncpg 原样
- PG 时不再挂 PRAGMA 监听器（仅 sqlite 挂）

### Task 1.2 config.py 增加异步 URL 推导
文件：`backend/app/core/config.py`
- 新增属性/computed：`DATABASE_URL_ASYNC`（按上述规则转换）
- 默认 DATABASE_URL 保持 sqlite 指向 app.db，生产用 .env 覆盖为 postgresql+asyncpg://...

### Task 1.3 模型时间默认值可移植化
文件：`backend/app/models/` 下 role.py / user_orm.py / hazard.py / notification.py / ai_orm.py / auth_session.py / knowledge.py / exam.py
- 新增 `backend/app/models/mixins.py`：`now_cst()` 返回 `datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()` 格式串（与现有 strftime 输出一致：`YYYY-MM-DDTHH:MM:SS+08:00`）
- 所有 `server_default=text("strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')")` → `default=now_cst`
- 验证：`pytest tests/test_auth.py`（sync 引擎路径不受影响）

### Task 1.4 init_db 重写（去 schema.sql 依赖）
文件：`backend/app/core/database.py`
- `init_db()` 改为 async：`async with async_engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)`
- `_seed_users/_seed_exam/_migrate_roles` 改为 async + Core `select`/`insert`（先查后插，替代 INSERT OR IGNORE；_migrate_roles 的 UPDATE/DELETE 原生 SQL 兼容两库）
- 删除 executescript/schema.sql/ALTER TABLE 分支（create_all 由 ORM 生成完整结构；exam_url 已在 ORM 中定义则直接生效）
- main.py lifespan：`await init_db()`（init_db 内部用 asyncio 兼容调用）
- **注意**：schema.sql 中若有 ORM 未覆盖的 CHECK 约束，记录到差异清单，迁移脚本建 PG 时人工核对
- 验证：删除临时 app.db 副本 → 启动 init_db → 表结构与种子齐全；`pytest tests/test_auth.py`

### Task 1.5 conftest 适配双引擎
文件：`backend/tests/conftest.py`
- `DATABASE_URL` → `sqlite:///{tmp}/test.db`（sync 种子用）；`DATABASE_URL_ASYNC` → `sqlite+aiosqlite:///{tmp}/test.db`（app 用）
- client fixture：drop_all 用 async engine（`asyncio.run` 或 TestClient portal 内）；init_db 用 async 版
- db fixture（测试直接造数据）：保持 **sync Session 指向同一 test.db 文件**（SQLite 多连接安全，TestClient 串行请求无锁竞争）
- 验证：`pytest tests/test_auth.py tests/test_users.py`

---

## P2 模块逐个 async 化（每任务后跑全量 pytest）

每个任务的套路一致：路由 `def`→`async def` + `Depends(get_db_async)` + `AsyncSession`；服务函数加 `async` + 按"通用转换模式"重写查询；`get_auth_context` 过渡期新增 `get_auth_context_async`（已转换路由用），全模块完成后删同步版。

### Task 2.1 auth 模块
文件：`app/api/v1/auth.py`、`app/services/auth_service.py`、`app/api/deps.py`（新增 async 版鉴权）
验证：`pytest tests/test_auth.py`

### Task 2.2 users 模块
文件：`app/api/v1/users.py`、`app/services/user_service.py`
验证：`pytest tests/test_users.py tests/test_user_management.py`

### Task 2.3 notifications 模块
文件：`app/api/v1/notifications.py`、`app/services/notification_service.py`
验证：`pytest tests/test_notifications.py`

### Task 2.4 hazards 模块（最重业务）
文件：`app/api/v1/hazards.py`、`app/services/hazard_service.py`、`app/services/vision.py`（LLM 调用改 httpx.AsyncClient/AsyncOpenAI）
验证：`pytest tests/test_hazards.py tests/test_vision.py`

### Task 2.5 exam 模块
文件：`app/api/v1/exam.py`、`app/services/exam_service.py`、`exam_excel.py`、`pdf_export.py`（纯 CPU 保持同步，路由层 to_thread 包装可选）
- `_read_document_text` 的 sqlite3 直连暂保持（P3 统一改 ORM）
验证：`pytest tests/test_exam.py`

### Task 2.6 knowledge + statistics + admin 模块
文件：`app/api/v1/knowledge.py`、`statistics.py`、`admin.py`；`app/services/knowledge_service.py`、`testset_service.py`、`model_eval_service.py`
验证：`pytest tests/test_knowledge.py tests/test_knowledge_unit.py tests/test_statistics.py tests/test_model_eval.py`

---

## P3 RAG / AI 深度改造

### Task 3.1 KB 数据 ORM 化
文件：`app/models/knowledge.py`（新增 KbDocument / KbEvidenceUnit）、`app/models/__init__.py`
- 表结构对齐 transport_safety_kb.sqlite3 的 documents / evidence_units 列
- 主键/ID 原样保留（Chroma 向量按 chunk_id 关联）

### Task 3.2 rag.py 重写数据源
文件：`app/services/rag.py`
- `_load_evidence`/`_load_rag_config` 的 sqlite3 直连 → AsyncSession ORM 查询（evidence 全量载入内存索引，现状不变）
- retrieve 调用链 async 化；embedding/rerank CPU 调用用 `anyio.to_thread.run_sync` 包装
验证：`pytest tests/test_rag.py`（内存注入，应全绿）

### Task 3.3 ai_chat.py SSE 纯异步
文件：`app/services/ai_chat.py`、`app/services/llm.py`、`app/api/v1/ai.py`、`app/api/v1/rag.py`
- OpenAI 客户端 → AsyncOpenAI，stream=True 异步迭代
- SSE 生成器 → async generator（`StreamingResponse` 原生支持）
- 会话/消息持久化 async 化
验证：`pytest tests/test_ai.py`

### Task 3.4 exam_service KB 读取改 ORM
文件：`app/services/exam_service.py`（`_read_document_text`）
验证：`pytest tests/test_exam.py`

---

## P4 收尾统一

### Task 4.1 main.py 后台任务 asyncio 化
- `_urge_loop` 线程 → `asyncio.create_task` + `asyncio.sleep(3600)` + AsyncSession
- `_preload_models` → `asyncio.to_thread`（torch 加载是阻塞 CPU）
- 删除 `threading` 依赖

### Task 4.2 删除 sync 引擎
- base.py 删除 sync engine/SessionLocal/get_db；`get_db_async` 改名 `get_db`；deps 删同步鉴权
- 全库 grep `SessionLocal|from sqlalchemy.orm import Session` 清零
验证：`pytest`（全量 129 条全绿）

---

## P5 数据迁移 + PG 切换

### Task 5.1 迁移脚本
文件：`backend/scripts/migrate_sqlite_to_pg.py`（新建）
- 读 app.db 全部表 + transport_safety_kb.sqlite3 的 documents/evidence_units
- 写入 PG（psycopg2 同步驱动，独立于 app）
- 保持所有主键/ID/时间戳原样；完成后打印各表行数核对清单

### Task 5.2 切换与验证
- `.env`：`DATABASE_URL=postgresql+asyncpg://postgres:{pwd}@localhost:5432/shudao`
- 启动后端 → init_db（create_all 幂等，不动已有数据）
- 前端全功能手测：登录/工作台/隐患/AI 问答（流式）/考试/知识库/测试集
- `transport_safety_kb.sqlite3` 更名 `transport_safety_kb.sqlite3.bak`（只读备份）

---

## 风险与回退

| 风险 | 应对 |
|------|------|
| AsyncSession 与 lazy relationship 触发 MissingGreenlet | 显式 selectinload 或改用先查后组 dict（现有服务多为后者，风险低） |
| schema.sql 的 CHECK 约束丢失 | create_all 后核对差异清单；业务校验已在 service 层 |
| PG 中文全文检索 | 不用 PG FTS，BM25 仍在内存索引（现状不变） |
| 测试双连接写竞争 | TestClient 串行执行，无并发；db fixture 提交后 API 可见 |
| 迁移后 Chroma 失配 | chunk_id 不变；若仍失配重建索引脚本已有（build_rag_index.py） |

## 执行顺序总览

P0 → P1（1.1-1.5 串行）→ P2（2.1→2.6 串行，每步全量 pytest）→ P3（3.1→3.4）→ P4 → P5

## 进度记录

- 2026-08-21：P0 / P1（base.py 双引擎、config 异步 URL 推导、模型时间默认值、init_db create_all、conftest 适配）完成
- 2026-08-22：P2.1-P2.6 全模块路由与服务 async 化完成，129 测试全绿
- 2026-08-23：P3.1 + P3.4 KB 数据 ORM 化完成
  - 新增 `app/models/kb.py`：KbDocument / KbEvidenceUnit / KbKnowledgeEntry / KbQuarantine 四表入业务库
    （KbDocument.row_id 与 KbKnowledgeEntry.entry_id 自增主键承接源库 rowid，
    保持 exam 文档出题寻址与 topic 选取顺序语义）
  - 新增 `scripts/migrate_kb_data.py`：transport_safety_kb.sqlite3 四表 → 业务库 kb_* 表（先删后插幂等），
    本地 app.db 已迁移（124 文档 / 2008 证据 / 2008 知识条目 / 0 隔离）
  - rag.py `read_evidence` 改 ORM 查询（过滤规则与返回字段逐项对齐原 SQL，脚本验证 2008 条字段零差异）
  - exam_service `_read_document_text` 改 ORM（row_id 寻址）
  - 测试改造：test_rag.py 两个 read_evidence 测试改 ORM 造数；test_ai.py read_evidence 非空测试改 ORM 造数
  - 全量 pytest 129 条通过；原 transport_safety_kb.sqlite3 保留只读备份
- 待办：P3.2（rag.py `_load_rag_config` 的 sqlite3 直连改 ORM + retrieve 链路 async 化）、P3.3（AsyncOpenAI）、P4、P5
- 2026-08-23（续）：P3.2 + P3.3 完成
  - P3.2：rag.py `_load_rag_config` 改 ORM（RagConfig + SessionLocal，跟随 DATABASE_URL；
    原 sqlite3 直连硬编码 app.db 路径，测试环境读不到测试库）。
    rag.py 中 sqlite3 直连已清零。retrieve 链路保持 run_in_threadpool 桥接：
    内部全是同步 CPU/本地 IO（embedding 推理、BM25、Chroma 同步客户端），
    线程池即最终形态，改 async 仅是语法糖，不做
  - P3.3：llm.py OpenAI → AsyncOpenAI，stream_chat 改 async generator；
    ai_chat.stream_answer 改 `async for` 消费（删除 _STREAM_END 哨兵与线程池逐 token 拉取）；
    exam_service `_call_llm_sync` → `_call_llm`（async，去掉线程池包装）；
    vision.py 多模态调用保持线程池桥接（非流式单次请求，功能等价）
  - 测试适配：test_ai.py / test_exam.py 共 4 处 stream_chat mock 改 async generator
  - 全量 pytest 129 条通过
- 待办：P4（main.py 后台任务 asyncio 化、删除 sync 引擎）、P5（数据迁移 PG）
- 2026-08-23（续 2）：P4 完成
  - main.py：_urge_loop / _preload_models 改 asyncio 原生任务（lifespan 中 create_task + cancel）
  - base.py：删除 sync engine/SessionLocal/get_db，get_db_async 改名 get_db（全库唯一异步引擎）
  - deps.py 删同步鉴权；permissions.py 删同步 require_roles；model_eval_service 异步化（评测 worker 线程内 asyncio.run）
  - conftest：测试造数/断言改走私有测试引擎 _TestSessionLocal（同步，指向同一 test.db）
  - 修复 8 个 API 文件共 60+ 处 GBK 编码损坏（_fix_encoding.py 字节级替换 + py_compile 校验），
    修复脚本曾误给 knowledge.py 的 APIRouter 行加尾逗号（router 变 tuple），已纠正；
    test_exam.py 的 _read_document_text mock 改 async
  - 全量 pytest 129 条通过
- 2026-08-23（续 3）：P5 完成，生产库正式切换 PostgreSQL
  - 新增 scripts/migrate_sqlite_to_pg.py：create_all 建表 → sorted_tables 逆序清空/正序回填（单事务幂等）
    → 自增主键 setval 校正序列 → 源/目标行数核对清单
  - 数据迁移结果：36 张 ORM 表全部一致（含 kb_documents 124 / kb_evidence_units 2008 /
    kb_knowledge_entries 2008 / ai_test_items 1200）；exam_answers / exam_attempts 为
    schema.sql 时代遗留死表（app/tests/scripts 零引用），跳过不迁移，数据仍留在 app.db 备份中
  - .env 增加 DATABASE_URL=postgresql+asyncpg://postgres:***@localhost:5432/shudao；
    测试不受影响（conftest 环境变量优先级高于 .env，仍走临时 SQLite），129 条 pytest 复跑全绿
  - 冒烟验证（uvicorn + PG）：登录（写 auth_sessions）、用户列表（role 关系加载）、
    AI 会话列表、题目分类、隐患列表全部通过
  - transport_safety_kb.sqlite3 更名 .bak（只读备份）；app.db 保留作为 SQLite 全量备份
- 2026-08-23：全部阶段（P0–P5）完成
