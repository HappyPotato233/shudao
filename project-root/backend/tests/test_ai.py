"""AI 智能助手模块测试"""
import asyncio
import json

from sqlalchemy import select

from app.core.config import settings
from app.models.ai_orm import SensitiveWord
from app.services.llm import llm_service
from app.services.rag import rag_service
from app.services.rag import RagService, _embedding_text
from app.services.ai_chat import AiChatService, RateLimiter
from app.services.sensitive_word import SensitiveWordFilter

API = settings.API_V1_PREFIX


def test_sensitive_word_filter_blocks_and_masks(client, db):
    # 词库从测试库加载（init_db 预置了 赌博/毒品 等敏感词）
    words = [
        w for (w,) in db.execute(
            select(SensitiveWord.word).where(SensitiveWord.is_active == 1)
        )
    ]
    f = SensitiveWordFilter(words=words)

    blocked = f.filter_input("请问哪里可以赌博")
    assert blocked.passed is False
    assert "赌博" in blocked.matched

    masked = f.filter_output("请远离赌博、毒品等违法内容")
    assert masked.text == "请远离***、***等违法内容"
    assert set(masked.matched) == {"赌博", "毒品"}

    clean = f.filter_input("高处作业安全带的使用标准是什么")
    assert clean.passed is True
    assert clean.matched == []


def test_create_and_list_sessions(client, auth_headers):
    headers = auth_headers("zhangsan")
    created = client.post(f"{API}/ai/sessions", headers=headers)
    assert created.status_code == 200
    assert created.json()["code"] == 0
    session_id = created.json()["data"]["session_id"]
    assert session_id.startswith("sess_")

    listed = client.get(f"{API}/ai/sessions", headers=headers)
    assert listed.status_code == 200
    ids = [i["session_id"] for i in listed.json()["data"]["items"]]
    assert session_id in ids


def test_rename_and_delete_session(client, auth_headers):
    headers = auth_headers("zhangsan")
    session_id = client.post(f"{API}/ai/sessions", headers=headers).json()["data"]["session_id"]
    renamed = client.put(
        f"{API}/ai/sessions/{session_id}",
        json={"title": "新标题"},
        headers=headers,
    )
    assert renamed.json()["data"]["title"] == "新标题"

    deleted = client.delete(f"{API}/ai/sessions/{session_id}", headers=headers)
    assert deleted.json()["code"] == 0
    assert client.get(
        f"{API}/ai/sessions/{session_id}/messages", headers=headers
    ).json()["code"] == 40402


def test_session_list_respects_owner(client, auth_headers):
    zh = auth_headers("zhangsan")
    li = auth_headers("lisi")
    sid_zh = client.post(f"{API}/ai/sessions", headers=zh).json()["data"]["session_id"]
    sid_li = client.post(f"{API}/ai/sessions", headers=li).json()["data"]["session_id"]

    zh_ids = [i["session_id"] for i in client.get(f"{API}/ai/sessions", headers=zh).json()["data"]["items"]]
    assert sid_zh in zh_ids
    assert sid_li not in zh_ids


def test_feedback_duplicate_and_cancel(client, auth_headers, db):
    headers = auth_headers("zhangsan")
    session_id = client.post(f"{API}/ai/sessions", headers=headers).json()["data"]["session_id"]
    from app.models.ai_orm import Message

    msg = Message(
        message_id="msg_feedback1",
        session_id=session_id,
        role="assistant",
        content="测试回答",
        status="completed",
    )
    db.add(msg)
    db.commit()

    first = client.post(
        f"{API}/ai/messages/msg_feedback1/feedback",
        json={"rating": "like"},
        headers=headers,
    )
    assert first.json()["code"] == 0
    dup = client.post(
        f"{API}/ai/messages/msg_feedback1/feedback",
        json={"rating": "dislike"},
        headers=headers,
    )
    assert dup.json()["code"] == 40012
    cancelled = client.delete(
        f"{API}/ai/messages/msg_feedback1/feedback", headers=headers
    )
    assert cancelled.json()["code"] == 0


