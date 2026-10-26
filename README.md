# 蜀道安全助手

施工安全隐患智能识别与 RAG 知识问答系统：面向施工安全场景，提供隐患图片识别、知识库问答、培训考试与数据统计的一体化解决方案。

## 主要功能

- **隐患识别**：上传施工图片，多模态模型识别隐患并输出标注结果
- **知识问答**：基于 RAG（向量检索 + BM25 混合检索 + 重排）回答规范与安全问题，回答带可回溯引用
- **研究方向跟踪**：关键词订阅、定时抓取论文、生成多视角综述
- **培训考试**：题库管理、在线考试与成绩统计
- **系统管理**：用户与权限、通知、调用日志与统计

## 目录结构

| 条目 | 说明 |
| --- | --- |
| `project-root/` | 主体工程，包含后端服务、前端页面、数据库脚本与容器化配置 |
| `project-root/backend/` | FastAPI 后端服务，按 `api` / `core` / `models` / `schemas` / `services` 分层 |
| `project-root/frontend/` | Vue 3 + Vite 前端工程（Element Plus、ECharts） |
| `project-root/database/` | 建表脚本 `schema.sql`、初始化数据 `init_data.sql` 与评测测试集（数据库文件不入库） |
| `project-root/docker/` | `docker-compose.yml` 等容器化部署配置 |
| `project-root/docs/` | 工程内部文档与接口测试说明 |
| `docs/` | 项目文档：PRD、架构设计、API、数据库设计、RAG 方案与前端风格指南 |
| `scripts/` | 本地开发启动脚本 `start-dev.ps1` |
| `test_report/` | RAG 分块策略与检索效果评测报告、测试集明细数据 |
| `data/` | 本地测试图片数据集（隧道、简支梁、加油站等，体积较大，**不入库**） |
| `annotate_hazards.py` | 隐患标注脚本：调用多模态 API，用 OpenCV 在施工图上画框并输出标注图 |
| `build_chunk_eval.py` | 分块策略评估脚本：对比固定、父子、语义、递归、滑动窗口 5 种分块方式的 BM25 检索效果 |
| `build_rag_sw_eval.py` | 滑动窗口分块评估脚本：重建语料后对比 BM25 / 向量 / 混合 / 混合+重排 4 种检索策略 |
| `build_rag_testset.py` | 测试集构建脚本：从知识库抽取 200 条去重问答对并评估检索策略 |
| `启动项目.bat` | Windows 一键启动入口，转调 `scripts/start-dev.ps1` 启动前后端开发服务 |
| `.gitignore` | Git 忽略规则：密钥、数据库、模型权重、本地数据、缓存与构建产物 |
| `README.md` | 项目说明与目录结构 |

## 快速开始

```bash
# 后端
cd project-root/backend
pip install -r requirements.txt
# 在 project-root/.env 中配置数据库连接与模型 API Key（该文件不入库）

# 前端
cd project-root/frontend
npm install
npm run dev
```

Windows 下也可直接双击根目录的 `启动项目.bat` 启动开发环境。

## 不入库的内容

以下内容体积较大或包含敏感信息，已在 `.gitignore` 中排除，需在本地自行准备：

- `project-root/.env`、`project-root/docker/.env.docker`（API Key、数据库密码、JWT 密钥）
- `project-root/database/*.db`、`*.sqlite3`（业务数据库与知识库）
- `project-root/models/`（bge-large、bge-base-rerank 等向量与重排模型）
- `project-root/chroma_data/`（向量库持久化目录）
- `project-root/uploads/`（上传的图片与数据集）
- `data/`（本地测试图片数据集）
- `project-root/frontend/node_modules/`、`dist/`（依赖与构建产物）
