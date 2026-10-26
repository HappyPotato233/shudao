---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 619a68374c198f2d1dccd9a31deded68_333aedb5971511f180bf525400f8a581
    ReservedCode1: LjA8RDkQHU3c9KJviNbeIbg/yXgUrrCabGu1wd4Wh5Bd3lVIVc2A/cpNn36T4/Pid2MlPMVxIZ0DhjawNPDzEb+HidMnGYy0PZWMQWEe9t2Qy/B2qtMxW6iqWQbhpcJTQpLER6g7OuWZiqwk3REzqKTDx0Ryh4fA+EqxtYrlElTR536g3b6sz0C7A8w=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 619a68374c198f2d1dccd9a31deded68_333aedb5971511f180bf525400f8a581
    ReservedCode2: LjA8RDkQHU3c9KJviNbeIbg/yXgUrrCabGu1wd4Wh5Bd3lVIVc2A/cpNn36T4/Pid2MlPMVxIZ0DhjawNPDzEb+HidMnGYy0PZWMQWEe9t2Qy/B2qtMxW6iqWQbhpcJTQpLER6g7OuWZiqwk3REzqKTDx0Ryh4fA+EqxtYrlElTR536g3b6sz0C7A8w=
---

---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 619a68374c198f2d1dccd9a31deded68_67b21356961b11f181ac525400f8a581
    ReservedCode1: 2Z6/+YkMOF4njb/ZtsisP6ovf+U8LJ0ocDOmYszCwEQpWfNe63kUMrewt8NzSXydGJfh9aiwMAotlhm8kzTfBCPHVueem+Y2EsfJtoe3XX4Z14ygqxJO30/aVi8hVF3pNB7oprgFq2xZdgcG2DQM1pUzfZ3Oncw7GZ3QMFEbheD4q8+iIqyF/L9fk0Y=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 619a68374c198f2d1dccd9a31deded68_67b21356961b11f181ac525400f8a581
    ReservedCode2: 2Z6/+YkMOF4njb/ZtsisP6ovf+U8LJ0ocDOmYszCwEQpWfNe63kUMrewt8NzSXydGJfh9aiwMAotlhm8kzTfBCPHVueem+Y2EsfJtoe3XX4Z14ygqxJO30/aVi8hVF3pNB7oprgFq2xZdgcG2DQM1pUzfZ3Oncw7GZ3QMFEbheD4q8+iIqyF/L9fk0Y=
---

# 蜀道安全助手 — API 接口文档

> **项目名称**：蜀道安全助手  
> **文档版本**：V1.0  
> **编写日期**：2026-08-12  
> **基础路径**：`http://{host}:{port}/api/v1`  
> **内容格式**：`application/json`（除文件上传使用 `multipart/form-data`、SSE 流使用 `text/event-stream`外）  
> **认证方式**：Bearer Token（JWT），Header: `Authorization: Bearer <token>`

---

## 目录