def test_chat_sse_and_persistence(client, auth_headers, monkeypatch):
    monkeypatch.setattr(llm_service, "is_configured", staticmethod(lambda: True))

    async def _fake_stream(messages):
        for token in ["根据", "规范", "回答"]:
            yield token

    monkeypatch.setattr(llm_service, "stream_chat", _fake_stream)

    async def _fake_retrieve(query, top_k=5, threshold=None, filters=None):
        return {
            "results": [
                {
                    "evidence_id": "ev_test",
                    "document_id": "doc_test",
                    "title": "测试规范",
                    "locator": "第1条",
                    "source_uri": "https://example.test",
                    "text": "证据正文",
                    "score": 0.9,
                }
            ],
            "no_evidence": False,
        }

    monkeypatch.setattr(rag_service, "retrieve", _fake_retrieve)

    headers = auth_headers("zhangsan")
    resp = client.post(
        f"{API}/ai/chat",
        json={"question": "高处作业安全带使用标准？"},
        headers=headers,
    )
    assert resp.status_code == 200
    text = resp.text
    assert "event: token" in text
    assert "event: done" in text
    assert "sess_" in text
    assert "msg_" in text

    from sqlalchemy import func

    from app.models.ai_orm import AiAuditLog, Message
    from app.models.base import AsyncSessionLocal

    async def _check_persistence():
        async with AsyncSessionLocal() as adb:
            user_cnt = await adb.scalar(
                select(func.count()).select_from(Message).where(Message.role == "user")
            )
            assistant_cnt = await adb.scalar(
                select(func.count()).select_from(Message).where(Message.role == "assistant")
            )
            audit_cnt = await adb.scalar(select(func.count()).select_from(AiAuditLog))
            assert user_cnt >= 1
            assert assistant_cnt >= 1
            assert audit_cnt >= 1

    asyncio.run(_check_persistence())


def test_rate_limiter_rejects_after_window(client):
    limiter = RateLimiter()
    for _ in range(10):
        assert limiter.allow("u1", 10) is True
    assert limiter.allow("u1", 10) is False
    # 不同用户不受影响
    assert limiter.allow("u2", 10) is True


def test_embedding_text_composition():
    text = _embedding_text("标题", "法律", "主题", "第五条", "正文")
    assert "标题：标题" in text
    assert "类型：法律" in text
    assert "主题：主题" in text
    assert "位置：第五条" in text
    assert "正文：正文" in text


def test_rag_read_evidence_is_nonempty(db):
    # KB 数据已迁入业务库 kb_* 表，测试库造数后验证读取链路
    from tests.test_rag import _add_kb_document, _add_kb_evidence, _add_kb_entry

    _add_kb_document(db, "doc_r", "src_r", "当前有效候选", "国家")
    _add_kb_entry(db, "k_r", "doc_r", 0)
    _add_kb_evidence(db, "ev_r", "doc_r")
    db.commit()

    rows = asyncio.run(RagService().read_evidence(limit=3))
    assert rows
    assert all(r["evidence_id"] and r["text"] for r in rows)


def test_chat_sensitive_word_blocks(client, auth_headers, monkeypatch):
    monkeypatch.setattr(llm_service, "is_configured", staticmethod(lambda: True))

    async def _fake_retrieve(query, top_k=5, threshold=None, filters=None):
        return {"results": [], "no_evidence": True}

    monkeypatch.setattr(rag_service, "retrieve", _fake_retrieve)
    headers = auth_headers("zhangsan")
    resp = client.post(
        f"{API}/ai/chat",
        json={"question": "请问赌博怎么玩"},
        headers=headers,
    )
    assert "event: error" in resp.text
    assert "40201" in resp.text


def test_chat_not_configured_returns_40203(client, auth_headers, monkeypatch):
    monkeypatch.setattr(llm_service, "is_configured", staticmethod(lambda: False))
    headers = auth_headers("zhangsan")
    resp = client.post(
        f"{API}/ai/chat",
        json={"question": "安全生产法有哪些要求？"},
        headers=headers,
    )
    assert "event: error" in resp.text
    assert "40203" in resp.text


