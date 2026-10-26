# 隐患管理模块（后端）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `project-root` 后端完成隐患管理模块（H01–H09），含隐患生命周期、统计、通知、真实大模型视觉识别与 OpenCV 标注。

**Architecture:** 沿用现有 FastAPI + SQLAlchemy 2.0 + SQLite 分层结构（core/schemas/models/services/api）。认证从内存 Mock 切换到 `users` 表；新增 RBAC 数据范围控制；H09 通过 OpenAI 兼容接口调用多模态模型并用 OpenCV+Pillow 画框。

**Tech Stack:** FastAPI、SQLAlchemy 2.0、SQLite、python-jose(JWT)、passlib(BCrypt)、openai、opencv-python、numpy、Pillow、python-dotenv、apscheduler、pytest。

## Global Constraints

- 项目根目录：`D:\实习\shudao\test\project-root`（下文相对路径均相对此目录）。
- 统一响应：`{code, message, data, timestamp}`；成功 `code=0`。
- 认证：JWT，access 2h + refresh；登录以外接口需 `Authorization: Bearer <token>`。
- 角色：`Admin` / `SafetyOfficer` / `Employee`。
- 安全员管辖范围 = `hazard.project == 当前用户.project`；管理员全局；普通员工仅本人数据。
- 隐患编号：`HD-YYYYMMDD-XXXX`，当日递增。
- 状态机：`pending → processing → pending_review → closed/rejected`；`rejected` 可由被指派员工重新整改回到 `pending_review`。
- 时间格式：ISO 8601 字符串（如 `2026-08-12T10:30:00+08:00`）。
- 布尔：INTEGER 0/1；JSON 字段存 JSON 文本。
- 测试环境：`D:\Anaconda\envs\shixi\python.exe`，运行命令统一为：
  `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; $env:PYTHONDONTWRITEBYTECODE="1"; & 'D:\Anaconda\envs\shixi\python.exe' -m pytest backend/tests/ -p no:cacheprovider -q`
- Git：`project-root` 文件当前未被 git 跟踪，且位于用户大仓库内。**提交步骤为可选**，默认只提交 `project-root` 下的具体文件，执行前请与用户确认；不提交也不影响功能。
- 每个任务遵循 TDD：先写失败测试并确认失败，再写最小实现，确认通过。

---

### Task 0: 基础配置、依赖与 `.env`

**Files:**
- Create: `.env`
- Modify: `backend/app/core/config.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `settings.VISULIZATION_API_KEY: str`、`settings.VISULIZATION_BASE_URL: str`、`settings.VISULIZATION_MODEL_NAME: str`、`settings.UPLOAD_DIR: str`、`settings.MAX_HAZARD_IMAGES: int`、`settings.MAX_IMAGE_SIZE_MB: int`；`settings` 从 `project-root/.env` 读取。

- [ ] **Step 1: 创建 `.env`（凭据留空）**

```bash
echo "" > .env
```

写入以下内容（UTF-8）：

```text
# 视觉大模型（OpenAI 兼容接口）；留空则 /hazards/ai-detect 返回 40203
VISULIZATION_API_KEY=
VISULIZATION_BASE_URL=
VISULIZATION_MODEL_NAME=
```

- [ ] **Step 2: 扩展 `config.py`**

在 `_PROJECT_ROOT` 已定义的前提下，修改 `model_config` 与新增字段：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ...现有字段不变...

    # 视觉大模型（OpenAI 兼容接口）
    VISULIZATION_API_KEY: str = ""
    VISULIZATION_BASE_URL: str = ""
    VISULIZATION_MODEL_NAME: str = ""

    # 上传
    UPLOAD_DIR: str = str(_PROJECT_ROOT / "uploads")
    MAX_HAZARD_IMAGES: int = 9
    MAX_IMAGE_SIZE_MB: int = 20


settings = Settings()
```

- [ ] **Step 3: 更新 `requirements.txt`**

追加：