- [1. 通用规范](#1-通用规范)
- [2. 认证与用户管理](#2-认证与用户管理)
- [3. 隐患安全管理](#3-隐患安全管理)
- [4. AI 智能助手](#4-ai-智能助手)
- [5. 考试工坊](#5-考试工坊)
- [6. 消息通知](#6-消息通知)
- [7. 统计分析](#7-统计分析)
- [8. 知识库管理](#8-知识库管理)
- [附录：错误码参考](#附录错误码参考)

---

## 1. 通用规范

### 1.1 请求格式

| 场景       | Content-Type                    |
| -------- | ------------------------------- |
| JSON 请求体 | `application/json`              |
| 文件上传     | `multipart/form-data`           |
| SSE 流式   | 客户端 Accept: `text/event-stream` |

### 1.2 统一响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "timestamp": 1692000000
}
```

| 字段          | 类型                    | 说明                   |
| ----------- | --------------------- | -------------------- |
| `code`      | int                   | 业务状态码，0 表示成功，非 0 为错误 |
| `message`   | string                | 状态描述                 |
| `data`      | object / array / null | 响应数据                 |
| `timestamp` | int                   | 响应时间戳（Unix 秒）        |

### 1.3 分页请求参数

| 参数          | 类型  | 默认值 | 说明                |
| ----------- | --- | --- | ----------------- |
| `page`      | int | 1   | 页码（从 1 开始）        |
| `page_size` | int | 20  | 每页条数（可选 10/20/50） |

### 1.4 分页响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "total": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  }
}
```

### 1.5 权限标识

接口标注所需角色：`Admin`（管理员）、`User`（普通用户）。未标注即所有已认证用户均可访问。

### 1.6 认证要求

除登录接口外，所有接口均需在 Header 中携带 JWT Token：

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Token 有效期 2 小时，过期后需通过刷新接口续期。30 分钟无操作自动登出。

---

## 2. 认证与用户管理

### 2.1 登录

```
POST /auth/login
```

**请求体**：

```json
{
  "username": "zhangsan",
  "password": "Abc@123456"
}
```

| 参数         | 类型     | 必填  | 说明                       |
| ---------- | ------ | --- | ------------------------ |
| `username` | string | 是   | 用户名或工号                   |
| `password` | string | 是   | 密码（≥ 8 位，含大小写字母+数字+特殊字符） |

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "expires_in": 7200,
    "user": {
      "id": "U001",
      "username": "zhangsan",
      "name": "张三",
      "role": "User",
      "department": "安全生产部",
      "project": "成绵高速扩容项目"
    }
  }
}
```

**错误码**：`40101` 用户名或密码错误、`40102` 账户已被禁用

---

### 2.2 刷新 Token

```
POST /auth/refresh
```

**请求体**：

```json
{
  "refresh_token": "eyJhbGciOi..."
}
```

**成功响应**：同 2.1 登录响应结构。

**错误码**：`40103` refresh_token 无效或已过期

---

### 2.3 退出登录

```
POST /auth/logout
```

**请求体**：无

**成功响应**：`{ "code": 0, "message": "已退出登录" }`

---

### 2.4 获取当前用户信息

```
GET /auth/me
```

**响应**：同 2.1 中 `user` 字段。

---

### 2.5 修改密码

```
PUT /auth/password
```

**请求体**：

```json
{
  "old_password": "Abc@123456",
  "new_password": "Xyz@654321"
}
```

**成功响应**：`{ "code": 0, "message": "密码修改成功" }`

**错误码**：`40104` 旧密码错误、`40001` 新密码不符合复杂度要求

---

### 2.6 用户列表

```
GET /users
```

> **角色**：Admin（全部）/ 普通用户（仅本 project）
>
> 说明：该接口同时用于隐患派单（H04）选择整改责任人。

**查询参数**：

| 参数           | 类型     | 必填  | 说明                              |
| ------------ | ------ | --- | ------------------------------- |
| `page`       | int    | 否   | 页码                              |
| `page_size`  | int    | 否   | 每页条数                            |
| `keyword`    | string | 否   | 用户名/姓名搜索                        |
| `department` | string | 否   | 按部门筛选                           |
| `project`    | string | 否   | 按项目筛选（普通用户固定限定本 project） |

**响应数据**：分页格式，`items` 为 `user` 对象数组（同 2.1 user 结构，不含 token）。

---

### 2.7 创建/编辑/删除用户（管理员）

| 方法       | 路径                 | 说明        |
| -------- | ------------------ | --------- |
| `POST`   | `/users`           | 创建用户      |
| `PUT`    | `/users/{user_id}` | 编辑用户信息    |
| `DELETE` | `/users/{user_id}` | 删除用户（软删除） |

> **角色**：Admin

**创建/编辑请求体**：

```json
{
  "username": "lisi",
  "name": "李四",
  "password": "Xyz@654321",
  "role": "User",
  "department": "工程部",
  "project": "绵九高速项目",
  "phone": "13800138000"
}
```

---

## 3. 隐患安全管理

### 3.1 隐患上报

```
POST /hazards
```

> **角色**：普通用户  
> **对应功能**：H01

**请求体**（`multipart/form-data`）：

| 参数                | 类型     | 必填                            | 说明                                                                                          |
| ----------------- | ------ | ----------------------------- | ------------------------------------------------------------------------------------------- |
| `title`           | string | 否                             | 隐患标题（≤ 100 字）                                                                               |
| `description`     | string | 否                             | 详细描述（≤ 2000 字）                                                                              |
| `level`           | string | 是                             | 隐患等级：`critical`（重大）/ `major`（较大）/ `minor`（一般）/ `trivial`（轻微）                                |
| `category`        | string | 是                             | 隐患类别：`height_work` / `edge_protection` / `machinery` / `fire_safety` / `temp_electricity` 等 |
| `location`        | string | 是                             | 发生位置描述                                                                                      |
| `location_coords` | string | 否                             | GPS 坐标（`"lng,lat"` 格式）                                                                      |
| `occurred_at`     | string | 是                             | 发生时间（ISO 8601）                                                                              |
| `project`         | string | 是 | 所属项目/标段                                                                                     |
| `images`          | file[] | 否                             | 现场照片（最多 9 张，单张最大 20MB）                                                                      |
| `detections_json` | string | 否 | AI 识别结果 JSON 数组（配合 `images` 使用），用于把检测结果与标注图保存进隐患；结构见 3.2 的 `items` |

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "hazard_id": "HD-20260812-0001",
    "status": "pending",
    "created_at": "2026-08-12T10:30:00+08:00"
  }
}
```

**错误码**：`40001` 参数校验失败、`40002` 图片数量超限

---

### 3.2 隐患 AI 识别

```
POST /hazards/ai-detect
```

> **角色**：普通用户
> **对应功能**：H09（H01 上传图片后自动触发）

**请求体**（`multipart/form-data`）：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `images` | file[] | 是 | 现场照片（最多 9 张，单张最大 20MB，不压缩） |
| `title` | string | 否 | 隐患标题（可选，辅助识别上下文） |
| `description` | string | 否 | 图片描述（可选，辅助识别上下文） |

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "image_index": 0,
        "original_url": "https://...",
        "annotated_url": "https://...",
        "detections": [
          {
            "id": 1,
            "label": "临边防护缺失",
            "risk": "high",
            "bbox_norm": [0.10, 0.22, 0.62, 0.78],
            "bbox_px": [120, 264, 744, 936],
            "color_bgr": [0, 0, 255],
            "conf": 0.92,
            "fix": "立即设置临时防护，安装正式护栏",
            "note": "3号桥墩东侧临边"
          }
        ]
      }
    ]
  }
}
```

**说明**：
- 每张图片独立识别，返回各自的原图 URL、标注图 URL 与检测结果 JSON。
- 无隐患检出时 `detections` 为空数组 `[]`，前端提示「未识别到明显隐患」。
- 识别接口异常时返回 `40203`，前端降级为普通图片上传，不阻塞上报。

**错误码**：`40002` 图片数量超限（最多 9 张）、`40203` AI 服务暂不可用

---

### 3.3 隐患列表

```
GET /hazards
```

> **对应功能**：H02  
> 仅普通用户可查看，且仅限本人上报的隐患

**查询参数**：

| 参数           | 类型     | 必填  | 说明                                                                               |
| ------------ | ------ | --- | -------------------------------------------------------------------------------- |
| `page`       | int    | 否   | 页码                                                                               |
| `page_size`  | int    | 否   | 每页条数（10/20/50）                                                                   |
| `status`     | string | 否   | 状态筛选：`pending` / `processing` / `pending_review` / `closed` / `rejected`，多选用逗号分隔 |
| `level`      | string | 否   | 等级筛选，多选用逗号分隔                                                                     |
| `category`   | string | 否   | 类别筛选                                                                             |
| `project`    | string | 否   | 项目筛选                                                                             |
| `keyword`    | string | 否   | 关键字搜索（标题/编号/描述）                                                                  |
| `date_from`  | string | 否   | 上报起始时间                                                                           |
| `date_to`    | string | 否   | 上报截止时间                                                                           |
| `sort_by`    | string | 否   | `created_at` 或 `urgency`，默认 `created_at`                                         |
| `sort_order` | string | 否   | `asc` / `desc`，默认 `desc`                                                         |

**响应数据**：分页格式，`items` 为 hazard 摘要对象数组：

```json
{
  "hazard_id": "HD-20260812-0001",
  "title": "3号桥墩临边防护缺失",
  "level": "major",
  "status": "pending",
  "category": "edge_protection",
  "reporter_name": "张三",
  "project": "成绵高速扩容项目",
  "created_at": "2026-08-12T10:30:00+08:00",
  "thumbnail_url": "https://..."
}
```

---

### 3.4 隐患详情

```
GET /hazards/{hazard_id}
```

> **对应功能**：H03  
> 权限同 3.3

**响应数据**：

```json
{
  "code": 0,
  "data": {
    "hazard_id": "HD-20260812-0001",
    "title": "3号桥墩临边防护缺失",
    "description": "桥墩施工区域临边护栏缺失约5米...",
    "level": "major",
    "category": "edge_protection",
    "location": "K12+350 3号桥墩",
    "location_coords": "104.12345,30.67890",
    "project": "成绵高速扩容项目",
    "reporter": { "id": "U001", "name": "张三" },
    "occurred_at": "2026-08-12T09:30:00+08:00",
    "created_at": "2026-08-12T10:30:00+08:00",
    "status": "processing",
    "media": {
      "images": ["https://..."],
      "annotated_images": ["https://..."],
      "detections": [
        {
          "id": 1,
          "label": "临边防护缺失",
          "risk": "high",
          "bbox_norm": [0.10, 0.22, 0.62, 0.78],
          "bbox_px": [120, 264, 744, 936],
          "color_bgr": [0, 0, 255],
          "conf": 0.92,
          "fix": "立即设置临时防护，安装正式护栏",
          "note": "3号桥墩东侧临边"
        }
      ]
    },
    "timeline": [
      {
        "node": "上报",
        "operator": "张三",
        "time": "2026-08-12T10:30:00+08:00",
        "note": "隐患首次上报"
      },
      {
        "node": "派单",
        "operator": "李四",
        "time": "2026-08-12T11:00:00+08:00",
        "note": "指派王五处理，截止2026-08-15"
      }
    ],
    "assignment": {
      "assignee": { "id": "U003", "name": "王五" },
      "requirements": "立即设置临时防护，48小时内安装正式护栏",
      "deadline": "2026-08-15T18:00:00+08:00",
      "priority": "urgent",
      "attachments": []
    },
    "rectification": null
  }
}
```

**错误码**：`40401` 隐患不存在、`40301` 无权查看该隐患

---

### 3.5 隐患派单

```
POST /hazards/{hazard_id}/assign
```

> **角色**：普通用户（仅限本人上报的隐患）  
> **对应功能**：H04

**请求体**：

```json
{
  "assignee_id": "U003",
  "requirements": "立即设置临时防护，48小时内安装正式护栏",
  "deadline": "2026-08-15T18:00:00+08:00",
  "priority": "urgent",
  "attachments": []
}
```

| 参数             | 类型     | 必填  | 说明                                   |
| -------------- | ------ | --- | ------------------------------------ |
| `assignee_id`  | string | 是   | 整改责任人用户 ID                           |
| `requirements` | string | 是   | 整改要求（≤ 1000 字）                       |
| `deadline`     | string | 是   | 整改截止日期（不早于当前日期）                      |
| `priority`     | string | 是   | `urgent` / `high` / `medium` / `low` |
| `attachments`  | file[] | 否   | 附件（最多 5 个）                           |

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "hazard_id": "HD-20260812-0001",
    "status": "processing",
    "assigned_at": "2026-08-12T11:00:00+08:00"
  }
}
```

**错误码**：`40004` 隐患状态不允许派单、`40005` 整改截止日期不合法、`40006` 重大隐患整改期限不得超过 7 天

---

### 3.6 整改反馈

```
POST /hazards/{hazard_id}/rectify
```

> **角色**：普通用户（被指派人）  
> **对应功能**：H05

**请求体**（`multipart/form-data`）：

| 参数             | 类型     | 必填  | 说明                   |
| -------------- | ------ | --- | -------------------- |
| `measures`     | string | 是   | 整改措施描述（≥ 20 字）       |
| `images_after` | file[] | 是   | 整改后照片（至少 1 张，最多 9 张） |
| `attachments`  | file[] | 否   | 相关附件                 |
| `completed_at` | string | 否   | 完成时间，默认当前时间          |

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "hazard_id": "HD-20260812-0001",
    "status": "pending_review",
    "rectified_at": "2026-08-13T16:00:00+08:00"
  }
}
```

**错误码**：`40007` 隐患状态不允许提交整改、`40008` 整改描述不足 20 字、`40009` 未上传整改后照片、`40302` 非被指派人无权操作

---

### 3.7 隐患验收

```
POST /hazards/{hazard_id}/review
```

> **角色**：普通用户（仅限本人上报的隐患）  
> **对应功能**：H06

**请求体**：

```json
{
  "result": "approved",
  "comment": "整改达标，防护设施安装规范",
  "attachments": []
}
```

| 参数            | 类型     | 必填   | 说明                             |
| ------------- | ------ | ---- | ------------------------------ |
| `result`      | string | 是    | `approved`（通过）/ `rejected`（驳回） |
| `comment`     | string | 条件必填 | 验收意见。驳回时必填且 ≥ 10 字，通过时选填       |
| `attachments` | file[] | 否    | 验收附件                           |

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "hazard_id": "HD-20260812-0001",
    "status": "closed",
    "reviewed_at": "2026-08-14T09:00:00+08:00"
  }
}
```