def test_stop_generation_marks_interrupted(client, auth_headers, monkeypatch):
    monkeypatch.setattr(llm_service, "is_configured", staticmethod(lambda: True))

    async def _fake_stream(messages):
        for token in ["token1", "token2"]:
            yield token

    monkeypatch.setattr(llm_service, "stream_chat", _fake_stream)

    async def _fake_retrieve(query, top_k=5, threshold=None, filters=None):
        return {"results": [], "no_evidence": True}

    monkeypatch.setattr(rag_service, "retrieve", _fake_retrieve)

    import app.services.ai_chat as chat_mod

    # 固定 assistant 消息 id，便于在流开始后调用 stop
    monkeypatch.setattr(chat_mod, "_new_id", lambda prefix: "msg_stop" if prefix == "msg" else f"{prefix}_x")
    headers = auth_headers("zhangsan")
    sid = client.post(f"{API}/ai/sessions", headers=headers).json()["data"]["session_id"]

    async def _run():
        import asyncio

        from app.models.base import AsyncSessionLocal

        async with AsyncSessionLocal() as adb:
            svc = AiChatService(adb, _fake_ctx("zhangsan"))
            gen = svc.stream_answer("测试问题", sid)
            first = await anext(gen)
            assert "event: token" in first
            await svc.stop_generation("msg_stop")
            async for _chunk in gen:
                pass
            from app.models.ai_orm import Message

            msg = await adb.get(Message, "msg_stop")
            assert msg.status == "interrupted"

    import asyncio

    asyncio.run(_run())


def _fake_ctx(user_id):
    from app.api.deps import AuthContext

    return AuthContext(
        user_id="U002" if user_id == "zhangsan" else "U001",
        username=user_id,
        name="张三" if user_id == "zhangsan" else "系统管理员",
        role="User" if user_id == "zhangsan" else "Admin",
        department="安全生产部",
        project="成绵高速扩容项目",
        jti="test",
    )


def test_ai_satisfaction_date_range_filter(client, auth_headers, db):
    from app.models.ai_orm import Message, MessageFeedback

    headers = auth_headers("admin")
    sid = client.post(
        f"{API}/ai/sessions", headers=auth_headers("zhangsan")
    ).json()["data"]["session_id"]

    db.add_all(
        [
            Message(
                message_id="msg_stat_old",
                session_id=sid,
                role="assistant",
                content="旧回答",
                status="completed",
                created_at="2020-01-01T00:00:00",
            ),
            Message(
                message_id="msg_stat_new",
                session_id=sid,
                role="assistant",
                content="新回答",
                status="completed",
            ),
        ]
    )
    db.add_all(
        [
            MessageFeedback(
                message_id="msg_stat_old",
                user_id="U002",
                rating="like",
                created_at="2020-01-01T00:00:00",
            ),
            MessageFeedback(
                message_id="msg_stat_new",
                user_id="U002",
                rating="dislike",
            ),
        ]
    )
    db.commit()

    # date_from 过滤掉 2020 年的旧反馈
    resp = client.get(
        f"{API}/statistics/ai-satisfaction",
        params={"date_from": "2025-01-01"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_feedback_count"] == 1
    assert data["dislike_count"] == 1
    assert data["like_rate"] == 0

    # date_to 只统计 2020 年的旧反馈
    resp = client.get(
        f"{API}/statistics/ai-satisfaction",
        params={"date_to": "2020-12-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_feedback_count"] == 1
    assert data["like_count"] == 1
    assert data["like_rate"] == 1

    # 组合范围无数据时 like_rate 为 0，不抛除零错误
    resp = client.get(
        f"{API}/statistics/ai-satisfaction",
        params={"date_from": "2030-01-01", "date_to": "2030-12-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_feedback_count"] == 0
    assert data["like_rate"] == 0