```text
openai>=1.0.0
opencv-python>=4.8.0
numpy>=1.26.0
Pillow>=10.0.0
python-dotenv>=1.0.0
apscheduler>=3.10.0
```

- [ ] **Step 4: 验证**

Run: `& 'D:\Anaconda\envs\shixi\python.exe' -c "from app.core.config import settings; print(settings.VISULIZATION_API_KEY, settings.UPLOAD_DIR)"`
Expected: 打印空字符串与 `.../project-root/uploads`。

- [ ] **Step 5: 提交（可选）**

```bash
git add .env backend/app/core/config.py backend/requirements.txt
git commit -m "chore: add AI vision config and upload settings"
```

---

### Task 1: 统一错误码 + 修复既有认证测试

**Files:**
- Modify: `backend/app/core/response.py`
- Modify: `backend/tests/test_auth.py`

**Interfaces:**
- Produces: `ErrorCode` 新增 `FORBIDDEN=(40303,...)`、`NOT_FOUND=(40401,...)`、`AI_UNAVAILABLE=(40203,...)`、以及 40004~40011 业务码。

- [ ] **Step 1: 在 `response.py` 补齐错误码**

```python
class ErrorCode:
    # 认证
    BAD_CREDENTIALS = (40101, "用户名或密码错误", 401)
    ACCOUNT_DISABLED = (40102, "账户已被禁用", 401)
    REFRESH_TOKEN_INVALID = (40103, "refresh_token 无效或已过期", 401)
    OLD_PASSWORD_ERROR = (40104, "旧密码错误", 400)
    UNAUTHORIZED = (40100, "未认证或 Token 过期", 401)
    TOKEN_INVALID = (40100, "Token 无效", 401)
    VALIDATION_FAILED = (40001, "参数校验失败", 400)

    # 隐患业务
    STATUS_NOT_ASSIGNABLE = (40004, "隐患状态不允许派单", 400)
    INVALID_DEADLINE = (40005, "整改截止日期不合法", 400)
    CRITICAL_DEADLINE = (40006, "重大隐患整改期限不得超过 7 天", 400)
    STATUS_NOT_RECTIFIABLE = (40007, "隐患状态不允许提交整改", 400)
    MEASURES_TOO_SHORT = (40008, "整改描述不足 20 字", 400)
    NO_RECTIFY_IMAGES = (40009, "未上传整改后照片", 400)
    STATUS_NOT_REVIEWABLE = (40010, "隐患状态不允许验收", 400)
    REJECT_NEEDS_REASON = (40011, "驳回时必须填写原因（≥10 字）", 400)

    # AI / 权限 / 资源
    AI_UNAVAILABLE = (40203, "AI 服务暂不可用", 503)
    HAZARD_FORBIDDEN = (40301, "无权查看该隐患", 403)
    NOT_ASSIGNEE = (40302, "非被指派人无权操作", 403)
    FORBIDDEN = (40303, "角色无此功能权限", 403)
    HAZARD_NOT_FOUND = (40401, "隐患不存在", 404)
```

- [ ] **Step 2: 修正 `test_auth.py` 的 4 处期望码**

把 `test_me_without_token`、`test_me_invalid_token`、`test_logout_without_token`、`test_token_invalid_after_logout` 中的断言从 40104/40105 改为 40100（注释同步改为 40100）。

- [ ] **Step 3: 运行测试确认全绿**

Run 全局测试命令。
Expected: `test_auth.py` 12 用例全部通过。

- [ ] **Step 4: 提交（可选）**

```bash
git add backend/app/core/response.py backend/tests/test_auth.py
git commit -m "fix: unify auth error code to 40100 and align tests"
```

---

### Task 2: 预置用户 + 认证切换到数据库

**Files:**
- Modify: `database/init_data.sql`
- Modify: `backend/app/core/database.py`
- Modify: `backend/app/models/user_orm.py`
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Produces:
  - `User.to_info() -> dict`（含 `id/username/name/role/department/project`，`role` 取 `self.role.name`）。
  - `auth_service.login(db, username, password) -> dict`
  - `auth_service.logout(jti) -> None`、`is_token_revoked(jti) -> bool`
  - `get_auth_context(request, db=Depends(get_db)) -> AuthContext`（Task 3 定义 AuthContext，本任务先返回一个含 `user` 与 `jti` 的中间结构；随后在 Task 3 定型）。

