"""AI 智能助手业务编排：会话、消息、问答、快捷问题、反馈与审计。"""
from __future__ import annotations

import json
import secrets
import threading
import time
from collections.abc import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import AuthContext
from app.core.config import settings
from app.core.response import BizError, ErrorCode
from app.models.ai_orm import (
    AiAuditLog,
    Conversation,
    Message,
    MessageFeedback,
    QuickQuestion,
)
from app.models.user_orm import User
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.services.sensitive_word import SensitiveWordFilter


def now_cst() -> str:
    import datetime

    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _sse(event: str, data: str) -> str:
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {payload}\n\n"


# 问答系统提示：线上问答与管理端单条模型测试共用，保证评估口径一致
QA_SYSTEM_PROMPT = (
    "你是蜀道安全助手。只能依据提供的证据回答，不得补充证据之外的法律义务、处罚金额或事故原因。"
    "证据冲突时，优先采用当前有效且权威等级更高的材料。"
    "若证据显示“无可用依据”，必须明确回答“知识库未收录或依据不足”。"
    "回答使用 Markdown 格式：要点用列表呈现，关键要求可加粗，适合多维度对比时可用表格。"
)


class RateLimiter:
    """进程内滑动窗口限流。"""

    def __init__(self):
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events.setdefault(key, [])
            events[:] = [t for t in events if now - t < window_seconds]
            if len(events) >= limit:
                return False
            events.append(now)
            return True


rate_limiter = RateLimiter()
stop_flags: dict[str, bool] = {}


