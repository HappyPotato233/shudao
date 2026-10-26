-- ============================================================
-- 蜀道安全助手 - 业务数据库（app.db）DDL 脚本
-- 隐患安全管理模块：11 张表
-- 数据库引擎：SQLite 3.35+
-- 字符编码：UTF-8
-- 时间格式：ISO 8601 字符串（如 2026-08-12T10:30:00+08:00）
-- 布尔值：INTEGER，CHECK(0/1)
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. roles（角色表）
-- RBAC 角色定义，两类角色：Admin（管理员）/ User（普通用户）
-- ============================================================
CREATE TABLE IF NOT EXISTS roles (
    role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,                          -- 角色名：Admin / User
    description TEXT NOT NULL,                                 -- 角色描述
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now'))
);

-- ============================================================
-- 2. users（用户表）
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,                           -- 用户唯一标识，格式：U{4位数字}
    username       TEXT NOT NULL UNIQUE,                       -- 用户名/工号
    password_hash  TEXT NOT NULL,                              -- BCrypt 加盐密码哈希
    name           TEXT NOT NULL,                              -- 真实姓名
    role_id        INTEGER NOT NULL,                           -- 角色 ID
    department     TEXT NOT NULL,                              -- 所属部门
    project        TEXT NOT NULL,                              -- 所属项目/标段
    phone          TEXT,                                       -- 手机号
    is_active      INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),  -- 是否启用（0=禁用，1=启用）
    last_login_at  TEXT,                                       -- 最后登录时间
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

CREATE INDEX IF NOT EXISTS idx_users_role       ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_department ON users(department);
CREATE INDEX IF NOT EXISTS idx_users_project    ON users(project);

