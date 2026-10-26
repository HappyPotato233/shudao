"""FastAPI 应用入口"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.core.response import register_exception_handlers
from app.api.v1.router import api_router


async def _cleanup_stale_eval_results():
    """启动时清理遗留的评测 running 状态（服务重启后评测线程已死，状态永远不会再更新）。"""
    import json
    from sqlalchemy import update
    from app.models.base import AsyncSessionLocal
    from app.models.ai_admin import AiTestResult

    async with AsyncSessionLocal() as db:
        # detail_json 形如 {"status": "running"}；_insert_result 由 json.dumps 生成
        result = await db.execute(
            update(AiTestResult)
            .where(AiTestResult.detail_json.like('%"status": "running"%'))
            .values(
                detail_json=json.dumps(
                    {"status": "failed", "error": "服务重启，评测中断，请重新发起测试"},
                    ensure_ascii=False,
                )
            )
        )
        if result.rowcount:
            await db.commit()
            print(f"[startup] 已清理 {result.rowcount} 条因服务重启中断的评测任务（running → failed）")


async def _run_urge_job():
    """催办任务：会话清理 + 催办通知 + 过期通知清理（全量 async）。"""
    from app.models.base import AsyncSessionLocal
    from app.services.auth_service import cleanup_expired_sessions
    from app.services.notification_service import (
        cleanup_expired_notifications,
        send_due_urge_notifications,
    )

    async with AsyncSessionLocal() as db:
        await cleanup_expired_sessions(db)
        await send_due_urge_notifications(db)
        await cleanup_expired_notifications(db)


async def _urge_loop():
    """每小时触发一次整改催办（asyncio 原生任务，无线程依赖）。"""
    while True:
        await asyncio.sleep(3600)
        try:
            await _run_urge_job()
        except Exception:
            pass


async def _preload_models():
    """后台预热本地 BGE 模型，避免首次 AI 问答请求等待 90s+ 模型加载。

    torch 加载为阻塞 CPU 操作，经 asyncio.to_thread 下沉线程池执行。
    """
    def _load():
        from app.services.embedding import embedding_service, rerank_service
        embedding_service._get_model()  # 预加载 bge-large
        rerank_service._get_model()     # 预加载 bge-rerank
        print("[startup] BGE 模型预热完成")

    try:
        await asyncio.to_thread(_load)
    except Exception as e:
        print(f"[startup] BGE 模型预热失败（不影响启动，首次请求时再加载）: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    await init_db()
    await _cleanup_stale_eval_results()
    urge_task = asyncio.create_task(_urge_loop())
    # 后台预热 BGE 模型，不阻塞启动（测试环境通过 PRELOAD_MODELS=false 关闭，
    # 避免加载中的线程在进程退出时引发段错误）
    preload_task = asyncio.create_task(_preload_models()) if settings.PRELOAD_MODELS else None
    try:
        yield
    finally:
        # 应用关闭时取消后台任务，避免事件循环挂起
        for task in (urge_task, preload_task):
            if task is not None:
                task.cancel()


def create_app() -> FastAPI:
    """应用工厂"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # CORS 中间件（前后端分离必需）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制为前端域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 统一异常处理
    register_exception_handlers(app)

    # 注册 v1 路由
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # 上传文件静态服务
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    # 健康检查
    @app.get("/health", tags=["系统"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