- [ ] **Step 1: 更新 `init_data.sql` 为幂等预置**

使用 `INSERT OR IGNORE`，密码哈希统一为 `Abc@123456` 的 BCrypt 哈希：

```sql
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO roles (role_id, name, description) VALUES
  (1, 'Admin', '系统管理员，拥有最高权限'),
  (2, 'SafetyOfficer', '安全员，管辖范围内的隐患和考试管理'),
  (3, 'Employee', '普通员工，仅可操作本人数据');

INSERT OR IGNORE INTO users
  (user_id, username, password_hash, name, role_id, department, project, phone, is_active)
VALUES
  ('U001', 'admin', '$2b$12$kn6XSw.u2EsAtCsVHdGUaeWbX60gfxM77XVgrPqzwUiSjNj2B8WiG', '系统管理员', 1, '信息中心', '蜀道集团总部', NULL, 1),
  ('U002', 'zhangsan', '$2b$12$kn6XSw.u2EsAtCsVHdGUaeWbX60gfxM77XVgrPqzwUiSjNj2B8WiG', '张三', 2, '安全生产部', '成绵高速扩容项目', NULL, 1),
  ('U003', 'lisi', '$2b$12$kn6XSw.u2EsAtCsVHdGUaeWbX60gfxM77XVgrPqzwUiSjNj2B8WiG', '李四', 3, '工程部', '绵九高速项目', NULL, 1),
  ('U004', 'wangwu', '$2b$12$kn6XSw.u2EsAtCsVHdGUaeWbX60gfxM77XVgrPqzwUiSjNj2B8WiG', '王五', 3, '工程部', '绵九高速项目', NULL, 0);
```

- [ ] **Step 2: `database.py` 改为始终执行 `init_data.sql`**

去掉“仅当 roles 为空才执行”的分支，直接：

```python
if INIT_DATA_SQL_PATH.is_file():
    raw_conn.executescript(INIT_DATA_SQL_PATH.read_text(encoding="utf-8"))
```

- [ ] **Step 3: `user_orm.py` 增加 `to_info()`**

```python
def to_info(self) -> dict:
    return {
        "id": self.user_id,
        "username": self.username,
        "name": self.name,
        "role": self.role.name if self.role else "",
        "department": self.department,
        "project": self.project,
    }
```

- [ ] **Step 4: 写失败测试**

`backend/tests/test_auth.py` 增加：

```python
def test_login_reads_from_db(client):
    resp = client.post(f"{API}/auth/login", json={"username": "admin", "password": "Abc@123456"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["role"] == "Admin"
    assert data["user"]["department"] == "信息中心"
```

先运行确认失败（若旧 Mock 里 admin 存在则不会失败；因此 Step 5 移除 Mock 后必须再确认）。

- [ ] **Step 5: 改 `auth_service.login` 走 DB**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user_orm import User

def login(db: Session, username: str, password: str) -> dict:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise BizError(*ErrorCode.BAD_CREDENTIALS)
    if not user.is_active:
        raise BizError(*ErrorCode.ACCOUNT_DISABLED)
    access_token, _jti = create_access_token(user.user_id, extra={"role": user.role.name if user.role else ""})
    refresh_token = create_refresh_token(user.user_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_info(),
    }