**错误码**：`40010` 隐患状态不允许验收、`40011` 驳回时必须填写原因（≥ 10 字）

---

### 3.8 隐患导出

```
GET /hazards/{hazard_id}/export
```

> **对应功能**：H03（导出功能）

**查询参数**：

| 参数       | 类型     | 必填  | 说明            |
| -------- | ------ | --- | ------------- |
| `format` | string | 否   | 导出格式，默认 `pdf` |

**响应**：返回文件流，Content-Type 为对应文件 MIME 类型。

---

## 4. AI 智能助手

### 4.1 AI 问答（流式）

```
POST /ai/chat
```

> **角色**：普通用户
> **对应功能**：A01、A03、A05、A06

**请求头**：

```
Accept: text/event-stream
Content-Type: application/json
```

**请求体**：

```json
{
  "session_id": "sess_abc123",
  "question": "高处作业安全带的使用标准是什么？"
}
```

| 参数           | 类型     | 必填  | 说明                             |
| ------------ | ------ | --- | ------------------------------ |
| `session_id` | string | 否   | 会话 ID。首次提问不传，服务端返回新 session_id |
| `question`   | string | 是   | 用户问题（≤ 500 字）                  |

**SSE 流式响应**：

```
event: token
data: 根据

event: token
data: 《高处作业

event: token
data: 安全技术规范》

...

event: done
data: {"session_id": "sess_abc123", "message_id": "msg_001"}

event: sources
data: [{"doc_name":"高处作业安全技术规范","section":"第5.2条","excerpt":"安全带应高挂低用..."}]
```

