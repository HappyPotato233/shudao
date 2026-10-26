"""AI 问答满意度统计接口测试

覆盖 GET /api/v1/statistics/ai-satisfaction（Admin only）：
- 权限：非 Admin 访问 40303
- 空数据聚合
- 造数据聚合校验（点赞率、踩原因分布、问答审计统计）
- days / date_from / date_to 时间过滤
"""
import json

from app.core.config import settings
from app.models.ai_orm import AiAuditLog, Conversation, Message, MessageFeedback

API = settings.API_V1_PREFIX

URL = f"{API}/statistics/ai-satisfaction"


def _seed_session(db) -> str:
    """创建一条会话（消息外键依赖），返回 session_id。"""
    session_id = "sess_statistics_test"
    db.add(Conversation(session_id=session_id, user_id="U002", title="统计测试会话"))
    db.commit()
    return session_id


def _seed_assistant_messages(db, session_id: str, message_ids: list[str]) -> None:
    for mid in message_ids:
        db.add(
            Message(
                message_id=mid,
                session_id=session_id,
                role="assistant",
                content=f"回答-{mid}",
                status="completed",
            )
        )
    db.commit()


def _add_feedback(db, message_id: str, rating: str, reasons: list[str] | None = None, created_at: str | None = None):
    fb = MessageFeedback(
        message_id=message_id,
        user_id="U002",
        rating=rating,
        reasons_json=json.dumps(reasons, ensure_ascii=False) if reasons else None,
    )
    if created_at:
        fb.created_at = created_at
    db.add(fb)


def test_ai_satisfaction_non_admin_forbidden(client, auth_headers):
    resp = client.get(URL, headers=auth_headers("zhangsan"))
    assert resp.status_code == 403
    assert resp.json()["code"] == 40303


def test_ai_satisfaction_empty_data(client, auth_headers):
    resp = client.get(URL, headers=auth_headers("admin"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_feedback_count"] == 0
    assert data["like_count"] == 0
    assert data["dislike_count"] == 0
    assert data["like_rate"] == 0
    assert data["dislike_reasons"] == {
        "inaccurate": 0,
        "incomplete": 0,
        "misunderstanding": 0,
        "off_topic": 0,
        "other": 0,
    }


def test_ai_satisfaction_aggregates_feedbacks(client, auth_headers, db):
    session_id = _seed_session(db)
    _seed_assistant_messages(db, session_id, [f"msg_stat_{i}" for i in range(1, 6)])

    # 2 条 like + 3 条 dislike，原因各不相同（含一个未定义原因 spam，应被忽略）
    _add_feedback(db, "msg_stat_1", "like")
    _add_feedback(db, "msg_stat_2", "like")
    _add_feedback(db, "msg_stat_3", "dislike", reasons=["inaccurate"])
    _add_feedback(db, "msg_stat_4", "dislike", reasons=["incomplete", "other"])
    _add_feedback(db, "msg_stat_5", "dislike", reasons=["misunderstanding", "inaccurate", "spam"])

    # 问答审计日志：2 次 glm-4 + 1 次 glm-5
    db.add_all(
        [
            AiAuditLog(user_id="U002", user_question="q1", model_used="glm-4", response_time_ms=100),
            AiAuditLog(user_id="U002", user_question="q2", model_used="glm-4", response_time_ms=300),
            AiAuditLog(user_id="U002", user_question="q3", model_used="glm-5", response_time_ms=200),
        ]
    )
    db.commit()

    resp = client.get(URL, headers=auth_headers("admin"))
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["total_feedback_count"] == 5
    assert data["like_count"] == 2
    assert data["dislike_count"] == 3
    assert data["like_rate"] == 0.4
    assert data["dislike_reasons"] == {
        "inaccurate": 2,
        "incomplete": 1,
        "misunderstanding": 1,
        "off_topic": 0,
        "other": 1,
    }

    assert data["total_questions"] == 3
    assert data["avg_response_time_ms"] == 200.0
    assert data["model_usage"][0] == {"model": "glm-4", "count": 2}


def test_ai_satisfaction_days_filter_excludes_old(client, auth_headers, db):
    session_id = _seed_session(db)
    _seed_assistant_messages(db, session_id, ["msg_stat_old", "msg_stat_new"])

    _add_feedback(db, "msg_stat_old", "dislike", reasons=["inaccurate"], created_at="2020-01-01T00:00:00")
    _add_feedback(db, "msg_stat_new", "like")  # 默认 created_at=now
    db.commit()

    resp = client.get(URL, params={"days": 30}, headers=auth_headers("admin"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_feedback_count"] == 1
    assert data["like_count"] == 1
    assert data["dislike_count"] == 0
    assert data["dislike_reasons"]["inaccurate"] == 0

    # 不传 days 则统计全部
    data = client.get(URL, headers=auth_headers("admin")).json()["data"]
    assert data["total_feedback_count"] == 2


def test_ai_satisfaction_date_range_filters(client, auth_headers, db):
    session_id = _seed_session(db)
    _seed_assistant_messages(db, session_id, ["msg_stat_old", "msg_stat_new"])

    _add_feedback(db, "msg_stat_old", "like", created_at="2020-01-01T00:00:00")
    _add_feedback(db, "msg_stat_new", "dislike", reasons=["incomplete"])
    db.commit()

    # date_from：过滤掉 2020 年的旧点赞
    data = client.get(
        URL, params={"date_from": "2025-01-01"}, headers=auth_headers("admin")
    ).json()["data"]
    assert data["total_feedback_count"] == 1
    assert data["dislike_count"] == 1
    assert data["like_rate"] == 0

    # date_to：只统计 2020 年的旧点赞
    data = client.get(
        URL, params={"date_to": "2020-12-31"}, headers=auth_headers("admin")
    ).json()["data"]
    assert data["total_feedback_count"] == 1
    assert data["like_count"] == 1
    assert data["like_rate"] == 1

    # 非法日期格式：40001
    resp = client.get(
        URL, params={"date_from": "2025/01/01"}, headers=auth_headers("admin")
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40001
