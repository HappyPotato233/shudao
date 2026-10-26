"""AI 智能助手接口。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context_async
from app.core.response import BizError, success
from app.models.base import get_db
from app.schemas.ai import (
    BatchDeleteRequest,
    ChatRequest,
    FeedbackRequest,
    SessionTitleRequest,
)
from app.services.ai_chat import AiChatService

router = APIRouter(prefix="/ai", tags=["AI 智能助手"])


@router.post("/chat", summary="AI 问答（SSE 流式）")
async def chat(
    req: ChatRequest,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    svc = AiChatService(db, ctx)
    try:
        prepared = await svc.prepare_chat(req.question, req.session_id)
        generator = svc.stream_answer(req.question, prepared["session_id"])
    except BizError as exc:
        import json

        code = exc.code
        message = exc.message

        def error_stream(code=code, message=message):
            yield (
                "event: error\n"
                f"data: {json.dumps({'code': code, 'message': message}, ensure_ascii=False)}\n\n"
            )

        generator = error_stream()
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/chat/{message_id}/stop", summary="停止生成")
async def stop_chat(
    message_id: str,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    await AiChatService(db, ctx).stop_generation(message_id)
    return success(None, message="生成已停止")


@router.get("/sessions", summary="获取会话列表")
async def list_sessions(
    page: int = Query(1),
    page_size: int = Query(20),
    keyword: str | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await AiChatService(db, ctx).list_sessions(page, page_size, keyword))


@router.post("/sessions", summary="创建新会话")
async def create_session(
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await AiChatService(db, ctx).create_session())


@router.get("/sessions/{session_id}/messages", summary="获取会话消息")
async def get_messages(
    session_id: str,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await AiChatService(db, ctx).get_messages(session_id))


@router.put("/sessions/{session_id}", summary="编辑会话标题")
async def rename_session(
    session_id: str,
    req: SessionTitleRequest,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await AiChatService(db, ctx).rename_session(session_id, req.title))


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    await AiChatService(db, ctx).delete_session(session_id)
    return success(None, message="会话已删除")


@router.post("/sessions/batch-delete", summary="批量删除会话")
async def batch_delete_sessions(
    req: BatchDeleteRequest,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    await AiChatService(db, ctx).batch_delete_sessions(req.session_ids)
    return success(None, message="批量删除成功")


@router.get("/quick-questions", summary="获取快捷问题")
async def quick_questions(
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await AiChatService(db, ctx).visible_quick_questions())


@router.post("/messages/{message_id}/feedback", summary="点赞/踩")
async def submit_feedback(
    message_id: str,
    req: FeedbackRequest,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    data = await AiChatService(db, ctx).submit_feedback(message_id, req)
    return success(data, message="反馈已提交")


@router.delete("/messages/{message_id}/feedback", summary="取消评价")
async def remove_feedback(
    message_id: str,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    await AiChatService(db, ctx).remove_feedback(message_id)
    return success(None, message="评价已取消")