```

`auth.py` 路由改为 `def login(req: LoginRequest, db: Session = Depends(get_db)):` 并传入 `db`。

- [ ] **Step 6: `deps.py` 鉴权走 DB（先返回中间结构）**

```python
def get_auth_context(request: Request, db: Session = Depends(get_db)):
    token = _extract_bearer(request)
    try:
        payload = decode_token(token)
    except JWTError:
        raise BizError(*ErrorCode.TOKEN_INVALID)
    if payload.get("type") != "access":
        raise BizError(*ErrorCode.TOKEN_INVALID)
    jti = payload.get("jti")
    if auth_service.is_token_revoked(jti):
        raise BizError(*ErrorCode.TOKEN_INVALID)
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise BizError(*ErrorCode.TOKEN_INVALID)
    from dataclasses import dataclass
    @dataclass
    class AuthContext:
        user: User
        jti: str
    return AuthContext(user=user, jti=jti)
```

同步更新 `auth.py` 的 `me`/`logout` 使用 `ctx.user.to_info()`。

- [ ] **Step 7: `conftest.py` 每个测试前重建数据**

```python
@pytest.fixture()
def client():
    from app.core.database import init_db
    init_db()
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 8: 运行测试**

Expected: `test_auth.py` 全绿；`users` 表有 4 行。

- [ ] **Step 9: 提交（可选）**

```bash
git add database/init_data.sql backend/app/core/database.py backend/app/models/user_orm.py backend/app/services/auth_service.py backend/app/api/deps.py backend/app/api/v1/auth.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "feat: seed users and switch auth to database"
```

---

### Task 3: RBAC 权限与数据范围

**Files:**
- Create: `backend/app/core/permissions.py`
- Modify: `backend/app/api/deps.py`

**Interfaces:**
- Produces:
  - `AuthContext`（dataclass：`user_id, username, name, role, department, project, jti`）。
  - `get_auth_context(request, db=Depends(get_db)) -> AuthContext`
  - `require_roles(*roles: str)`（FastAPI 依赖工厂，不满足抛 40303）。
  - `can_view_hazard(ctx, hazard) -> bool`、`can_manage_hazard(ctx, hazard) -> bool`、`is_assignee(ctx, hazard) -> bool`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_permissions.py`：

```python
def test_employee_cannot_manage_others_hazard(client):
    # 先用 Employee 登录；通过一个受 require_roles("Admin","SafetyOfficer") 保护的占位接口验证 40303
    ...
```

> 为避免依赖未实现的隐患接口，本任务测试以 `require_roles` 保护一个临时 `/auth/me/admin-only` 路由，验证 Employee 返回 40303。实现后在 Task 4+ 被真实接口覆盖。

- [ ] **Step 2: 定义 `AuthContext` 并改造 `get_auth_context`**

```python
@dataclass
class AuthContext:
    user_id: str
    username: str
    name: str
    role: str
    department: str
    project: str
    jti: str
```

`get_auth_context` 返回 `AuthContext(user_id=user.user_id, username=user.username, name=user.name, role=user.role.name if user.role else "", department=user.department, project=user.project, jti=jti)`。

- [ ] **Step 3: 实现 `permissions.py`**

```python
from fastapi import Depends
from app.api.deps import AuthContext, get_auth_context
from app.core.response import BizError, ErrorCode

def require_roles(*roles: str):
    def dep(ctx: AuthContext = Depends(get_auth_context)):
        if ctx.role not in roles:
            raise BizError(*ErrorCode.FORBIDDEN)
        return ctx
    return dep

def can_view_hazard(ctx, hazard) -> bool:
    if ctx.role == "Admin":
        return True
    if ctx.role == "SafetyOfficer":
        return hazard.project == ctx.project
    return hazard.reporter_id == ctx.user_id

def can_manage_hazard(ctx, hazard) -> bool:
    return ctx.role in ("Admin", "SafetyOfficer") and (
        ctx.role == "Admin" or hazard.project == ctx.project
    )

def is_assignee(ctx, hazard) -> bool:
    if not hazard.assignments:
        return False
    latest = sorted(hazard.assignments, key=lambda a: a.created_at)[-1]
    return latest.assignee_id == ctx.user_id
