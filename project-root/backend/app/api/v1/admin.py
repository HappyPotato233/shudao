"""管理端 API (Admin only)"""
import json, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.permissions import require_roles_async
from app.core.response import BizError, success
from app.models.base import get_db

router = APIRouter(prefix="/admin", tags=["管理端"])


def _mask_key(key: str | None) -> str:
    """API Key 脱敏：仅保留前 4 位与后 4 位。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


@router.get("/models/runtime")
async def get_runtime_models(ctx=Depends(require_roles_async("Admin"))):
    """当前系统实际生效的模型配置（来自 .env / settings，API Key 脱敏）。"""
    embedding_dir = settings.EMBEDDING_MODEL_DIR
    rerank_dir = settings.RERANK_MODEL_DIR
    return success([
        {
            "model_type": "chat",
            "model_name": settings.LLM_MODEL_NAME or "",
            "api_base": settings.LLM_BASE_URL or "",
            "api_key": _mask_key(settings.LLM_API_KEY),
            "configured": bool(settings.LLM_API_KEY and settings.LLM_BASE_URL and settings.LLM_MODEL_NAME),
            "source": "env",
            "note": "AI 智能问答大模型（OpenAI 兼容接口）",
        },
        {
            "model_type": "vision",
            "model_name": settings.VISULIZATION_MODEL_NAME or "",
            "api_base": settings.VISULIZATION_BASE_URL or "",
            "api_key": _mask_key(settings.VISULIZATION_API_KEY),
            "configured": bool(settings.VISULIZATION_API_KEY and settings.VISULIZATION_BASE_URL and settings.VISULIZATION_MODEL_NAME),
            "source": "env",
            "note": "隐患图像识别大模型（OpenAI 兼容接口）",
        },
        {
            "model_type": "embedding",
            "model_name": Path(embedding_dir).name if embedding_dir else "",
            "api_base": embedding_dir or "",
            "api_key": "",
            "configured": bool(embedding_dir and Path(embedding_dir).exists()),
            "source": "local",
            "note": "本地向量化模型（sentence-transformers）",
        },
        {
            "model_type": "rerank",
            "model_name": Path(rerank_dir).name if rerank_dir else "",
            "api_base": rerank_dir or "",
            "api_key": "",
            "configured": bool(rerank_dir and Path(rerank_dir).exists()),
            "source": "local",
            "note": "本地重排序模型（CrossEncoder）",
        },
    ])


@router.get("/models")
async def list_models(ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text("SELECT * FROM ai_model_config ORDER BY model_type, id"))).fetchall()
    return success([dict(r._mapping) for r in rows])


async def _deactivate_same_type(db: AsyncSession, model_type: str, keep_id: int | None = None) -> None:
    """同类型模型互斥：启用某个模型前，把同类型其它模型统一置为停用。

    保证每种类型（chat / vision / embedding / rerank）同一时刻只有一个 is_active=1，
    避免下游按类型取生效配置时命中多个。
    """
    from app.models.mixins import now_cst
    sql = "UPDATE ai_model_config SET is_active = 0, updated_at = :uat WHERE model_type = :mt AND is_active = 1"
    params = {"uat": now_cst(), "mt": model_type}
    if keep_id is not None:
        sql += " AND id <> :keep"
        params["keep"] = keep_id
    await db.execute(text(sql), params)


@router.post("/models")
async def create_model(model_type: str = Form(...), model_name: str = Form(...),
    provider: str = Form(""), api_base: str | None = Form(None), api_key: str | None = Form(None),
    confidence: float = Form(0.7), temperature: float = Form(0.3), max_tokens: int = Form(2048),
    is_active: int = Form(0),
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """provider 仅用于 embedding 来源标记（local/huggingface），chat/vision 不再区分厂商。"""
    from app.models.mixins import now_cst
    _now = now_cst()
    # 新建即启用时，先停用同类型其它模型，保证同类型只有一个生效模型
    if is_active:
        await _deactivate_same_type(db, model_type)
    await db.execute(text(
        "INSERT INTO ai_model_config (model_type, provider, model_name, api_base, api_key, confidence, temperature, max_tokens, is_active, created_at, updated_at) "
        "VALUES (:mt, :p, :mn, :ab, :ak, :c, :t, :mtk, :ia, :cat, :uat)"),
        {"mt": model_type, "p": provider, "mn": model_name, "ab": api_base, "ak": api_key, "c": confidence, "t": temperature, "mtk": max_tokens, "ia": 1 if is_active else 0, "cat": _now, "uat": _now})
    await db.commit()
    return success(None)


@router.put("/models/{model_id}")
async def update_model(model_id: int, model_type: str | None = Form(None), provider: str | None = Form(None),
    model_name: str | None = Form(None), api_base: str | None = Form(None), api_key: str | None = Form(None),
    confidence: float | None = Form(None), temperature: float | None = Form(None),
    max_tokens: int | None = Form(None), is_active: int | None = Form(None),
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    # 启用某个模型时，先停用同类型其它模型（同类型同时只允许一个生效）
    if is_active == 1:
        final_type = model_type
        if final_type is None:
            row = (await db.execute(text("SELECT model_type FROM ai_model_config WHERE id = :id"), {"id": model_id})).fetchone()
            if not row:
                raise BizError(40401, "模型不存在", 404)
            final_type = row[0]
        await _deactivate_same_type(db, final_type, keep_id=model_id)
    sets, params = [], {}
    for fld, val in [("model_type", model_type), ("provider", provider), ("model_name", model_name),
        ("api_base", api_base), ("api_key", api_key), ("confidence", confidence),
        ("temperature", temperature), ("max_tokens", max_tokens), ("is_active", is_active)]:
        if val is not None:
            sets.append(f"{fld} = :{fld}")
            params[fld] = val
    if not sets: raise BizError(40001, "无更新字段")
    params["id"] = model_id
    from app.models.mixins import now_cst
    sets.append("updated_at = :uat")
    params["uat"] = now_cst()
    await db.execute(text(f"UPDATE ai_model_config SET {', '.join(sets)} WHERE id = :id"), params)
    await db.commit()
    return success(None)


@router.delete("/models/{model_id}")
async def delete_model(model_id: int, ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    await db.execute(text("DELETE FROM ai_model_config WHERE id = :id"), {"id": model_id})
    await db.commit()
    return success(None)


def _sse(event: str, data) -> str:
    """构造 SSE 事件帧，与 ai.py 的流式格式保持一致（token 为原文，其余为 JSON）。"""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def _load_model_cfg(db: AsyncSession, model_id: int, label: str = "模型", expected_type: str | None = None) -> dict:
    """按 id 读取模型配置，可选校验类型。"""
    row = (await db.execute(text("SELECT * FROM ai_model_config WHERE id = :id"), {"id": model_id})).fetchone()
    if not row:
        raise BizError(40401, f"{label}模型不存在", 404)
    cfg = dict(row._mapping)
    if expected_type and cfg["model_type"] != expected_type:
        raise BizError(40001, f"{label}模型类型应为 {expected_type}")
    return cfg


async def _load_active_cfg(db: AsyncSession, model_type: str) -> dict | None:
    """取系统生效的指定类型模型配置（is_active=1），不存在则返回 None。"""
    row = (await db.execute(text(
        "SELECT * FROM ai_model_config WHERE model_type = :mt AND is_active = 1 ORDER BY id LIMIT 1"),
        {"mt": model_type})).fetchone()
    return dict(row._mapping) if row else None


class ModelChatTestRequest(BaseModel):
    """单条问答测试请求。"""
    question: str


@router.post("/models/{model_id}/chat-test", summary="模型单条问答测试（Admin）")
async def model_chat_test(model_id: int, req: ModelChatTestRequest,
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """用指定 chat 模型做一次单条 RAG 问答（SSE 流式）。

    检索固定使用系统生效的 Embedding / CrossEncoder；不写会话、消息与审计表，
    仅用于验证某个 chat 模型配置是否可用。
    """
    from app.services.ai_chat import QA_SYSTEM_PROMPT
    from app.services.model_eval_service import build_rag_service
    from app.services.rag import rag_service

    question = req.question.strip()
    if not question:
        raise BizError(40001, "问题不能为空")
    cfg = await _load_model_cfg(db, model_id, "被测", "chat")

    emb_cfg = await _load_active_cfg(db, "embedding")
    rerank_cfg = await _load_active_cfg(db, "rerank")
    rag = build_rag_service(emb_cfg, rerank_cfg) if (emb_cfg or rerank_cfg) else rag_service

    async def _stream():
        client = None
        try:
            retrieval = await rag.retrieve(question, top_k=5, threshold=settings.RAG_RERANK_THRESHOLD)
            sources = retrieval.get("results", [])
            evidence = "\n\n".join(
                f"[{i + 1}] {s.get('title', '')} {s.get('locator', '')}\n{s.get('text', '')}"
                for i, s in enumerate(sources)
            ) or "无可用依据"
            messages = [
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": f"证据：\n{evidence}\n\n问题：{question}"},
            ]
            client = AsyncOpenAI(api_key=cfg.get("api_key") or "none", base_url=cfg["api_base"])
            stream = await client.chat.completions.create(
                model=cfg["model_name"], messages=messages,
                temperature=cfg.get("temperature") or 0.3, stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield _sse("token", delta)
            yield _sse("sources", sources)
            yield _sse("done", {"session_id": "", "message_id": ""})
        except Exception as exc:  # 单项测试失败不抛 500，按流式错误事件回传
            yield _sse("error", {"message": str(exc)[:300]})
        finally:
            if client is not None:
                await client.close()

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/test-sets")
async def list_test_sets(ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text("SELECT * FROM ai_test_sets ORDER BY created_at DESC"))).fetchall()
    return success([dict(r._mapping) for r in rows])


@router.post("/test-sets")
async def create_test_set(name: str = Form(...), description: str | None = Form(None),
    model_type: str = Form("vision"), count: int = Form(200),
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """新建测试集；vision 类型自动从标注图片库抽样生成带标注条目。"""
    from app.services.testset_service import build_vision_testset
    from app.models.mixins import now_cst
    tid = f"ts_{uuid.uuid4().hex[:12]}"
    await db.execute(text("INSERT INTO ai_test_sets (test_set_id, name, description, model_type, created_by, created_at) VALUES (:id, :n, :d, :mt, :cb, :cat)"),
        {"id": tid, "n": name, "d": description, "mt": model_type, "cb": ctx.user_id, "cat": now_cst()})
    if model_type == "vision":
        stats = await build_vision_testset(db, tid, count=count)
        await db.commit()
        return success({"test_set_id": tid, "image_count": stats["total"], "by_subset": stats["by_subset"]})
    await db.commit()
    return success({"test_set_id": tid})


@router.get("/test-sets/{test_set_id}/items", summary="查看测试集条目")
async def list_test_set_items(test_set_id: str, page: int = 1, page_size: int = 20,
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """分页返回测试集条目（vision 显示图片+标注，chat 显示问答内容）。"""
    total = (await db.execute(text("SELECT COUNT(*) FROM ai_test_items WHERE test_set_id = :id"), {"id": test_set_id})).scalar()
    rows = (await db.execute(
        text("SELECT id, item_type, image_path, ground_truth, expected_answer, metadata_json FROM ai_test_items "
             "WHERE test_set_id = :id ORDER BY id LIMIT :lim OFFSET :off"),
        {"id": test_set_id, "lim": page_size, "off": (page - 1) * page_size},
    )).fetchall()
    items = []
    for r in rows:
        gt = json.loads(r.ground_truth) if r.ground_truth else {}
        meta = json.loads(r.metadata_json) if r.metadata_json else {}
        items.append({
            "id": r.id,
            "item_type": r.item_type,
            "image_path": r.image_path,
            "image_url": f"/uploads/{r.image_path}" if r.image_path else None,
            "source": gt.get("source") or meta.get("subset"),
            "original_name": gt.get("original_name"),
            "detections": gt.get("detections", []),
            "query": gt.get("query"),
            "expected_answer": r.expected_answer,
        })
    return success({"total": total, "page": page, "page_size": page_size, "items": items})


@router.delete("/test-sets/{test_set_id}")
async def delete_test_set(test_set_id: str, ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    from app.services.testset_service import purge_testset_files
    await db.execute(text("DELETE FROM ai_test_items WHERE test_set_id = :id"), {"id": test_set_id})
    await db.execute(text("DELETE FROM ai_test_sets WHERE test_set_id = :id"), {"id": test_set_id})
    await db.commit()
    # 删除测试集图片目录（磁盘 IO，放线程池）
    await run_in_threadpool(purge_testset_files, test_set_id)
    return success(None)


@router.post("/test-sets/{test_set_id}/items", summary="上传测试条目（预留）")
async def upload_test_items(
    test_set_id: str,
    images: list[UploadFile] = File(None),
    ground_truth: str | None = Form(None),
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """测试图片上传预留接口，当前不启用真实图片测试。"""
    return success({"test_set_id": test_set_id, "uploaded": 0, "note": "图片测试暂未启用"})


class VisionRunRequest(BaseModel):
    """执行 vision 评测请求。"""
    model_config_id: int


class ChatRunRequest(BaseModel):
    """执行 chat 评测请求（检索链路必填）。"""
    model_config_id: int
    embedding_model_id: int
    crossencoder_model_id: int


async def _load_test_set(db: AsyncSession, test_set_id: str) -> dict:
    """读取测试集，不存在则 404。"""
    row = (await db.execute(text("SELECT * FROM ai_test_sets WHERE test_set_id = :id"), {"id": test_set_id})).fetchone()
    if not row:
        raise BizError(40401, "测试集不存在", 404)
    return dict(row._mapping)


@router.post("/test-sets/{test_set_id}/run-vision", summary="执行 vision 评测")
async def run_vision_test(test_set_id: str, req: VisionRunRequest,
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """视觉检测评测：逐图识别并与 YOLO 真值匹配，异步执行。"""
    from app.services.model_eval_service import start_eval_task

    ts = await _load_test_set(db, test_set_id)
    if ts["model_type"] != "vision":
        raise BizError(40001, "该测试集不是 vision 类型，请使用 chat 评测接口")
    cfg = await _load_model_cfg(db, req.model_config_id, "被测", "vision")

    result_id = await start_eval_task(test_set_id, cfg, None, None, user_id=ctx.user_id)
    return success({"result_id": result_id, "test_set_id": test_set_id, "status": "running"})


@router.post("/test-sets/{test_set_id}/run-chat", summary="执行 chat 评测")
async def run_chat_test(test_set_id: str, req: ChatRunRequest,
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """检索增强问答评测：计算 recall@5 / MRR 与回答准确率，异步执行。"""
    from app.services.model_eval_service import start_eval_task

    ts = await _load_test_set(db, test_set_id)
    if ts["model_type"] != "chat":
        raise BizError(40001, "该测试集不是 chat 类型，请使用 vision 评测接口")
    cfg = await _load_model_cfg(db, req.model_config_id, "被测", "chat")
    emb_cfg = await _load_model_cfg(db, req.embedding_model_id, "embedding", "embedding")
    rerank_cfg = await _load_model_cfg(db, req.crossencoder_model_id, "crossencoder", "rerank")

    result_id = await start_eval_task(test_set_id, cfg, emb_cfg, rerank_cfg, user_id=ctx.user_id)
    return success({"result_id": result_id, "test_set_id": test_set_id, "status": "running"})


@router.get("/test-results")
async def list_test_results(test_set_id: str | None = Query(None),
    ctx=Depends(require_roles_async("Admin")), db: AsyncSession = Depends(get_db)):
    """评测历史列表：附测试集名称与被测模型名，detail_json 含 token/耗时/逐条详情。

    test_set_id 可选，传入时只返回该测试集的评测记录。
    """
    where = "WHERE r.test_set_id = :ts " if test_set_id else ""
    rows = (await db.execute(text(
        "SELECT r.*, s.name AS test_set_name, m.model_name "
        "FROM ai_test_results r "
        "LEFT JOIN ai_test_sets s ON s.test_set_id = r.test_set_id "
        "LEFT JOIN ai_model_config m ON m.id = r.model_config_id "
        f"{where}"
        "ORDER BY r.executed_at DESC LIMIT 50"), {"ts": test_set_id} if test_set_id else {})).fetchall()
    return success([dict(r._mapping) for r in rows])