-- ============================================================
-- 3. hazards（隐患表）
-- 核心业务表，存储隐患全生命周期数据。对应 PRD H01-H06。
-- 状态流转：pending -> processing -> pending_review -> closed / rejected
-- ============================================================
CREATE TABLE IF NOT EXISTS hazards (
    hazard_id        TEXT PRIMARY KEY,                         -- 隐患编号，格式：HD-YYYYMMDD-XXXX
    title            TEXT NOT NULL,                            -- 隐患标题（≤ 100 字）
    description      TEXT NOT NULL,                            -- 详细描述（≤ 2000 字）
    level            TEXT NOT NULL,                            -- 隐患等级：critical / major / minor / trivial
    category         TEXT NOT NULL,                            -- 隐患类别：height_work / edge_protection / machinery / fire_safety / temp_electricity 等
    location         TEXT NOT NULL,                            -- 发生位置描述
    location_coords  TEXT,                                     -- GPS 坐标（"lng,lat"）
    project          TEXT NOT NULL,                            -- 所属项目/标段
    reporter_id      TEXT NOT NULL,                            -- 上报人
    status           TEXT NOT NULL DEFAULT 'pending',          -- 状态：pending / processing / pending_review / closed / rejected
    occurred_at      TEXT NOT NULL,                            -- 发生时间
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (reporter_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_hazards_status   ON hazards(status);
CREATE INDEX IF NOT EXISTS idx_hazards_level    ON hazards(level);
CREATE INDEX IF NOT EXISTS idx_hazards_category ON hazards(category);
CREATE INDEX IF NOT EXISTS idx_hazards_project  ON hazards(project);
CREATE INDEX IF NOT EXISTS idx_hazards_reporter ON hazards(reporter_id);

-- ============================================================
-- 4. hazard_media（隐患媒体附件表）
-- 存储隐患上报/整改/验收的图片附件（原图与标注图）
-- ============================================================
CREATE TABLE IF NOT EXISTS hazard_media (
    media_id        INTEGER PRIMARY KEY AUTOINCREMENT,           -- 附件 ID
    hazard_id       TEXT NOT NULL,                               -- 所属隐患
    media_type      TEXT NOT NULL,                               -- 媒体类型：image_original（原图）/ image_annotated（标注图）
    parent_media_id INTEGER,                                     -- 标注图对应的原图 media_id，原图为 NULL
    file_path       TEXT NOT NULL,                               -- 文件存储路径
    file_size       INTEGER NOT NULL,                            -- 文件大小（字节）
    sort_order      INTEGER NOT NULL DEFAULT 0,                  -- 排序序号
    context         TEXT NOT NULL DEFAULT 'report',              -- 所属环节：report / rectification / review
    uploaded_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (hazard_id) REFERENCES hazards(hazard_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_media_id) REFERENCES hazard_media(media_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hazard_media_hazard ON hazard_media(hazard_id);

-- ============================================================
-- 5. hazard_detections（隐患检测结果表）
-- 存储隐患上报图片经大模型视觉识别后的检测结果，对应 PRD H09。
-- ============================================================
CREATE TABLE IF NOT EXISTS hazard_detections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,               -- 检测结果 ID
    hazard_id   TEXT NOT NULL,                                   -- 所属隐患
    media_id    INTEGER,                                         -- 所属原图 media_id，可空
    label       TEXT NOT NULL,                                   -- 隐患名称/类别
    risk        TEXT NOT NULL,                                   -- 风险等级：high / medium / low
    bbox_norm   TEXT NOT NULL,                                   -- 归一化边界框 JSON：[x1, y1, x2, y2]，取值 0~1
    bbox_px     TEXT,                                             -- 像素坐标边界框 JSON，可空，默认 NULL
    color_bgr   TEXT NOT NULL,                                   -- 标注框颜色 BGR JSON：[B, G, R]（OpenCV 顺序）
    conf        REAL NOT NULL,                                   -- 置信度 0~1
    fix         TEXT,                                             -- 整改建议
    note        TEXT,                                             -- 隐患位置/说明备注
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (hazard_id) REFERENCES hazards(hazard_id) ON DELETE CASCADE,
    FOREIGN KEY (media_id) REFERENCES hazard_media(media_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_detections_hazard ON hazard_detections(hazard_id);
CREATE INDEX IF NOT EXISTS idx_detections_media  ON hazard_detections(media_id);

-- ============================================================
-- 6. hazard_assignments（隐患派单记录表）
-- ============================================================
CREATE TABLE IF NOT EXISTS hazard_assignments (
    assignment_id    INTEGER PRIMARY KEY AUTOINCREMENT,        -- 派单 ID
    hazard_id        TEXT NOT NULL,                            -- 所属隐患
    assigner_id      TEXT NOT NULL,                            -- 派单人（安全员/管理员）
    assignee_id      TEXT NOT NULL,                            -- 整改责任人
    requirements     TEXT NOT NULL,                            -- 整改要求
    deadline         TEXT NOT NULL,                            -- 整改截止日期
    priority         TEXT NOT NULL,                            -- 优先级：urgent / high / medium / low
    attachments_json TEXT NOT NULL DEFAULT '[]',                   -- 附件路径列表 JSON（合法 JSON 字符串）
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (hazard_id)   REFERENCES hazards(hazard_id) ON DELETE CASCADE,
    FOREIGN KEY (assigner_id) REFERENCES users(user_id),
    FOREIGN KEY (assignee_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_hazard_assignments_hazard    ON hazard_assignments(hazard_id);
CREATE INDEX IF NOT EXISTS idx_hazard_assignments_assignee  ON hazard_assignments(assignee_id);

-- ============================================================
-- 7. hazard_rectifications（整改反馈记录表）
-- ============================================================
CREATE TABLE IF NOT EXISTS hazard_rectifications (
    rectification_id  INTEGER PRIMARY KEY AUTOINCREMENT,       -- 整改 ID
    hazard_id         TEXT NOT NULL,                           -- 所属隐患
    assignee_id       TEXT NOT NULL,                           -- 整改人
    measures          TEXT NOT NULL,                           -- 整改措施描述（≥ 20 字）
    images_json       TEXT NOT NULL DEFAULT '[]',                -- 整改后照片路径列表 JSON（合法 JSON 字符串）
    attachments_json  TEXT NOT NULL DEFAULT '[]',                -- 相关附件路径列表 JSON（合法 JSON 字符串）
    completed_at      TEXT NOT NULL,                           -- 整改完成时间
    round             INTEGER NOT NULL DEFAULT 1,              -- 整改轮次（驳回后递增）
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (hazard_id)   REFERENCES hazards(hazard_id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_hazard_rectifications_hazard ON hazard_rectifications(hazard_id);

-- ============================================================
-- 8. hazard_reviews（验收记录表）
-- ============================================================
CREATE TABLE IF NOT EXISTS hazard_reviews (
    review_id         INTEGER PRIMARY KEY AUTOINCREMENT,       -- 验收 ID
    hazard_id         TEXT NOT NULL,                           -- 所属隐患
    reviewer_id       TEXT NOT NULL,                           -- 验收人
    result            TEXT NOT NULL,                           -- 验收结论：approved / rejected
    comment           TEXT,                                    -- 验收意见（驳回时必填，≥ 10 字）
    attachments_json  TEXT NOT NULL DEFAULT '[]',                -- 验收附件路径列表 JSON（合法 JSON 字符串）
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (hazard_id)   REFERENCES hazards(hazard_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_hazard_reviews_hazard ON hazard_reviews(hazard_id);

-- ============================================================
-- 9. hazard_timeline（隐患状态流转时间线表）
-- 记录隐患全生命周期的每个操作节点，不可篡改
-- ============================================================
CREATE TABLE IF NOT EXISTS hazard_timeline (
    timeline_id   INTEGER PRIMARY KEY AUTOINCREMENT,           -- 记录 ID
    hazard_id     TEXT NOT NULL,                               -- 所属隐患
    action_type   TEXT NOT NULL,                               -- 操作类型：reported / assigned / rectified / reviewed / urged
    operator_id   TEXT NOT NULL,                               -- 操作人
    note          TEXT NOT NULL,                               -- 操作备注
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (hazard_id)   REFERENCES hazards(hazard_id) ON DELETE CASCADE,
    FOREIGN KEY (operator_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_timeline_hazard ON hazard_timeline(hazard_id);

-- ============================================================
-- 10. notifications（消息通知表）
-- 对应 PRD H08，站内消息通知。保留策略：90 天自动清理。
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    notification_id  TEXT PRIMARY KEY,                         -- 通知 ID，格式：notif_{12位hex}
    user_id          TEXT NOT NULL,                            -- 接收用户
    type             TEXT NOT NULL,                            -- 通知类型：hazard_assigned / rectification_submitted / review_result / rectification_urge
    title            TEXT NOT NULL,                            -- 通知标题
    content          TEXT NOT NULL,                            -- 通知内容
    target_type      TEXT,                                     -- 关联业务类型：hazard / system
    target_id        TEXT,                                     -- 关联业务 ID
    is_read          INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),  -- 是否已读
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notifications_user   ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id, is_read);

-- ============================================================
-- 11. notification_preferences（通知偏好表）
-- ============================================================
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id                  TEXT PRIMARY KEY,                 -- 用户 ID（既为主键又为外键）
    hazard_assigned          INTEGER NOT NULL DEFAULT 1 CHECK(hazard_assigned IN (0,1)),
    rectification_submitted  INTEGER NOT NULL DEFAULT 1 CHECK(rectification_submitted IN (0,1)),
    review_result            INTEGER NOT NULL DEFAULT 1 CHECK(review_result IN (0,1)),
    rectification_urge       INTEGER NOT NULL DEFAULT 1 CHECK(rectification_urge IN (0,1)),
    updated_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ============================================================
-- 12. conversations（AI 会话表）
-- 对应 PRD A02，每个用户最多 100 个会话。
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    session_id            TEXT PRIMARY KEY,                    -- 会话 ID，格式：sess_{12位hex}
    user_id               TEXT NOT NULL,                       -- 所属用户
    title                 TEXT NOT NULL DEFAULT '新对话',      -- 会话标题
    message_count         INTEGER NOT NULL DEFAULT 0,          -- 消息数量
    last_message_preview  TEXT,                                -- 最后一条消息预览
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversations_user    ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);

-- ============================================================
-- 13. messages（AI 消息表）
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    message_id    TEXT PRIMARY KEY,                            -- 消息 ID，格式：msg_{12位hex}
    session_id    TEXT NOT NULL,                               -- 所属会话
    role          TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content       TEXT NOT NULL,                               -- 消息内容
    sources_json  TEXT,                                        -- 引用来源列表 JSON
    status        TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed','interrupted')),
    token_count   INTEGER,                                     -- Token 数量
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (session_id) REFERENCES conversations(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);

-- ============================================================
-- 14. message_feedback（AI 回答评价表）
-- ============================================================
CREATE TABLE IF NOT EXISTS message_feedback (
    feedback_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   TEXT NOT NULL,                                -- 被评价消息
    user_id      TEXT NOT NULL,                                -- 评价人
    rating       TEXT NOT NULL CHECK(rating IN ('like','dislike')),
    reasons_json TEXT,                                         -- 踩的原因列表 JSON
    comment      TEXT,                                         -- 补充说明
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE (message_id, user_id)
);

-- ============================================================
-- 15. quick_questions（快捷问题表）
-- ============================================================
CREATE TABLE IF NOT EXISTS quick_questions (
    question_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    category       TEXT NOT NULL,                              -- 分类名称
    category_icon  TEXT NOT NULL,                              -- 分类图标标识
    question       TEXT NOT NULL,                              -- 问题文本
    roles_json     TEXT NOT NULL DEFAULT '[]',                 -- 可见角色列表 JSON
    is_hot         INTEGER NOT NULL DEFAULT 0 CHECK(is_hot IN (0,1)),
    sort_order     INTEGER NOT NULL DEFAULT 0,
    is_active      INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now'))
);

-- ============================================================
-- 16. ai_audit_log（AI 审计日志表）
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,                                      -- 会话 ID
    user_id         TEXT NOT NULL,                             -- 用户 ID
    user_question   TEXT NOT NULL,                             -- 用户提问原文
    ai_answer       TEXT,                                      -- AI 回答全文
    model_used      TEXT NOT NULL,                             -- 使用的模型
    response_time_ms INTEGER NOT NULL,                         -- 响应时间（毫秒）
    sources_json    TEXT,                                      -- 引用来源 JSON
    filter_action   TEXT,                                      -- blocked / passed / output_filtered
    token_input     INTEGER,                                   -- 输入 Token 数
    token_output    INTEGER,                                   -- 输出 Token 数
    scene           TEXT NOT NULL DEFAULT 'qa',                -- 调用场景
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (session_id) REFERENCES conversations(session_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON ai_audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_user    ON ai_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_time    ON ai_audit_log(created_at);

-- ============================================================
-- 17. sensitive_words（敏感词库表）
-- ============================================================
CREATE TABLE IF NOT EXISTS sensitive_words (
    word_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    word       TEXT NOT NULL UNIQUE,
    category   TEXT NOT NULL,                                  -- political / violence / pornography / illegal / ads / privacy / other
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now'))
);

-- ============================================================
-- 18. auth_sessions（认证会话表）
-- 登录成功后创建，保存 access/refresh token jti、最后活动时间、
-- token 过期时间与吊销时间。用于持久化登出与 30 分钟空闲自动失效。
-- ============================================================
CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id          TEXT PRIMARY KEY,                     -- 会话 ID，格式：auth_{12位hex}
    user_id             TEXT NOT NULL,                        -- 所属用户
    access_jti          TEXT NOT NULL UNIQUE,                 -- access token 唯一标识
    refresh_jti         TEXT NOT NULL UNIQUE,                 -- refresh token 唯一标识
    last_active_at      TEXT NOT NULL,                        -- 最后活动时间
    access_expires_at   TEXT NOT NULL,                        -- access token 过期时间
    refresh_expires_at  TEXT NOT NULL,                        -- refresh token 过期时间
    revoked_at          TEXT,                                 -- 吊销时间；NULL 表示有效
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user        ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_access_jti  ON auth_sessions(access_jti);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_refresh_jti ON auth_sessions(refresh_jti);

-- ============================================================
-- 19. question_categories（题目分类表）
-- 对应 PRD E01，多级题目分类树。
-- ============================================================
CREATE TABLE IF NOT EXISTS question_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    parent_id   INTEGER,
    level       INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (parent_id) REFERENCES question_categories(category_id)
);

-- ============================================================
-- 20. questions（题库表）
-- ============================================================
CREATE TABLE IF NOT EXISTS questions (
    question_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    type              TEXT NOT NULL,
    content           TEXT NOT NULL,
    options_json      TEXT,
    answer            TEXT NOT NULL,
    explanation       TEXT NOT NULL,
    score             REAL NOT NULL DEFAULT 2,
    difficulty        TEXT NOT NULL,
    category_id       INTEGER,
    tags_json         TEXT NOT NULL DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'draft',
    source            TEXT NOT NULL DEFAULT 'manual',
    ai_generation_id  TEXT,
    created_by        TEXT NOT NULL,
    reviewed_by       TEXT,
    reviewed_at       TEXT,
    review_comment    TEXT,
    is_deleted        INTEGER NOT NULL DEFAULT 0 CHECK(is_deleted IN (0,1)),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (category_id) REFERENCES question_categories(category_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (reviewed_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_questions_type       ON questions(type);
CREATE INDEX IF NOT EXISTS idx_questions_status     ON questions(status);
CREATE INDEX IF NOT EXISTS idx_questions_category   ON questions(category_id);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);

-- ============================================================
-- 21. exam_papers（试卷表）
-- ============================================================
CREATE TABLE IF NOT EXISTS exam_papers (
    paper_id           TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT,
    mode               TEXT NOT NULL,
    strategy_json      TEXT,
    total_score        REAL NOT NULL,
    pass_score         REAL NOT NULL,
    duration           INTEGER NOT NULL,
    shuffle_questions  INTEGER NOT NULL DEFAULT 0 CHECK(shuffle_questions IN (0,1)),
    shuffle_options    INTEGER NOT NULL DEFAULT 0 CHECK(shuffle_options IN (0,1)),
    anti_cheat         INTEGER NOT NULL DEFAULT 0 CHECK(anti_cheat IN (0,1)),
    max_switch_count   INTEGER NOT NULL DEFAULT 3,
    allow_retake       INTEGER NOT NULL DEFAULT 0 CHECK(allow_retake IN (0,1)),
    max_retake_count   INTEGER NOT NULL DEFAULT 1,
    start_time         TEXT NOT NULL,
    end_time           TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'draft',
    created_by         TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_papers_status  ON exam_papers(status);
CREATE INDEX IF NOT EXISTS idx_papers_creator ON exam_papers(created_by);

-- ============================================================
-- 22. paper_questions（试卷-题目关联表）
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id    TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    score       REAL NOT NULL,
    "order"     INTEGER NOT NULL,
    FOREIGN KEY (paper_id) REFERENCES exam_papers(paper_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id),
    UNIQUE (paper_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_questions_paper ON paper_questions(paper_id);

-- ============================================================
-- 23. paper_assignees（试卷指派人表）
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_assignees (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id      TEXT NOT NULL,
    assignee_type TEXT NOT NULL,
    assignee_id   TEXT NOT NULL,
    FOREIGN KEY (paper_id) REFERENCES exam_papers(paper_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_paper_assignees_paper ON paper_assignees(paper_id);

-- ============================================================
-- 26. ai_model_config（AI模型配置表）
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_model_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type      TEXT NOT NULL,           -- chat / vision / embedding
    provider        TEXT NOT NULL,            -- baidu / aliyun / zhipu
    model_name      TEXT NOT NULL,            -- ERNIE-4.0-Turbo / Qwen-Plus 等
    api_base        TEXT,                     -- API 地址
    api_key         TEXT,                     -- API Key（加密存储）
    confidence      REAL NOT NULL DEFAULT 0.7,-- 置信度阈值
    temperature     REAL NOT NULL DEFAULT 0.3,
    max_tokens      INTEGER NOT NULL DEFAULT 2048,
    is_active       INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1)),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_model_config_type ON ai_model_config(model_type);

-- ============================================================
-- 27. ai_test_sets（AI测试集表）
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_test_sets (
    test_set_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    model_type      TEXT NOT NULL,           -- chat / vision
    image_count     INTEGER NOT NULL DEFAULT 0,
    question_count  INTEGER NOT NULL DEFAULT 0,
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- ============================================================
-- 28. ai_test_items（测试集条目表）
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_test_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    test_set_id     TEXT NOT NULL,
    item_type       TEXT NOT NULL,           -- image / question
    image_path      TEXT,                     -- 测试图片路径
    ground_truth    TEXT,                     -- 真值（JSON：detections 或正确答案）
    expected_answer TEXT,                     -- 期望回答（问答测试）
    metadata_json   TEXT,                     -- 额外元数据
    FOREIGN KEY (test_set_id) REFERENCES ai_test_sets(test_set_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_test_items_set ON ai_test_items(test_set_id);

-- ============================================================
-- 29. ai_test_results（AI测试结果表）
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_test_results (
    result_id       TEXT PRIMARY KEY,
    test_set_id     TEXT NOT NULL,
    model_config_id INTEGER NOT NULL,
    model_type      TEXT NOT NULL,
    total_items     INTEGER NOT NULL,
    correct_items   INTEGER NOT NULL,
    accuracy        REAL NOT NULL,
    precision_val   REAL,
    recall_val      REAL,
    f1_score        REAL,
    avg_latency_ms  REAL,
    detail_json     TEXT,                     -- 逐条结果详情
    executed_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    executed_by     TEXT NOT NULL,
    FOREIGN KEY (test_set_id) REFERENCES ai_test_sets(test_set_id),
    FOREIGN KEY (model_config_id) REFERENCES ai_model_config(id),
    FOREIGN KEY (executed_by) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_test_results_set ON ai_test_results(test_set_id);

-- ============================================================
-- 30. rag_config（RAG参数配置表）
-- ============================================================
CREATE TABLE IF NOT EXISTS rag_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key      TEXT NOT NULL UNIQUE,
    config_value    TEXT NOT NULL,
    description     TEXT,
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now'))
);

-- 默认 RAG 配置
INSERT OR IGNORE INTO rag_config (config_key, config_value, description) VALUES
    ('chunk_size', '500', '文档分块大小（字符数）'),
    ('chunk_overlap', '50', '分块重叠字符数'),
    ('retrieval_top_k', '5', '检索返回 Top-K 条'),
    ('similarity_threshold', '0.7', '相似度阈值'),
    ('rerank_enabled', '1', '是否启用重排序'),
    ('hybrid_search_enabled', '0', '是否启用混合检索'),
    ('hybrid_keyword_weight', '0.3', '混合检索中关键词权重');

-- ============================================================
-- 31. exam_papers 增加 exam_url 字段
-- ============================================================
-- ALTER TABLE exam_papers ADD COLUMN exam_url TEXT;
-- SQLite 不支持 ADD COLUMN IF NOT EXISTS，通过应用层 init_db 处理

-- ============================================================
-- 32. knowledge_categories（知识库分类树）
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    parent_id   INTEGER,
    level       INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (parent_id) REFERENCES knowledge_categories(category_id)
);

-- ============================================================
-- 33. knowledge_documents（知识库文档）
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_documents (
    doc_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'other',  -- regulation / procedure / case / emergency / other
    category_id     INTEGER,
    tags_json       TEXT NOT NULL DEFAULT '[]',
    authority_level TEXT NOT NULL DEFAULT 'B',      -- A / B / C
    file_path       TEXT NOT NULL,                  -- 相对 uploads 目录路径
    file_size       INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'parsing',-- parsing / chunking / indexing / indexed / failed
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (category_id) REFERENCES knowledge_categories(category_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- ============================================================
-- 34. knowledge_chunks（知识库文档分块）
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+08:00', 'now')),
    FOREIGN KEY (doc_id) REFERENCES knowledge_documents(doc_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc ON knowledge_chunks(doc_id);