**SSE 事件类型**：

| 事件        | 说明                              |
| --------- | ------------------------------- |
| `token`   | AI 回答的文本片段（逐 token）             |
| `done`    | 回答完成，附带 session_id 和 message_id |
| `sources` | 引用来源列表                          |
| `error`   | 发生错误时的错误信息                      |

> 单次回答长度 ≤ 2000 字，超出部分自动截断。

**错误码（error 事件）**：`40201` 敏感词拦截、`40202` 非安全相关问题（引导重定向）、`40203` AI 服务不可用

---

### 4.2 停止生成

```
POST /ai/chat/{message_id}/stop
```

> **对应功能**：A03（停止生成）

**请求体**：无

**成功响应**：`{ "code": 0, "message": "生成已停止" }`

中断后的消息标记为 `interrupted`，已输出的部分内容保留。

---

### 4.3 获取会话列表

```
GET /ai/sessions
```

> **对应功能**：A02

**查询参数**：

| 参数          | 类型     | 必填  | 说明          |
| ----------- | ------ | --- | ----------- |
| `page`      | int    | 否   | 页码          |
| `page_size` | int    | 否   | 每页条数（默认 20） |
| `keyword`   | string | 否   | 按会话标题搜索     |

**响应数据**：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "session_id": "sess_abc123",
        "title": "高处作业安全带使用标准",
        "last_message": "安全带应高挂低用...",
        "message_count": 6,
        "updated_at": "2026-08-12T10:30:00+08:00"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 4.4 创建新会话

```
POST /ai/sessions
```

> **对应功能**：A02

**请求体**：无（或 `{}`）

**响应**：

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_new456",
    "title": "新对话",
    "created_at": "2026-08-12T10:45:00+08:00"
  }
}
```

---

### 4.5 获取会话消息

```
GET /ai/sessions/{session_id}/messages
```

> **对应功能**：A02

**响应数据**：

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_abc123",
    "title": "高处作业安全带使用标准",
    "messages": [
      {
        "message_id": "msg_001",
        "role": "user",
        "content": "高处作业安全带的使用标准是什么？",
        "created_at": "2026-08-12T10:25:00+08:00"
      },
      {
        "message_id": "msg_002",
        "role": "assistant",
        "content": "根据《高处作业安全技术规范》第5.2条...",
        "sources": [{ "doc_name": "...", "section": "...", "excerpt": "..." }],
        "status": "completed",
        "created_at": "2026-08-12T10:25:05+08:00"
      }
    ]
  }
}
```

---

### 4.6 编辑会话标题

```
PUT /ai/sessions/{session_id}
```

> **对应功能**：A02

**请求体**：

```json
{
  "title": "高处作业安全规范问答"
}
```

---

### 4.7 删除会话

```
DELETE /ai/sessions/{session_id}
```

> **对应功能**：A02

**请求体**：无

**成功响应**：`{ "code": 0, "message": "会话已删除" }`

---

### 4.8 批量删除会话

```
POST /ai/sessions/batch-delete
```

**请求体**：

```json
{
  "session_ids": ["sess_abc", "sess_def", "sess_ghi"]
}
```

---

### 4.9 获取快捷问题

```
GET /ai/quick-questions
```

> **对应功能**：A04

**响应数据**：

```json
{
  "code": 0,
  "data": {
    "categories": [
      {
        "name": "法律法规",
        "icon": "law",
        "questions": [
          "安全生产法对从业人员的权利有哪些规定？",
          "三同时制度的具体要求是什么？"
        ]
      },
      {
        "name": "操作规程",
        "icon": "operation",
        "questions": [
          "高处作业安全带佩戴规范？",
          "动火作业审批流程是什么？"
        ]
      }
    ],
    "hot_questions": [
      "什么是重大事故隐患判定标准？"
    ]
  }
}
```

---

### 4.10 点赞/踩

```
POST /ai/messages/{message_id}/feedback
```

> **对应功能**：A07

**请求体**：

```json
{
  "rating": "dislike",
  "reasons": ["inaccurate", "incomplete"],
  "comment": "回答遗漏了2025年新版规范的内容"
}
```

| 参数        | 类型       | 必填          | 说明                                                                            |
| --------- | -------- | ----------- | ----------------------------------------------------------------------------- |
| `rating`  | string   | 是           | `like` / `dislike`                                                            |
| `reasons` | string[] | 否（like 时忽略） | 踩的原因：`inaccurate` / `incomplete` / `misunderstanding` / `off_topic` / `other` |
| `comment` | string   | 否           | 补充说明（≤ 200 字）                                                                 |

**成功响应**：`{ "code": 0, "message": "反馈已提交" }`

**错误码**：`40012` 重复评价（同一用户同一消息只允许评价一次）

---

### 4.11 取消评价

```
DELETE /ai/messages/{message_id}/feedback
```

> **对应功能**：A07（取消评价后允许重新评价）

---

## 5. 考试工坊

### 5.1 题库管理

#### 5.1.1 题目列表

```
GET /exam/questions
```

> **角色**：普通用户  
> **对应功能**：E01

**查询参数**：

| 参数            | 类型     | 必填  | 说明                                                                |
| ------------- | ------ | --- | ----------------------------------------------------------------- |
| `page`        | int    | 否   | 页码                                                                |
| `page_size`   | int    | 否   | 每页条数                                                              |
| `type`        | string | 否   | 题型：`single_choice` / `multi_choice` / `true_false` / `essay` |
| `difficulty`  | string | 否   | 难度：`easy` / `medium` / `hard`                                     |
| `category_id` | int    | 否   | 分类 ID                                                             |
| `tag`         | string | 否   | 标签筛选                                                              |
| `status`      | string | 否   | 状态：`draft` / `pending_review` / `published` / `rejected`          |
| `keyword`     | string | 否   | 题干关键字搜索                                                           |

**响应数据**：分页格式。

---

#### 5.1.2 题目详情

```
GET /exam/questions/{question_id}
```

---

#### 5.1.3 手动录入题目

```
POST /exam/questions
```

> **对应功能**：E01

**请求体**：

```json
{
  "type": "single_choice",
  "content": "根据《安全生产法》，从业人员有权对本单位安全生产工作中存在的问题提出批评、(  )、控告。",
  "options": {
    "A": "检举",
    "B": "举报",
    "C": "投诉",
    "D": "建议"
  },
  "answer": "B",
  "explanation": "根据《安全生产法》第五十七条...",
  "score": 2,
  "difficulty": "medium",
  "category_id": 1,
  "tags": ["安全生产法", "从业人员权利"]
}
```