```

- [ ] **Step 4: 运行测试确认通过**

- [ ] **Step 5: 提交（可选）**

```bash
git add backend/app/core/permissions.py backend/app/api/deps.py backend/tests/test_permissions.py
git commit -m "feat: add RBAC role and data-scope checks"
```

---

### Task 4: 隐患编号生成

**Files:**
- Create: `backend/app/services/idgen.py`
- Test: `backend/tests/test_hazards.py`

**Interfaces:**
- Produces: `generate_hazard_id(db) -> str`

- [ ] **Step 1: 写失败测试**

```python
from app.services.idgen import generate_hazard_id

def test_generate_hazard_id_format(db):
    hid = generate_hazard_id(db)
    assert hid.startswith("HD-")
    assert len(hid) == 17  # HD-YYYYMMDD-XXXX
```

- [ ] **Step 2: 实现**

```python
import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

def generate_hazard_id(db: Session) -> str:
    prefix = f"HD-{datetime.date.today():%Y%m%d}-"
    row = db.execute(text("SELECT MAX(hazard_id) FROM hazards WHERE hazard_id LIKE :p"), {"p": prefix + "%"}).scalar()
    seq = int(row.rsplit("-", 1)[-1]) + 1 if row else 1
    return f"{prefix}{seq:04d}"
```

- [ ] **Step 3: 运行测试确认通过**

- [ ] **Step 4: 提交（可选）**

```bash
git add backend/app/services/idgen.py backend/tests/test_hazards.py
git commit -m "feat: add hazard id generator"
```

---

### Task 5: H01 隐患上报

**Files:**
- Create: `backend/app/schemas/hazard.py`
- Create: `backend/app/services/hazard_service.py`
- Create: `backend/app/api/v1/hazards.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_hazards.py`

**Interfaces:**
- Consumes: `AuthContext`, `generate_hazard_id`, `notification_service.create_notification`（Task 11 实现；本任务先调用一个 `create_notification` 占位并在 Task 11 补全）。
- Produces: `hazard_service.create_hazard(db, ctx, data, files) -> Hazard`

- [ ] **Step 1: 写失败测试**

```python
def test_report_hazard_creates_pending(client, auth_headers):
    files = [("images", ("a.jpg", b"fake-bytes", "image/jpeg"))]
    data = {
        "title": "临边防护缺失",
        "description": "桥墩施工区域临边护栏缺失约5米",
        "level": "major",
        "category": "edge_protection",
        "location": "K12+350",
        "occurred_at": "2026-08-12T09:30:00+08:00",
        "project": "成绵高速扩容项目",
    }
    resp = client.post(f"{API}/hazards", data=data, files=files, headers=auth_headers("zhangsan"))
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "pending"
    assert body["hazard_id"].startswith("HD-")
```

- [ ] **Step 2: 实现 Schema（仅本任务所需字段）**

```python
class HazardCreate(BaseModel):
    title: str
    description: str
    level: str
    category: str
    location: str
    location_coords: str | None = None
    occurred_at: str
    project: str
```

- [ ] **Step 3: 实现 `create_hazard`**

要点：生成编号、保存图片到 `settings.UPLOAD_DIR/hazards/{hazard_id}/`、写 `Hazard` + `HazardMedia`(context=report) + `HazardTimeline`(reported)、向同 `project` 的安全员发 `hazard_assigned` 通知占位、返回 hazard。

```python
def create_hazard(db, ctx, data, files):
    hazard_id = generate_hazard_id(db)
    hazard = Hazard(hazard_id=hazard_id, reporter_id=ctx.user_id, status="pending", **data.model_dump(exclude={"location_coords"}))
    if data.location_coords:
        hazard.location_coords = data.location_coords
    db.add(hazard)
    db.flush()
    # 保存文件、写 media、写 timeline
    ...
    db.commit()
    db.refresh(hazard)
    # 通知辖区安全员（Task 11 之前可用直接 insert 占位）
    return hazard
```

- [ ] **Step 4: 路由**

```python
@router.post("", summary="隐患上报")
def report_hazard(
    title: str = Form(...), description: str = Form(...), level: str = Form(...),
    category: str = Form(...), location: str = Form(...),
    location_coords: str | None = Form(None), occurred_at: str = Form(...),
    project: str = Form(...), images: list[UploadFile] = File(default=[]),
    ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db),
):
    ...
