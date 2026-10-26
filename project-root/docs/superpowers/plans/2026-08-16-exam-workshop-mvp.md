# 考试工坊 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 FastAPI 后端实现考试工坊可运行 MVP：预置正式题库、AI 补题并审核、组卷、在线考试、自动阅卷和成绩查询。

**Architecture:** 沿用 FastAPI + SQLAlchemy + SQLite 分层结构。考试只从 `published` 题目抽题；AI 生成题目进入 `pending_review`，管理员审核后进入正式题库。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, SQLite, pytest, openpyxl, reportlab, 现有 rag_service 和 llm_service。

## Global Constraints

- 项目根目录：`D:\实习\shudao\test\project-root`
- 角色：Admin / SafetyOfficer / Employee
- 题库状态：`draft` / `pending_review` / `published` / `rejected`
- 试卷状态：`draft` / `published` / `ended`
- 考试记录状态：`in_progress` / `submitted` / `grading` / `scored`
- 用户考试只能从 `published` 题目中抽题
- AI 题目必须经管理员审核后才能被组卷使用
- 全量测试环境：`D:\Anaconda\envs\shixi\python.exe`

---

### Task 1: 保存计划文档

- [x] **Step 1: 创建计划文档**
- [x] **Step 2: 确认范围**

---

### Task 2: 添加失败测试

**Files:**
- Create: `backend/tests/test_exam.py`

- [ ] **Step 1: 写题目、审核、组卷、考试、阅卷的接口测试**
- [ ] **Step 2: 运行并确认因表或路由缺失而失败**

---

### Task 3: 添加考试表与预置题库

**Files:**
- Modify: `database/schema.sql`
- Modify: `backend/app/core/database.py`
- Create: `backend/app/models/exam.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 新增 7 张考试表**
- [ ] **Step 2: 新增 ORM 模型**
- [ ] **Step 3: 预置分类和已发布题目**

---

### Task 4: 题库与分类 API

**Files:**
- Create: `backend/app/schemas/exam.py`
- Create: `backend/app/services/exam_service.py`
- Create: `backend/app/api/v1/exam.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: 分类列表和题目 CRUD**
- [ ] **Step 2: 题目列表支持筛选和分页**
- [ ] **Step 3: 已使用题目删除保护**

---

### Task 5: AI 出题与审核

- [ ] **Step 1: POST /exam/ai/generate 生成 pending_review 题目**
- [ ] **Step 2: 待审核列表**
- [ ] **Step 3: 单题和批量审核**

---

### Task 6: 组卷、发布与指派

- [ ] **Step 1: 手动组卷**
- [ ] **Step 2: 智能组卷**
- [ ] **Step 3: 试卷列表、详情、发布**

---

### Task 7: 在线考试

- [ ] **Step 1: 我的考试列表**
- [ ] **Step 2: 开始考试**
- [ ] **Step 3: 单题保存、批量保存、标记**
- [ ] **Step 4: 切屏事件和交卷**

---

### Task 8: 自动阅卷与结果

- [ ] **Step 1: 客观题自动评分**
- [ ] **Step 2: 成绩结果查询**
- [ ] **Step 3: 成绩发布**

---

### Task 9: 全量回归

- [ ] **Step 1: 运行 `pytest tests/ -q`**
- [ ] **Step 2: 确认所有新增和既有测试通过**

---

## Self-Review

- 覆盖检查：预置题库、AI 出题、审核、组卷、考试、阅卷、结果均有测试。
- 占位符检查：无 TBD。
- 类型一致性：各任务使用同一套 question/paper/attempt 状态和接口命名。