| 参数            | 类型       | 必填   | 说明                                                    |
| ------------- | -------- | ---- | ----------------------------------------------------- |
| `type`        | string   | 是    | 题型                                                    |
| `content`     | string   | 是    | 题干                                                    |
| `options`     | object   | 条件必填 | 客观题的选项                                                |
| `answer`      | string   | 是    | 正确答案。客观题为选项 key（单选"A"、多选"AB"），判断为"正确"/"错误"，简答题为参考答案 |
| `explanation` | string   | 是    | 解析                                                    |
| `score`       | float    | 是    | 分值                                                    |
| `difficulty`  | string   | 是    | 难度等级                                                  |
| `category_id` | int      | 否    | 分类 ID                                                 |
| `tags`        | string[] | 否    | 标签                                                    |

**多选题 answer 格式**：`"ABD"`（正确选项字母拼接）

**简答题（essay）answer 格式**：`"参考答案要点"`（自由作答，answer 填参考要点用于评分）

---

#### 5.1.4 编辑题目

```
PUT /exam/questions/{question_id}
```

---

#### 5.1.5 删除题目

```
DELETE /exam/questions/{question_id}
```

> 已被试卷引用的题目不可物理删除，返回错误码 `40021`。

---

#### 5.1.6 批量导入题目

```
POST /exam/questions/import
```

> **对应功能**：E01

**请求体**（`multipart/form-data`）：

| 参数     | 类型   | 必填  | 说明              |
| ------ | ---- | --- | --------------- |
| `file` | file | 是   | Excel 文件（.xlsx） |

**Excel 模板字段**：题型、题干、选项A~H、正确答案、解析、分值、难度、分类、标签

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "total": 150,
    "success": 142,
    "failed": 8,
    "errors": [
      { "row": 5, "reason": "正确答案'X'不在选项范围内" },
      { "row": 23, "reason": "题干长度超过2000字限制" }
    ]
  }
}
```

---

#### 5.1.7 下载导入模板

```
GET /exam/questions/template
```

返回 Excel 模板文件流。

---

#### 5.1.8 题目查重检测

```
POST /exam/questions/check-duplicate
```

**请求体**：

```json
{
  "content": "根据《安全生产法》，从业人员有权..."
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "has_duplicate": true,
    "similar_questions": [
      {
        "question_id": 1024,
        "content": "依据《安全生产法》...",
        "similarity": 0.87
      }
    ]
  }
}
```

---

### 5.2 AI 出题

```
POST /exam/ai/generate
```

> **角色**：普通用户
> **对应功能**：E02

**请求体**：

```json
{
  "mode": "knowledge",
  "knowledge_points": ["高处作业安全", "安全带使用规范"],
  "types": ["single_choice", "true_false"],
  "count": 10,
  "difficulty": "mixed",
  "use_knowledge_base": true
}
```

| 参数                   | 类型       | 必填  | 说明                                                                   |
| -------------------- | -------- | --- | -------------------------------------------------------------------- |
| `mode`               | string   | 是   | 出题方式：`knowledge`（知识点出题）/ `document`（文档出题）/ `free`（自由出题）              |
| `knowledge_points`   | string[] | 否   | 知识点列表（mode=knowledge 时必填）                                            |
| `document_id`        | int      | 否   | 文档 ID（mode=document 时必填）                                             |
| `topic`              | string   | 否   | 自由主题（mode=free 时必填）                                                  |
| `types`              | string[] | 是   | 题型列表（`single_choice` / `multi_choice` / `true_false` / `essay`） |
| `count`              | int      | 是   | 生成数量（1-50）                                                           |
| `difficulty`         | string   | 是   | `easy` / `medium` / `hard` / `mixed`                                 |
| `use_knowledge_base` | bool     | 否   | 是否基于知识库出题，默认 true                                                    |

**SSE 流式响应**（首题 ≤ 5 秒返回）：

```
event: question
data: {"index":1,"type":"single_choice","content":"...","options":{...},"answer":"B","explanation":"...","difficulty":"medium"}

event: question
data: {"index":2,...}

...

event: done
data: {"generation_id":"gen_001","count":10}
```

**最终生成的问题进入「待审核」状态**。

---

### 5.3 试卷管理

#### 5.3.1 试卷列表

```
GET /exam/papers
```

> **角色**：普通用户
> **对应功能**：E03

**查询参数**：`page`、`page_size`、`status`（draft / published）、`keyword`

---

#### 5.3.2 创建试卷（手动组卷）

```
POST /exam/papers
```

> **对应功能**：E03

**请求体**：

```json
{
  "title": "2026年第三季度安全考试",
  "description": "全员安全生产知识考核",
  "mode": "manual",
  "questions": [
    { "question_id": 101, "score": 2, "order": 1 },
    { "question_id": 102, "score": 2, "order": 2 }
  ],
  "config": {
    "total_score": 100,
    "shuffle_questions": true,
    "shuffle_options": true
  }
}
```

| 参数                         | 类型     | 必填  | 说明                                      |
| -------------------------- | ------ | --- | --------------------------------------- |
| `title`                    | string | 是   | 试卷标题                                    |
| `description`              | string | 否   | 试卷说明                                    |
| `mode`                     | string | 是   | `manual`（手动组卷）                          |
| `questions`                | array  | 是   | 题目列表                                    |
| `config.total_score`       | float  | 是   | 试卷总分（固定 100 分）                          |
| `config.shuffle_questions` | bool   | 否   | 题目乱序，默认 false                           |
| `config.shuffle_options`   | bool   | 否   | 选项乱序，默认 false                           |

---

#### 5.3.3 创建试卷（智能组卷）

```
POST /exam/papers
```

> **对应功能**：E03

**请求体**（mode=auto）：

```json
{
  "title": "2026年第三季度安全考试",
  "mode": "auto",
  "strategy": {
    "total_score": 100,
    "distribution": [
      { "type": "single_choice", "count": 20, "score_per": 2 },
      { "type": "multi_choice", "count": 10, "score_per": 3 },
      { "type": "true_false", "count": 10, "score_per": 2 }
    ],
    "difficulty_ratio": { "easy": 0.4, "medium": 0.4, "hard": 0.2 },
    "category_coverage": [
      { "category_id": 1, "ratio": 0.4 },
      { "category_id": 2, "ratio": 0.3 }
    ]
  },
  "config": { ... }
}
```

---

#### 5.3.4 试卷详情

```
GET /exam/papers/{paper_id}
```

---

#### 5.3.5 编辑试卷

```
PUT /exam/papers/{paper_id}
```

> 仅「草稿」状态可编辑。

---

#### 5.3.6 替换题目

```
PUT /exam/papers/{paper_id}/questions/{index}
```

> 替换试卷中某一题，从题库随机抽取同类型同难度题目。

**请求体**：

```json
{
  "type": "single_choice",
  "difficulty": "medium",
  "category_id": 1
}
```

---

#### 5.3.7 删除试卷

```
DELETE /exam/papers/{paper_id}
```

---

### 5.4 出题历史记录

```
GET /exam/my-questions
```

> **角色**：普通用户
> **对应功能**：E05

**查询参数**：`page`、`page_size`、`type`（题型筛选）、`keyword`

**响应数据**：分页格式，`items` 为题目对象数组，仅返回当前用户（出题人）创建的题目：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "question_id": 101,
        "type": "single_choice",
        "content": "根据《安全生产法》...",
        "creator_id": "U001",
        "creator_name": "张三",
        "created_at": "2026-08-12T10:30:00+08:00"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20
  }
}
```

