# 认证会话持久化与 30 分钟空闲自动登出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将进程内 Token 黑名单替换为 SQLite `auth_sessions` 会话表，并实现 30 分钟无操作自动失效。

**Architecture:** 每次登录创建服务端会话，记录 access/refresh token 的 jti、最后活动时间、过期时间和吊销时间。鉴权依赖读取会话判断有效性；refresh 使用 token rotation。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, SQLite, python-jose, pytest。

## Global Constraints

- 项目根目录：`D:\实习\shudao\test\project-root`
- 测试环境：`D:\Anaconda\envs\shixi\python.exe`
- 统一认证错误码：未认证、Token 无效、会话过期、空闲超时均返回 `40100`
- 允许同一账号多端登录
- refresh 旋转并立即吊销旧 refresh token
- 时间格式：ISO 8601 字符串

---

### Task 1: 保存计划文档

**Files:**
- Create: `docs/superpowers/plans/2026-08-16-auth-session-persistence.md`

- [x] **Step 1: 创建计划文档**
- [x] **Step 2: 确认文档内容与执行计划一致**

---

### Task 2: 添加失败测试

**Files:**
- Modify: `backend/tests/test_auth.py`
- Modify: `backend/tests/test_user_management.py`

**Interfaces:**
- Consumes: 现有 `client`, `auth_headers`, `db` fixtures
- Produces: 新的失败测试覆盖会话持久化、空闲超时、多端登录、refresh rotation、cleanup

- [ ] **Step 1: 写失败测试**
- [ ] **Step 2: 运行并确认测试因缺失 `auth_sessions` 表或新接口而失败**
- [ ] **Step 3: 暂不提交，等待实现**

---

### Task 3: 添加 auth_sessions 表和 ORM

**Files:**
- Modify: `database/schema.sql`
- Create: `backend/app/models/auth_session.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `AuthSession` ORM，表 `auth_sessions`

- [ ] **Step 1: 在 schema.sql 添加建表语句和索引**
- [ ] **Step 2: 创建 AuthSession ORM**
- [ ] **Step 3: 在 models/__init__.py 导出**
- [ ] **Step 4: 运行测试确认表创建**

---

### Task 4: 更新 Token 签发与认证服务

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/services/auth_service.py`

**Interfaces:**
- Produces:
  - `create_refresh_token(subject) -> tuple[str, str]`
  - `login(db, username, password) -> dict`
  - `logout(db, jti) -> None`
  - `refresh(db, refresh_token) -> dict`
  - `get_active_session_by_access_jti(db, jti) -> AuthSession`
  - `get_active_session_by_refresh_jti(db, refresh_jti) -> AuthSession`
  - `touch_session(db, session) -> None`
  - `cleanup_expired_sessions(db) -> int`

- [ ] **Step 1: 修改 refresh token 签发，返回 token 与 jti**
- [ ] **Step 2: 用 auth_sessions 替换内存黑名单**
- [ ] **Step 3: 实现 login/refresh/logout 会话读写**
- [ ] **Step 4: 实现空闲超时、活动续期和 cleanup**
- [ ] **Step 5: 运行认证相关测试**

---

### Task 5: 接入鉴权依赖和后台清理

**Files:**
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `auth_service.get_active_session_by_access_jti`, `touch_session`, `cleanup_expired_sessions`
- Produces: 所有受保护接口自动检查会话有效性、空闲超时，并续期

- [ ] **Step 1: 更新 get_auth_context 查询 auth_sessions**
- [ ] **Step 2: 更新 logout 路由传入 db**
- [ ] **Step 3: 在 main.py 后台循环调用 cleanup**
- [ ] **Step 4: 运行相关测试**

---

### Task 6: 全量回归

**Files:**
- None

- [ ] **Step 1: 运行 `pytest tests/ -q`**
- [ ] **Step 2: 确认 73+ 新增测试全部通过**
- [ ] **Step 3: 检查数据库和代码一致性**

---

## Self-Review

- 覆盖检查：空闲超时、持久化吊销、多端登录、refresh rotation、cleanup 均有测试。
- 占位符检查：无 TBD。
- 类型一致性：`jti`、`AuthSession`、`db` 参数在各任务中保持一致。