```

- [ ] **Step 5: 运行测试确认通过**

- [ ] **Step 6: 提交（可选）**

---

### Task 6: H02 隐患列表

**Files:** Modify `backend/app/schemas/hazard.py`、`backend/app/services/hazard_service.py`、`backend/app/api/v1/hazards.py`；Test `backend/tests/test_hazards.py`

**Interfaces:**
- Produces: `hazard_service.list_hazards(db, ctx, params) -> dict`（`items,total,page,page_size,total_pages`）

- [ ] **Step 1: 写失败测试**：Employee 只能看到本人上报；SafetyOfficer 只看同 project；支持 `status/level/category/project/keyword/date_from/date_to/sort_by/sort_order` 筛选。
- [ ] **Step 2: 实现查询**：按 `can_view_hazard` 拼 `where` 条件，分页返回摘要（`hazard_id,title,level,status,category,reporter_name,project,created_at,thumbnail_url`）。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 7: H03 隐患详情

**Files:** Modify `backend/app/schemas/hazard.py`、`backend/app/services/hazard_service.py`、`backend/app/api/v1/hazards.py`；Test `backend/tests/test_hazards.py`

**Interfaces:**
- Produces: `hazard_service.get_hazard(db, ctx, hazard_id) -> dict`（基本字段 + media + detections + timeline + assignment + rectification + review）

- [ ] **Step 1: 写失败测试**：无权限返回 40301；不存在返回 40401；存在返回完整详情。
- [ ] **Step 2: 实现**：加载 hazard 及 `media/assignments/rectifications/reviews/timeline`，按 `can_view_hazard` 校验。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 8: H04 隐患派单

**Files:** Modify `backend/app/schemas/hazard.py`、`backend/app/services/hazard_service.py`、`backend/app/api/v1/hazards.py`；Test `backend/tests/test_hazards.py`

**Interfaces:**
- Produces: `hazard_service.assign_hazard(db, ctx, hazard_id, req) -> Hazard`

- [ ] **Step 1: 写失败测试**：仅 Admin/SafetyOfficer 可派单；状态非 pending 返回 40004；deadline 早于今天返回 40005；critical 且 deadline 超过 7 天返回 40006；成功后状态为 processing 并向被指派人发通知。
- [ ] **Step 2: 实现**：校验 `can_manage_hazard` + 状态 + 期限；写 `HazardAssignment`、`hazard.status="processing"`、`HazardTimeline(assigned)`、`notification(hazard_assigned)`。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 9: H05 整改反馈

**Files:** Modify `backend/app/schemas/hazard.py`、`backend/app/services/hazard_service.py`、`backend/app/api/v1/hazards.py`；Test `backend/tests/test_hazards.py`

**Interfaces:**
- Produces: `hazard_service.rectify_hazard(db, ctx, hazard_id, req, files) -> Hazard`

- [ ] **Step 1: 写失败测试**：状态非 processing/rejected 返回 40007；measures<20 返回 40008；无整改后照片返回 40009；非被指派人返回 40302；成功后状态为 pending_review 并通知派单人。
- [ ] **Step 2: 实现**：校验 `is_assignee`（Employee）/`can_manage_hazard`（Admin/SafetyOfficer）+ 状态；写 `HazardRectification`、`status="pending_review"`、`timeline(rectified)`、`notification(rectification_submitted)`。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 10: H06 隐患验收

**Files:** Modify `backend/app/schemas/hazard.py`、`backend/app/services/hazard_service.py`、`backend/app/api/v1/hazards.py`；Test `backend/tests/test_hazards.py`

**Interfaces:**
- Produces: `hazard_service.review_hazard(db, ctx, hazard_id, req) -> Hazard`

- [ ] **Step 1: 写失败测试**：状态非 pending_review 返回 40010；驳回无原因/原因<10 返回 40011；approve→closed，reject→rejected；发送 `review_result` 通知。
- [ ] **Step 2: 实现**：校验 `can_manage_hazard` + 状态；写 `HazardReview`、`status=closed/rejected`、`timeline(reviewed)`、`notification(review_result)`。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 11: H08 通知 CRUD + 自动通知

**Files:**
- Create: `backend/app/schemas/notification.py`
- Create: `backend/app/services/notification_service.py`
- Create: `backend/app/api/v1/notifications.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_notifications.py`

**Interfaces:**
- Produces: `create_notification`, `list_notifications`, `unread_count`, `mark_read`, `mark_all_read`, `delete_notification`, `batch_delete`。

- [ ] **Step 1: 写失败测试**：列表按未读置顶/时间倒序、`read_status/type/category` 筛选；未读数按分类/类型；标记已读/全部已读/单删/批删。
- [ ] **Step 2: 实现**：用 `Notification` ORM；`create_notification` 被 Task 5/8/9/10 调用（替换占位）。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 12: H08 整改催办调度

**Files:** Create `backend/app/services/scheduler.py`（或并入 notification_service）；Modify `backend/app/main.py`；Test `backend/tests/test_notifications.py`

**Interfaces:**
- Produces: `send_due_urge_notifications(db)`

- [ ] **Step 1: 写失败测试**：对 `processing` 状态、截止在 24h 内且无反馈的隐患，向被指派人发 `rectification_urge`；同一隐患 24h 内不重复。
- [ ] **Step 2: 实现**：查询条件 + `rectification_urge` 通知；APScheduler `CronTrigger(hour="*", minute=0)` 每小时跑一次，在 `lifespan` 启动/关闭。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 13: H07 隐患统计

**Files:** Create `backend/app/schemas/statistics.py`、`backend/app/services/statistics_service.py`、`backend/app/api/v1/statistics.py`；Modify `router.py`；Test `backend/tests/test_statistics.py`

**Interfaces:**
- Produces: `hazard_overview`, `hazard_trend`, `closure_ranking`

- [ ] **Step 1: 写失败测试**：overview 的 total/各状态计数/closure_rate/avg_closure_hours/level_distribution/category_distribution 正确；trend 按日聚合；closure-ranking 按 project/officer 分组。
- [ ] **Step 2: 实现**：SQL 聚合；SafetyOfficer 只统计本 project；Employee 返回 40303。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 14: 用户列表（派单选人）

**Files:** Create `backend/app/api/v1/users.py`；Modify `router.py`；Test `backend/tests/test_hazards.py`

**Interfaces:**
- Produces: `GET /users`（Admin 全部；SafetyOfficer 本 project；支持 keyword/department/project 筛选）

- [ ] **Step 1: 写失败测试**：Admin 看到全部；SafetyOfficer 只看到同 project；Employee 返回 40303。
- [ ] **Step 2: 实现**：查询 `users` 并返回 `to_info()` 列表（分页）。
- [ ] **Step 3: 运行测试确认通过**
- [ ] **Step 4: 提交（可选）**

---

### Task 15: H09 AI 识别 + OpenCV 画框

**Files:**
- Create: `backend/app/services/vision.py`
- Create: `backend/app/services/annotator.py`
- Modify: `backend/app/api/v1/hazards.py`
- Modify: `backend/app/main.py`（挂载 `/uploads` 静态目录）
- Test: `backend/tests/test_vision.py`

**Interfaces:**
- Produces:
  - `AiVisionService().is_configured() -> bool`
  - `AiVisionService().detect(image_path: Path, title: str | None = None, description: str | None = None) -> list[dict]`
  - `annotator.annotate(image_path: Path, items: list[dict], output_path: Path) -> list[dict]`

- [ ] **Step 1: 写失败测试（mock OpenAI client）**

```python
def test_detect_not_configured_returns_40203(client, auth_headers):
    # settings.VISULIZATION_API_KEY/BASE_URL/MODEL_NAME 为空时
    resp = client.post(f"{API}/hazards/ai-detect", files=[...], headers=auth_headers("zhangsan"))
    assert resp.json()["code"] == 40203