**说明**：历史记录仅显示当前用户（出题人）所有出的题目，不同用户展示各自创建的考题。

---

## 6. 消息通知

### 6.1 消息列表

```
GET /notifications
```

> **对应功能**：H08
> **通知渠道**：站内消息（铃铛红点）+ 邮件通知 + SSE 实时推送
> **默认排序**：未读置顶，按时间倒序；支持 read_status / type / category 筛选

**查询参数**：

| 参数          | 类型   | 必填  | 说明          |
| ----------- | ---- | --- | ----------- |
| `page`      | int  | 否   | 页码          |
| `page_size` | int  | 否   | 每页条数（默认 20） |
| `read_status` | string | 否 | 已读状态筛选：`all`（默认，全部）/ `unread`（仅未读）/ `read`（仅已读） |
| `type`      | string | 否 | 通知类型筛选，多选逗号分隔（如 `hazard_assigned,review_result`） |
| `category`  | string | 否 | 分类筛选：`hazard`（隐患类） |

**响应数据**：分页格式，`items` 为通知对象数组：

```json
{
  "notification_id": "notif_001",
  "type": "hazard_assigned",
  "title": "您有一条新的隐患整改任务",
  "content": "李四指派您处理隐患 [HD-20260812-0001]...",
  "is_read": false,
  "channel": "inbox+email",
  "target_type": "hazard",
  "target_id": "HD-20260812-0001",
  "created_at": "2026-08-12T11:00:05+08:00"
}
```

**通知类型**：

| type                      | 分类   | 说明          |
| ------------------------- | ---- | ----------- |
| `hazard_assigned`         | hazard | 隐患被派单       |
| `rectification_submitted` | hazard | 整改反馈已提交     |
| `review_result`           | hazard | 验收结果（通过/驳回） |
| `rectification_urge`      | hazard | 整改催办        |
| `system_message`          | -   | 系统通知（服务端发送系统类消息时使用，不参与隐患分类统计） |

---

### 6.2 消息详情

```
GET /notifications/{notification_id}
```

> **对应功能**：H08
> 返回单条消息完整详情，响应对象与 6.1 `items` 元素一致（含 `notification_id` / `type` / `title` / `content` / `is_read` / `target_type` / `target_id` / `created_at` 等字段）。

---

### 6.3 未读消息数量

```
GET /notifications/unread-count
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "total": 5,
    "by_category": { "hazard": 3 },
    "by_type": {
      "hazard_assigned": 1,
      "rectification_submitted": 0,
      "review_result": 1,
      "rectification_urge": 1
    }
  }
}
```

> `total` 为总未读数；`by_category` 为分类未读计数（隐患类，供分类 tab 角标）；`by_type` 为分类型未读计数。

---

### 6.4 标记已读

```
PUT /notifications/{notification_id}/read
```

---

### 6.5 全部标记已读

```
POST /notifications/read-all
```

---

### 6.6 删除消息（单条）

```
DELETE /notifications/{notification_id}
```

> 删除单条消息（物理删除），删除后不再展示。

---

### 6.7 批量删除消息

```
POST /notifications/batch-delete
```

**请求体**：

```json
{
  "notification_ids": ["notif_001", "notif_002"]
}
```

> 批量删除消息（物理删除），支持多选。

---

### 6.8 消息实时推送（SSE）

```
GET /notifications/stream
```

> 建立 SSE 长连接，服务端实时推送新消息事件。

**事件格式**：

```
event: notification
data: {"notification_id": "notif_001", "type": "hazard_assigned", "title": "您有一条新的隐患整改任务", "created_at": "2026-08-12T11:00:05+08:00"}
```

---

### 6.9 消息偏好设置

```
GET /notifications/preferences
PUT /notifications/preferences
```

**请求体**（PUT）：

```json
{
  "hazard_assigned": true,
  "rectification_submitted": true,
  "review_result": true,
  "rectification_urge": true
}
```

---

## 7. 统计分析

### 7.1 AI 问答满意度统计

```
GET /statistics/ai-satisfaction
```

> **角色**：Admin  
> **对应功能**：A07（前端入口：管理端「AI 统计」页，路由 `/admin/ai-statistics`）

**查询参数**：

| 参数          | 类型     | 必填  | 说明                                        |
| ----------- | ------ | --- | ----------------------------------------- |
| `days`      | int    | 否   | 统计最近 N 天（1~365）；不传则统计全部                   |
| `date_from` | string | 否   | 开始日期，格式 `YYYY-MM-DD`                      |
| `date_to`   | string | 否   | 结束日期，格式 `YYYY-MM-DD`                      |

> 时间口径：`date_from` / `date_to` 与 `days` 二选一；只要给了任一日期参数即按日期范围过滤（`date_from` 当日 00:00:00 起、`date_to` 当日 23:59:59 止），否则回退按 `days` 过滤；日期格式非法返回 `40001`。

**响应**：

