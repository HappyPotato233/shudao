# 隐患管理模块（后端）设计文档

> 日期：2026-08-14
> 范围：project-root 后端（FastAPI + SQLAlchemy + SQLite），不含前端

## 1. 目标

按 PRD / API.md / DATABASE.md / AI_SOLUTION.md 完成隐患管理模块的后端，覆盖：

- H01 隐患上报
- H02 隐患列表
- H03 隐患详情（导出 PDF 本轮不做）
- H04 隐患派单
- H05 整改反馈
- H06 隐患验收
- H07 隐患统计分析
- H08 消息通知（站内通知 + 自动通知 + 催办调度）
- H09 AI 隐患智能识别（真实大模型调用 + OpenCV 画框，凭据经 `.env` 注入，留空则优雅降级）

## 2. 关键决策

1. **只做后端**，不建 Vue3 前端。
2. **H09 走 OpenAI 兼容接口**：参考 `test/annotate_hazards.py`，用 `openai.OpenAI(api_key, base_url)` 调用多模态模型，返回结构化 JSON，再用 OpenCV（画框）+ Pillow（中文标注）在原图副本上绘制标注图。
3. **认证切数据库**：移除 Mock 内存用户，登录/鉴权改为查询 `users` + `roles` 表，并在 `init_data.sql` 预置 4 个账号。
4. **管辖范围规则**：安全员 `SafetyOfficer` 可查看/管理 `hazard.project == 当前用户.project` 的隐患；管理员全局；普通员工仅本人上报的数据。
5. **导出 PDF**：本轮跳过，后续补。

## 3. 角色与数据范围

| 操作 | Admin | SafetyOfficer | Employee |
|---|---|---|---|
| 上报 H01 | 全部 | 全部 | 全部 |
| 列表/详情 H02/H03 | 全部 | 本 project | 仅本人 |
| 派单 H04 | 允许 | 允许 | 禁止 |
| 整改 H05 | 允许 | 允许 | 仅被指派时 |
| 验收 H06 | 允许 | 允许 | 禁止 |
| 统计 H07 | 全局 | 本 project | 禁止 |
| 通知 H08 | 本人 | 本人 | 本人 |

## 4. 状态机

```
pending --派单--> processing --整改反馈--> pending_review --验收通过--> closed
                                          |--验收驳回--> rejected --重新整改--> pending_review
```

## 5. 文件结构

```
project-root/
├── .env                                  # 新增：VISULIZATION_API_KEY/BASE_URL/MODEL_NAME（留空）
├── uploads/                              # 运行期生成：上传图片/标注图
├── database/init_data.sql                # 改：INSERT OR IGNORE 预置角色+用户
├── backend/
│   ├── requirements.txt                  # 改：+openai/opencv/numpy/Pillow/python-dotenv/apscheduler
│   └── app/
│       ├── main.py                       # 改：挂载 /uploads 静态目录 + 启动调度器
│       ├── core/
│       │   ├── config.py                 # 改：AI 配置 + 上传目录 + 图片限制
│       │   ├── database.py               # 改：init_db 幂等执行 init_data.sql
│       │   ├── response.py               # 改：补充 40004~40011/403xx/40203/429xx 错误码
│       │   └── permissions.py            # 新增：RBAC 装饰器 + 数据范围判断
│       ├── api/deps.py                   # 改：鉴权走 DB + 返回 AuthContext(role/scope)
│       ├── api/v1/hazards.py             # 新增：隐患接口
│       ├── api/v1/notifications.py       # 新增：通知接口
│       ├── api/v1/statistics.py          # 新增：统计接口
│       ├── api/v1/users.py               # 新增：用户列表（派单选人）
│       ├── api/v1/router.py              # 改：聚合新路由
│       ├── schemas/hazard.py             # 新增
│       ├── schemas/notification.py       # 新增
│       ├── schemas/statistics.py         # 新增
│       ├── services/hazard_service.py    # 新增：隐患业务
│       ├── services/notification_service.py # 新增：通知业务
│       ├── services/statistics_service.py   # 新增：统计业务
│       ├── services/idgen.py             # 新增：HD-YYYYMMDD-XXXX
│       ├── services/vision.py            # 新增：大模型视觉调用
│       └── services/annotator.py         # 新增：OpenCV+Pillow 画框
│   └── tests/
│       ├── test_auth.py                  # 改：40104/40105 -> 40100
│       ├── test_hazards.py               # 新增
│       ├── test_notifications.py         # 新增
│       ├── test_statistics.py            # 新增
│       └── test_vision.py                # 新增
```

## 6. 错误码约定（本模块新增/复用）

| 码 | 含义 |
|---|---|
| 40001 | 参数校验失败 |
| 40004 | 隐患状态不允许派单 |
| 40005 | 整改截止日期不合法 |
| 40006 | 重大隐患整改期限不得超过 7 天 |
| 40007 | 隐患状态不允许提交整改 |
| 40008 | 整改描述不足 20 字 |
| 40009 | 未上传整改后照片 |
| 40010 | 隐患状态不允许验收 |
| 40011 | 驳回时必须填写原因（≥10 字） |
| 40203 | AI 服务暂不可用 |
| 40301 | 无权查看该隐患 |
| 40302 | 非被指派人无权操作 |
| 40303 | 角色无此功能权限 |
| 40401 | 隐患不存在 |
| 40100 | 未认证 / Token 无效（统一约定） |

## 7. 视觉识别方案（H09）

- 配置：`.env` 中 `VISULIZATION_API_KEY`、`VISULIZATION_BASE_URL`、`VISULIZATION_MODEL_NAME`，留空则不调用。
- 调用：OpenAI 兼容多模态 `chat.completions.create`，图片以 base64 data URL 传入。
- 输出：解析模型 JSON 数组，字段对齐 `label/risk/bbox_norm/bbox_px/color_bgr/conf/fix/note/id`。
- 画框：OpenCV `cv2.rectangle` 画框 + Pillow 画中文标注/引线；只画在原图副本上，原图不变。
- 降级：未配置或调用失败返回 40203；`detections` 为空数组表示未识别到隐患。

## 8. 验收口径

- 全部新接口有测试；`pytest` 全绿。
- 隐患编号格式 `HD-YYYYMMDD-XXXX` 且当日递增。
- 状态流转、角色数据范围、自动通知均按上表/状态机执行。
- H09 在 `.env` 为空时返回 40203，配置后能真实调用并输出标注图。