class AiChatService:
    def __init__(self, db: AsyncSession, ctx: AuthContext):
        self.db = db
        self.ctx = ctx

    # ---------- 会话管理 ----------

    async def create_session(self, title: str = "新对话") -> dict:
        await self._check_session_limit()
        session_id = _new_id("sess")
        conv = Conversation(
            session_id=session_id,
            user_id=self.ctx.user_id,
            title=title or "新对话",
            message_count=0,
        )
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return {
            "session_id": conv.session_id,
            "title": conv.title,
            "created_at": conv.created_at,
        }

    async def list_sessions(self, page: int, page_size: int, keyword: str | None) -> dict:
        q = select(Conversation).where(Conversation.user_id == self.ctx.user_id)
        if keyword:
            q = q.where(Conversation.title.like(f"%{keyword}%"))
        total = await self.db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = (
            await self.db.scalars(
                q.order_by(Conversation.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items = [
            {
                "session_id": c.session_id,
                "title": c.title,
                "last_message": c.last_message_preview,
                "message_count": c.message_count,
                "updated_at": c.updated_at,
            }
            for c in rows
        ]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size else 0,
        }

    async def get_messages(self, session_id: str) -> dict:
        conv = await self._get_conversation(session_id)
        msgs = (
            await self.db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc(), Message.message_id.asc())
            )
        ).all()
        messages = [
            {
                "message_id": m.message_id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources_json or "[]"),
                "status": m.status,
                "created_at": m.created_at,
            }
            for m in msgs
        ]
        return {"session_id": conv.session_id, "title": conv.title, "messages": messages}

    async def rename_session(self, session_id: str, title: str) -> dict:
        conv = await self._get_conversation(session_id)
        conv.title = title.strip() or conv.title
        conv.updated_at = now_cst()
        await self.db.commit()
        return {"session_id": conv.session_id, "title": conv.title}

    async def delete_session(self, session_id: str) -> None:
        conv = await self._get_conversation(session_id)
        await self.db.delete(conv)
        await self.db.commit()

    async def batch_delete_sessions(self, session_ids: list[str]) -> None:
        if not session_ids:
            return
        q = select(Conversation).where(
            Conversation.user_id == self.ctx.user_id,
            Conversation.session_id.in_(session_ids),
        )
        for conv in (await self.db.scalars(q)).all():
            await self.db.delete(conv)
        await self.db.commit()

    async def _get_conversation(self, session_id: str) -> Conversation:
        conv = await self.db.get(Conversation, session_id)
        if conv is None or conv.user_id != self.ctx.user_id:
            raise BizError(*ErrorCode.SESSION_NOT_FOUND)
        return conv

    async def _check_session_limit(self) -> None:
        count = await self.db.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == self.ctx.user_id)
        ) or 0
        if count >= 100:
            raise BizError(*ErrorCode.SESSION_LIMIT_EXCEEDED)

    # ---------- 快捷问题 ----------

    async def visible_quick_questions(self) -> dict:
        rows = (
            await self.db.scalars(
                select(QuickQuestion)
                .where(QuickQuestion.is_active == 1)
                .order_by(QuickQuestion.sort_order.desc(), QuickQuestion.question_id.asc())
            )
        ).all()
        categories: dict[str, dict] = {}
        hot: list[str] = []
        for q in rows:
            roles = json.loads(q.roles_json or "[]")
            if roles and self.ctx.role not in roles:
                continue
            bucket = categories.setdefault(
                q.category,
                {"name": q.category, "icon": q.category_icon, "questions": []},
            )
            bucket["questions"].append(q.question)
            if q.is_hot:
                hot.append(q.question)
        return {"categories": list(categories.values()), "hot_questions": hot}

    # ---------- 反馈 ----------

    async def submit_feedback(self, message_id: str, data) -> dict:
        await self._get_assistant_message(message_id)
        exists = await self.db.scalar(
            select(func.count())
            .select_from(MessageFeedback)
            .where(
                MessageFeedback.message_id == message_id,
                MessageFeedback.user_id == self.ctx.user_id,
            )
        )
        if exists:
            raise BizError(*ErrorCode.DUPLICATE_FEEDBACK)
        fb = MessageFeedback(
            message_id=message_id,
            user_id=self.ctx.user_id,
            rating=data.rating,
            reasons_json=json.dumps(data.reasons or [], ensure_ascii=False),
            comment=data.comment,
        )
        self.db.add(fb)
        await self.db.commit()
        return {"message_id": message_id, "rating": data.rating}

    async def remove_feedback(self, message_id: str) -> None:
        await self._get_assistant_message(message_id)
        fb = await self.db.scalar(
            select(MessageFeedback).where(
                MessageFeedback.message_id == message_id,
                MessageFeedback.user_id == self.ctx.user_id,
            )
        )
        if fb is not None:
            await self.db.delete(fb)
            await self.db.commit()

    async def _get_assistant_message(self, message_id: str) -> Message:
        msg = await self.db.get(Message, message_id)
        if msg is None or msg.role != "assistant":
            raise BizError(40401, "消息不存在")
        conv = await self.db.get(Conversation, msg.session_id)
        if conv is None or conv.user_id != self.ctx.user_id:
            raise BizError(*ErrorCode.SESSION_NOT_FOUND)
        return msg

    # ---------- 问答 ----------

    async def _build_prompt(self, question: str, session_id: str | None) -> list[dict]:
        # retrieve 内部已把 embedding/BM25/重排等 CPU 密集操作下沉线程池
        retrieval = await rag_service.retrieve(
            question,
            top_k=5,
            threshold=settings.RAG_RERANK_THRESHOLD,
        )
        sources = retrieval["results"]
        if sources:
            evidence = "\n\n".join(
                f"[{i + 1}] {s.get('title', '')} {s.get('locator', '')}\n{s.get('text', '')}"
                for i, s in enumerate(sources)
            )
        else:
            evidence = "无可用依据"
        system = QA_SYSTEM_PROMPT
        messages = [{"role": "system", "content": system}]
        if session_id:
            history = (
                await self.db.scalars(
                    select(Message)
                    .where(Message.session_id == session_id)
                    .order_by(Message.created_at.desc())
                    .limit(10)
                )
            ).all()
            history.reverse()
            for m in history:
                messages.append({"role": m.role, "content": m.content})
        messages.append(
            {
                "role": "user",
                "content": f"证据：\n{evidence}\n\n问题：{question}",
            }
        )
        return messages, sources

    async def prepare_chat(self, question: str, session_id: str | None) -> dict:
        question = question.strip()
        if not question or len(question) > 500:
            raise BizError(*ErrorCode.VALIDATION_FAILED)
        if not await llm_service.resolve_config(self.db):
            raise BizError(*ErrorCode.AI_UNAVAILABLE)
        if not rate_limiter.allow(self.ctx.user_id, settings.AI_RATE_LIMIT_PER_MIN):
            raise BizError(*ErrorCode.AI_RATE_LIMITED)

        sensitive = await SensitiveWordFilter.load_async(self.db)
        if not sensitive.filter_input(question).passed:
            raise BizError(*ErrorCode.SENSITIVE_CONTENT)

        if session_id:
            conv = await self._get_conversation(session_id)
        else:
            await self._check_session_limit()
            session_id = _new_id("sess")
            title = question[:30]
            conv = Conversation(
                session_id=session_id,
                user_id=self.ctx.user_id,
                title=title,
                message_count=0,
            )
            self.db.add(conv)

        user_msg = Message(
            message_id=_new_id("msg"),
            session_id=session_id,
            role="user",
            content=question,
            status="completed",
        )
        self.db.add(user_msg)
        conv.message_count += 1
        conv.last_message_preview = question[:100]
        conv.updated_at = now_cst()
        await self.db.commit()

        return {"session_id": session_id, "user_message_id": user_msg.message_id}

    async def stream_answer(self, question: str, session_id: str) -> AsyncIterator[str]:
        messages, sources = await self._build_prompt(question, session_id)
        # 每次生成前重新解析生效模型：管理员在模型管理里切换后无需重启即可生效
        cfg = await llm_service.resolve_config(self.db)
        if not cfg:
            raise BizError(*ErrorCode.AI_UNAVAILABLE)
        assistant_id = _new_id("msg")
        conv = await self._get_conversation(session_id)
        assistant_msg = Message(
            message_id=assistant_id,
            session_id=session_id,
            role="assistant",
            content="",
            sources_json=json.dumps(sources, ensure_ascii=False),
            status="completed",
            token_count=0,
        )
        self.db.add(assistant_msg)
        conv.message_count += 1
        conv.updated_at = now_cst()
        await self.db.commit()

        stop_flags[assistant_id] = False
        parts: list[str] = []
        started = time.time()
        try:
            # llm_service.stream_chat 为 AsyncOpenAI 异步流式调用，
            # async for 逐 token 消费，事件循环不被阻塞
            async for token in llm_service.stream_chat(messages, cfg):
                if stop_flags.get(assistant_id):
                    break
                parts.append(token)
                yield _sse("token", token)
            content = "".join(parts)
            sensitive = await SensitiveWordFilter.load_async(self.db)
            filtered = sensitive.filter_output(content)
            assistant_msg.content = filtered.text
            assistant_msg.token_count = len(content)
            assistant_msg.status = "interrupted" if stop_flags.get(assistant_id) else "completed"
            conv.last_message_preview = assistant_msg.content[:100]
            conv.updated_at = now_cst()
            self._write_audit(
                question,
                assistant_msg.content,
                sources,
                start_time=started,
                session_id=session_id,
                filter_action="output_filtered" if filtered.matched else "passed",
                token_input=sum(len(m.get("content", "")) for m in messages),
                token_output=len(content),
                model_used=cfg["model_name"],
            )
            await self.db.commit()
            yield _sse("sources", json.dumps(sources, ensure_ascii=False))
            yield _sse("done", json.dumps(
                {"session_id": session_id, "message_id": assistant_id}, ensure_ascii=False
            ))
        except BizError as exc:
            assistant_msg.status = "interrupted"
            await self.db.commit()
            yield _sse("error", json.dumps({"code": exc.code, "message": exc.message}, ensure_ascii=False))
        finally:
            stop_flags.pop(assistant_id, None)

    def _write_audit(self, question, answer, sources, start_time, session_id, filter_action, token_input, token_output, model_used):
        self.db.add(
            AiAuditLog(
                session_id=session_id,
                user_id=self.ctx.user_id,
                user_question=question,
                ai_answer=answer,
                model_used=model_used,
                response_time_ms=int((time.time() - start_time) * 1000),
                sources_json=json.dumps(sources, ensure_ascii=False),
                filter_action=filter_action,
                token_input=token_input,
                token_output=token_output,
                scene="qa",
            )
        )

    async def stop_generation(self, message_id: str) -> None:
        await self._get_assistant_message(message_id)
        stop_flags[message_id] = True


def build_chat_service(db: AsyncSession, ctx: AuthContext) -> AiChatService:
    return AiChatService(db, ctx)