```json
{
  "code": 0,
  "data": {
    "total_feedback_count": 5000,
    "like_count": 3900,
    "dislike_count": 1100,
    "like_rate": 0.78,
    "dislike_reasons": {
      "inaccurate": 300,
      "incomplete": 200,
      "misunderstanding": 150,
      "off_topic": 50,
      "other": 100
    },
    "total_questions": 12000,
    "avg_response_time_ms": 2350.5,
    "model_usage": [
      { "model": "glm-4", "count": 9000 },
      { "model": "qwen-plus", "count": 3000 }
    ]
  }
}
```

| 字段                    | 类型     | 说明                                       |
| --------------------- | ------ | ---------------------------------------- |
| `total_feedback_count` | int    | 时间范围内反馈总数（`message_feedback`）           |
| `like_count`          | int    | 点赞数                                      |
| `dislike_count`       | int    | 点踩数                                      |
| `like_rate`           | float  | 点赞率（0~1，保留 4 位小数，无反馈时为 0）               |
| `dislike_reasons`     | object | 点踩原因分布，固定五键：`inaccurate` / `incomplete` / `misunderstanding` / `off_topic` / `other` |
| `total_questions`     | int    | 时间范围内问答总数（`ai_audit_log`）                |
| `avg_response_time_ms`| float  | 平均响应时间（毫秒，保留 1 位小数）                     |
| `model_usage`         | array  | 模型调用分布，元素为 `{ "model": string, "count": int }`，按调用次数降序 |

---

## 8. 知识库管理

### 8.1 知识库文档列表

```
GET /knowledge/documents
```

> **角色**：Admin
> **对应功能**：A05（管理端，前端入口：管理端「知识库管理」页）

**查询参数**：

| 参数          | 类型     | 必填  | 说明                                  |
| ----------- | ------ | --- | ----------------------------------- |
| `page`      | int    | 否   | 页码（默认 1）                            |
| `page_size` | int    | 否   | 每页条数（默认 20，1~100）                   |
| `type`      | string | 否   | 按文档类型筛选：`regulation` / `procedure` / `case` / `emergency` / `other` |
| `status`    | string | 否   | 按状态筛选：`parsing` / `chunking` / `indexing` / `indexed` / `failed` |
| `keyword`   | string | 否   | 按标题模糊搜索                             |

**响应数据**：分页格式，`items` 为文档对象数组：

| 字段               | 类型     | 说明                                   |
| ---------------- | ------ | ------------------------------------ |
| `document_id`    | int    | 文档 ID（即 `doc_id`）                    |
| `title`          | string | 文档标题                                 |
| `doc_type`       | string | 文档类型                                  |
| `category_id`    | int/null | 所属分类 ID（未分类为 null）               |
| `tags`           | string[] | 标签列表（由 `tags_json` 解析）             |
| `authority_level` | string | 权威等级：`A` / `B` / `C`                |
| `file_path`      | string | 文件存储路径（相对 `uploads` 目录）             |
| `file_size`      | int    | 文件大小（字节）                             |
| `status`         | string | 处理状态（见 8.3）                          |
| `chunk_count`    | int    | 分块数量                                 |
| `error_message`  | string/null | 失败原因（status=failed 时非空）       |
| `created_by`     | string | 上传人用户 ID                             |
| `created_at`     | string | 创建时间                                 |
| `updated_at`     | string | 更新时间                                 |

---

### 8.2 上传文档

```
POST /knowledge/documents
```

> **角色**：Admin  
> **对应功能**：A05

**请求体**（`multipart/form-data`）：

| 参数                | 类型       | 必填  | 说明                                                               |
| ----------------- | -------- | --- | ---------------------------------------------------------------- |
| `file`            | file     | 是   | 文档文件（PDF/Word/TXT/Markdown，≤ 50MB）                               |
| `title`           | string   | 是   | 文档标题                                                             |
| `doc_type`        | string   | 是   | 文档类型：`regulation` / `procedure` / `case` / `emergency` / `other` |
| `category_id`     | int      | 否   | 分类 ID                                                            |
| `tags`            | string[] | 否   | 标签                                                               |
| `authority_level` | string   | 否   | 权威等级：`A` / `B` / `C`，默认 `B`                                      |

**响应**：

```json
{
  "code": 0,
  "data": {
    "document_id": 245,
    "status": "indexed",
    "message": "文档已上传，正在解析和向量化处理中"
  }
}
```

> 上传为同步处理：解析 -> 切分（参数读 `rag_config`，默认 `chunk_size=500` / `chunk_overlap=50`）-> 向量化（bge-large）-> 写入 Chroma 集合 `safety_knowledge`，完成后 `status=indexed`。

**失败场景**：

| 场景 | 返回 |
| --- | --- |
| 文件类型不支持（仅 `.pdf` / `.docx` / `.doc` / `.txt` / `.md`） | 错误码 `40020` |
| 文件超过 50MB | 错误码 `41300` |
| `doc_type` / `authority_level` 取值非法 | 错误码 `40001` |
| 解析/切分异常（如 PDF 损坏、解析库缺失） | 错误码 `50001`（"文档解析失败: ..."），文档记录保留且 `status=failed` |
| 向量化失败 | 上传仍成功返回，`status=failed`、`message="文档已上传，但向量化失败，请查看状态接口中的错误信息"`，具体原因通过 8.3 状态接口的 `error_message` 查看 |

---

### 8.3 文档解析状态查询

```
GET /knowledge/documents/{doc_id}/status
```

> **角色**：Admin

**响应**：

```json
{
  "code": 0,
  "data": {
    "document_id": 245,
    "status": "indexed",
    "chunk_count": 36,
    "error_message": null
  }
}
```

**状态流转**：`parsing` -> `chunking` -> `indexing` -> `indexed`；任一环节失败置 `failed`（`error_message` 记录原因，≤ 500 字）。

---

### 8.4 删除文档

```
DELETE /knowledge/documents/{doc_id}
```

> **角色**：Admin  
> 同时删除关联向量（Chroma 集合 `safety_knowledge` 中该文档的分块向量）、分块记录与磁盘文件；文档不存在返回 `40401`。

---

### 8.5 知识库分类管理

> **角色**：Admin（以下 4 个端点均仅限管理员）

