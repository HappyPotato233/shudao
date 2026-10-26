"""消息通知接口测试"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

API = settings.API_V1_PREFIX

# 动态未来截止日期（+30 天），避免硬编码日期过期导致"整改截止日期不合法"
_FUTURE_DEADLINE = (
    datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=30)
).isoformat(timespec="seconds")


def _report_and_assign(client, reporter, assignee_headers):
    resp = client.post(
        f"{API}/hazards",
        data={
            "title": "通知测试隐患",
            "description": "用于验证自动通知的隐患描述内容",
            "level": "minor",
            "category": "fire_safety",
            "location": "测试点位",
            "occurred_at": "2026-08-14T09:00:00+08:00",
            "project": "成绵高速扩容项目",
        },
        files=[("images", ("a.jpg", b"x", "image/jpeg"))],
        headers=reporter,
    )
    hid = resp.json()["data"]["hazard_id"]
    client.post(
        f"{API}/hazards/{hid}/assign",
        data={"assignee_id": "U005", "requirements": "立即整改", "deadline": _FUTURE_DEADLINE, "priority": "medium"},
        headers=reporter,
    )
    return hid


def test_auto_notify_and_list(client, auth_headers):
    li = auth_headers("lisi")
    zhao = auth_headers("zhaoliu")
    hid = _report_and_assign(client, li, zhao)
    items = client.get(f"{API}/notifications", headers=zhao).json()["data"]["items"]
    assert any(n["type"] == "hazard_assigned" and n["target_id"] == hid for n in items)
    assert items[0]["is_read"] is False


def test_unread_count(client, auth_headers):
    li = auth_headers("lisi")
    zhao = auth_headers("zhaoliu")
    _report_and_assign(client, li, zhao)
    data = client.get(f"{API}/notifications/unread-count", headers=zhao).json()["data"]
    assert data["total"] >= 1
    assert data["by_category"]["hazard"] >= 1


def test_mark_read_and_delete(client, auth_headers):
    li = auth_headers("lisi")
    zhao = auth_headers("zhaoliu")
    hid = _report_and_assign(client, li, zhao)
    items = client.get(f"{API}/notifications", headers=zhao).json()["data"]["items"]
    target = [n for n in items if n["target_id"] == hid][0]
    nid = target["notification_id"]
    client.put(f"{API}/notifications/{nid}/read", headers=zhao)
    detail = client.get(f"{API}/notifications/{nid}", headers=zhao).json()["data"]
    assert detail["is_read"] is True
    client.delete(f"{API}/notifications/{nid}", headers=zhao)
    assert client.get(f"{API}/notifications/{nid}", headers=zhao).json()["code"] == 40400


def test_send_due_urge_notifications(client, auth_headers, db):
    import datetime

    from sqlalchemy import select

    from app.models.hazard import Hazard, HazardAssignment
    from app.models.notification import Notification
    from app.services.notification_service import send_due_urge_notifications

    deadline = (
        datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        + datetime.timedelta(hours=12)
    ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    hid = "HD-20260814-9999"
    db.add(
        Hazard(
            hazard_id=hid,
            title="t",
            description="d",
            level="minor",
            category="fire_safety",
            location="l",
            project="成绵高速扩容项目",
            reporter_id="U002",
            status="processing",
            occurred_at="2026-08-14T00:00:00+08:00",
        )
    )
    db.flush()
    db.add(
        HazardAssignment(
            hazard_id=hid,
            assigner_id="U002",
            assignee_id="U003",
            requirements="立即整改",
            deadline=deadline,
            priority="high",
        )
    )
    db.commit()

    # send_due_urge_notifications 已 async 化：用临时 event loop + AsyncSession 调用
    import asyncio

    from app.models.base import AsyncSessionLocal

    async def _run_urge():
        async with AsyncSessionLocal() as adb:
            await send_due_urge_notifications(adb)

    asyncio.run(_run_urge())

    n = db.scalar(
        select(Notification).where(
            Notification.type == "rectification_urge",
            Notification.target_id == hid,
        )
    )
    assert n is not None
    assert n.user_id == "U003"


def test_notification_preferences(client, auth_headers):
    li = auth_headers("lisi")
    prefs = client.get(f"{API}/notifications/preferences", headers=li).json()["data"]
    assert prefs["hazard_assigned"] is True
    updated = client.put(
        f"{API}/notifications/preferences",
        json={"hazard_assigned": False},
        headers=li,
    ).json()["data"]
    assert updated["hazard_assigned"] is False


def test_cleanup_expired_notifications(client, auth_headers, db):
    import datetime

    from app.models.notification import Notification
    from app.services.notification_service import cleanup_expired_notifications

    tz = datetime.timezone(datetime.timedelta(hours=8))
    old = (datetime.datetime.now(tz) - datetime.timedelta(days=91)).strftime(
        "%Y-%m-%dT%H:%M:%S+08:00"
    )
    nid = "notif_old123456"
    db.add(
        Notification(
            notification_id=nid,
            user_id="U003",
            type="hazard_assigned",
            title="old",
            content="old",
            created_at=old,
            is_read=0,
        )
    )
    db.commit()

    # cleanup_expired_notifications 已 async 化：用临时 event loop + AsyncSession 调用
    import asyncio

    from app.models.base import AsyncSessionLocal

    async def _run_cleanup():
        async with AsyncSessionLocal() as adb:
            await cleanup_expired_notifications(adb)

    asyncio.run(_run_cleanup())
    db.expire_all()  # 绕过 identity map 缓存，确保读到异步删除后的真实状态
    assert db.get(Notification, nid) is None