def test_annotate_draws_box(tmp_path, monkeypatch):
    from app.services.annotator import annotate
    # 生成一张 100x100 纯色图，传入 1 个 bbox_norm 检测项，验证输出文件存在且 drawn 含 bbox_px
```

- [ ] **Step 2: 实现 `annotator.py`**（从 `test/annotate_hazards.py` 适配，去掉 CLI，保留 `imread_unicode/imwrite_unicode/encode_image_data_url/extract_json_array/to_pixel_bbox/resolve_color/annotate`）

```python
def annotate(image_path: Path, items: list[dict], output_path: Path) -> list[dict]:
    image = imread_unicode(image_path)
    annotated, drawn = annotate_image(image, items)
    imwrite_unicode(output_path, annotated)
    return drawn
```

- [ ] **Step 3: 实现 `vision.py`**

```python
class AiVisionService:
    SYSTEM_PROMPT = (
        "你是施工安全隐患识别模型。请只输出 JSON 数组，每项字段为："
        "id(整数), label(字符串), risk(high/medium/low 之一), "
        "bbox_norm([x1,y1,x2,y2] 归一化 0~1), bbox_px([x1,y1,x2,y2] 像素，可省略), "
        "color_bgr([B,G,R]：high 红[0,0,255]、medium 橙[0,165,255]、low 绿[0,255,0]), "
        "conf(0~1), fix(整改建议), note(位置说明)。无隐患时输出 []。"
    )
    def is_configured(self) -> bool:
    return bool(settings.VISULIZATION_API_KEY and settings.VISULIZATION_BASE_URL and settings.VISULIZATION_MODEL_NAME)
    def detect(self, image_path, title=None, description=None) -> list[dict]:
        if not self.is_configured():
            raise BizError(*ErrorCode.AI_UNAVAILABLE)
        client = OpenAI(api_key=settings.VISULIZATION_API_KEY, base_url=settings.VISULIZATION_BASE_URL)
        raw = call_vision_api(client, settings.VISULIZATION_MODEL_NAME, self.SYSTEM_PROMPT, title, description, image_path)
        return extract_json_array(raw)