| 方法       | 路径                           | 说明           |
| -------- | ---------------------------- | ------------ |
| `GET`    | `/knowledge/categories`      | 分类树（返回多级树形结构，节点含 `category_id` / `name` / `parent_id` / `level` / `sort_order` / `children`） |
| `POST`   | `/knowledge/categories`      | 创建分类（请求体：`name` 必填，`parent_id` / `sort_order` 可选；`level` 由服务端按父分类层级 +1 计算） |
| `PUT`    | `/knowledge/categories/{category_id}` | 编辑分类（请求体：`name` / `parent_id` / `sort_order` 均可选；父分类不能是自身；分类不存在返回 `40401`） |
| `DELETE` | `/knowledge/categories/{category_id}` | 删除分类（存在子分类或其下存在文档时返回 `40001`，不可删除） |

---

## 9. 管理端接口（AI 模型配置 / RAG 配置 / 测试集）

> 本节接口均仅限 `Admin` 角色访问，是管理端后台管控能力的接口。

### 9.1 AI 模型配置

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/admin/models` | 获取所有模型配置 |
| `POST` | `/admin/models` | 新增模型配置 |
| `PUT` | `/admin/models/{model_id}` | 编辑模型配置（含置信度、启用状态） |
| `DELETE` | `/admin/models/{model_id}` | 删除模型配置 |

**请求体（创建，multipart/form-data）**：`model_type`（chat/vision/embedding）、`model_name`、`provider`（可选，仅 embedding 使用，标记来源 `local`/`huggingface`）、`api_base`（本地目录或镜像地址）、`api_key`、`confidence`（默认 0.7）、`temperature`（默认 0.3）、`max_tokens`（默认 2048）、`is_active`（默认 0）。

> 说明：chat/vision 模型不再区分厂商；embedding 模型在前端以独立弹窗配置，需选择"本地部署"或"联入 HuggingFace 下载"来源。RAG 参数配置接口（`GET/PUT /admin/rag-config`）已于 2026-08-17 移除，切分参数沿用 `rag_config` 表默认值。

### 9.3 测试集管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/admin/test-sets` | 获取测试集列表 |
| `POST` | `/admin/test-sets` | 创建测试集（可选择测试集数量，最少 100、最高 500） |
| `POST` | `/admin/test-sets/{test_set_id}/items` | 上传测试条目（预留，可后续扩展） |
| `POST` | `/admin/test-sets/{test_set_id}/run` | 执行模型测试（预留） |
| `POST` | `/admin/test-sets/regenerate` | 从知识库重新生成 RAG 测试集（数量 100-500 可配置） |
| `DELETE` | `/admin/test-sets/{test_set_id}` | 删除测试集 |
| `GET` | `/admin/test-results` | 获取测试结果列表 |

**创建测试集请求体**：

```json
{
  "name": "2026年Q3 RAG测试集",
  "count": 200,
  "source": "knowledge_base"
}
```

| 参数     | 类型   | 必填  | 说明                              |
| ------ | ---- | --- | ------------------------------- |
| `name` | string | 是 | 测试集名称                           |
| `count` | int  | 是   | 测试集数量，最少 100、最高 500             |
| `source` | string | 否 | 数据来源，默认 `knowledge_base`（知识库） |

**说明**：
- 新建的测试集能够保存，保存后可在测试集列表中查看。
- 模型测试评估中可直接使用测试集管理中创建出的测试集（通过 `test_set_id` 指定）。
- 测试集数据持久化存储于数据库测试集数据表。

---

## 10. 考试工坊补充接口（试卷发送 / 题目替换 / 总分约束）

### 10.1 发送试卷（预留接口）

```
POST /exam/papers/{paper_id}/send
```

> **角色**：普通用户

发送时前端弹窗显示「发送成功」，当前版本实际不做任何行为；预留发送接口，以便后续衔接其它系统。

### 10.2 替换试卷题目（预览阶段）

```
PUT /exam/papers/{paper_id}/questions/{question_id}
```

> **角色**：普通用户

预览阶段可替换单题，替换后重新校验总分。

### 10.3 总分 100 分约束

所有试卷创建、编辑、题目替换操作均强制校验 `total_score == 100`，不符合返回 `40001`。

---

## 附录：错误码参考

### HTTP 状态码

| 状态码 | 说明                |
| --- | ----------------- |
| 200 | 成功                |
| 201 | 创建成功              |
| 400 | 请求参数错误            |
| 401 | 未认证或 Token 过期     |
| 403 | 无权限               |
| 404 | 资源不存在             |
| 409 | 资源冲突（如重复提交）       |
| 413 | 上传文件过大            |
| 429 | 请求频率超限            |
| 500 | 服务器内部错误           |
| 503 | 服务暂不可用（如 AI 服务降级） |

### 业务错误码

| 错误码            | 说明                   |
| -------------- | -------------------- |
| 0              | 成功                   |
| **认证 (401xx)** |                      |
| 40101          | 用户名或密码错误             |
| 40102          | 账户已被禁用               |
| 40103          | refresh_token 无效或已过期 |
| 40104          | 旧密码错误                |
| **通用 (400xx)** |                      |
| 40001          | 参数校验失败               |
| 40002          | 图片数量超限（最多 9 张）       |
| 40004          | 隐患状态不允许当前操作          |
| 40005          | 整改截止日期不合法            |
| 40006          | 重大隐患整改期限不得超过 7 天     |
| 40007          | 隐患状态不允许提交整改          |
| 40008          | 整改描述不足 20 字          |
| 40009          | 未上传整改后照片             |
| 40010          | 隐患状态不允许验收            |
| 40011          | 驳回时必须填写原因（≥ 10 字）    |
| 40012          | 重复评价                 |
| 40021          | 题目已被试卷引用，不可删除        |
| **权限 (403xx)** |                      |
| 40301          | 无权查看该隐患              |
| 40302          | 非被指派人无权操作            |
| 40303          | 角色无此功能权限             |
| **AI (402xx)** |                      |
| 40201          | 问题包含敏感内容             |
| 40202          | 非安全相关问题              |
| 40203          | AI 服务暂不可用            |
| 40204          | 会话数量已达上限（100 个）      |
| **资源 (404xx)** |                      |
| 40401          | 隐患不存在                |
| 40402          | 会话不存在                |
| 40403          | 试卷不存在                |
| 40404          | 题目不存在                |
| **限流 (429xx)** |                      |
| 42901          | AI 问答频率超限（≤ 10 次/分钟） |
| 42902          | 请求频率超限               |

---

> **文档结束** | 蜀道安全助手 API 接口文档 V1.0  
> 共 8 大模块、60+ 接口，覆盖隐患管理、AI 问答、考试工坊、消息通知、统计分析、知识库管理全部功能。

*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