```

- [ ] **Step 4: 实现 `/hazards/ai-detect`**：逐图保存原图 → `detect` → `annotate` → 返回 `items[{image_index, original_url, annotated_url, detections}]`；未配置或异常返回 40203。
- [ ] **Step 5: `main.py` 挂载静态目录**

```python
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
```

- [ ] **Step 6: 运行测试确认通过**
- [ ] **Step 7: 提交（可选）**

---

### Task 16: 路由聚合 + 全量回归

**Files:** Modify `backend/app/api/v1/router.py`；确保 `main.py` 完成 `init_db`、静态挂载、调度器。

- [ ] **Step 1: `router.py` 聚合**

```python
from app.api.v1 import auth, hazards, notifications, statistics, users
api_router.include_router(auth.router)
api_router.include_router(hazards.router)
api_router.include_router(notifications.router)
api_router.include_router(statistics.router)
api_router.include_router(users.router)
```

- [ ] **Step 2: 运行全量测试**（全局命令）
Expected: 全部用例通过。

- [ ] **Step 3: 提交（可选）**

```bash
git add backend/app backend/tests
git commit -m "feat: complete hazard management module backend"
```

---

## Self-Review

- 覆盖检查：H01(T5)、H02(T6)、H03(T7)、H04(T8)、H05(T9)、H06(T10)、H07(T13)、H08(T11/T12)、H09(T15)、认证/权限(T1/T2/T3)、编号(T4)、派单选人(T14)、导出 PDF（明确跳过）。
- 占位符检查：无 TBD；跨任务接口名在 Interfaces 中定义并保持一致。
- 类型一致性：`AuthContext`、`generate_hazard_id`、`create_notification`、`hazard_service.*`、`annotate` 等签名前后一致。
