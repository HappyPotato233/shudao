"""消息通知服务（async）"""
import datetime
import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext
from app.core.response import BizError
from app.models.hazard import Hazard
from app.models.notification import Notification, NotificationPreference

HAZARD_TYPES = {"hazard_assigned", "rectification_submitted", "review_result", "rectification_urge"}
ALL_TYPES = HAZARD_TYPES
PREF_FIELDS = [
    "hazard_assigned",
    "rectification_submitted",
    "review_result",
    "rectification_urge",
]


def create_notification(
    db,
    user_id: str,
    type_: str,
    title: str,
    content: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> Notification:
    """创建通知记录（纯 db.add 无 IO，同步/AsyncSession 均可，由调用方 commit）。"""
    n = Notification(
        notification_id="notif_" + uuid.uuid4().hex[:12],
        user_id=user_id,
        type=type_,
        title=title,
        content=content,
        target_type=target_type,
        target_id=target_id,
        is_read=0,
    )
    db.add(n)
    return n


async def send_to_users(
    db: AsyncSession,
    user_ids: list[str],
    title: str,
    content: str,
    type_: str = "system_message",
) -> list[dict]:
    """管理员向指定用户推送消息，返回发送记录。"""
    records: list[dict] = []
    for user_id in user_ids:
        n = create_notification(db, user_id, type_, title, content)
        records.append(
            {
                "notification_id": n.notification_id,
                "user_id": user_id,
                "title": title,
                "content": content,
                "type": type_,
                "created_at": n.created_at,
            }
        )
    await db.commit()
    return records


def to_dict(n: Notification) -> dict:
    return {
        "notification_id": n.notification_id,
        "type": n.type,
        "title": n.title,
        "content": n.content,
        "is_read": bool(n.is_read),
        "target_type": n.target_type,
        "target_id": n.target_id,
        "created_at": n.created_at,
    }


async def list_notifications(
    db: AsyncSession,
    ctx: AuthContext,
    read_status: str = "all",
    type_: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    q = select(Notification).where(Notification.user_id == ctx.user_id)
    if read_status == "unread":
        q = q.where(Notification.is_read == 0)
    elif read_status == "read":
        q = q.where(Notification.is_read == 1)
    if type_:
        types = [t for t in type_.split(",") if t]
        if types:
            q = q.where(Notification.type.in_(types))
    if category == "hazard":
        q = q.where(Notification.type.in_(list(HAZARD_TYPES)))

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    q = (
        q.order_by(Notification.is_read.asc(), Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(q)).scalars().all()
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [to_dict(n) for n in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def unread_count(db: AsyncSession, ctx: AuthContext) -> dict:
    rows = (
        await db.execute(
            select(Notification.type, func.count())
            .where(Notification.user_id == ctx.user_id, Notification.is_read == 0)
            .group_by(Notification.type)
        )
    ).all()
    by_type = {t: c for t, c in rows}
    total = sum(by_type.values())
    return {
        "total": total,
        "by_category": {
            "hazard": sum(by_type.get(t, 0) for t in HAZARD_TYPES),
        },
        "by_type": {t: by_type.get(t, 0) for t in ALL_TYPES},
    }


async def get_notification(db: AsyncSession, ctx: AuthContext, notification_id: str) -> Notification:
    n = (
        await db.execute(
            select(Notification).where(
                Notification.notification_id == notification_id,
                Notification.user_id == ctx.user_id,
            )
        )
    ).scalar_one_or_none()
    if n is None:
        raise BizError(40400, "通知不存在", 404)
    return n


async def mark_read(db: AsyncSession, ctx: AuthContext, notification_id: str) -> None:
    n = await get_notification(db, ctx, notification_id)
    n.is_read = 1
    await db.commit()


async def mark_all_read(db: AsyncSession, ctx: AuthContext) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == ctx.user_id, Notification.is_read == 0)
        .values(is_read=1)
    )
    await db.commit()


async def delete_notification(db: AsyncSession, ctx: AuthContext, notification_id: str) -> None:
    n = await get_notification(db, ctx, notification_id)
    await db.delete(n)
    await db.commit()


async def batch_delete(db: AsyncSession, ctx: AuthContext, notification_ids: list[str]) -> None:
    await db.execute(
        delete(Notification).where(
            Notification.user_id == ctx.user_id,
            Notification.notification_id.in_(notification_ids),
        )
    )
    await db.commit()


def _parse_dt(value: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.datetime.combine(datetime.date.fromisoformat(value[:10]), datetime.time())
        except Exception:
            return None


async def send_due_urge_notifications(db: AsyncSession) -> None:
    """对整改截止前 24 小时仍未反馈的隐患发送催办通知（每小时调度一次）。"""
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    cutoff = (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    hazards = (
        (
            await db.execute(
                select(Hazard)
                .where(Hazard.status == "processing")
                # AsyncSession 下 lazy load 会触发 MissingGreenlet，预加载 assignments
                .options(selectinload(Hazard.assignments))
            )
        )
        .scalars()
        .all()
    )
    for h in hazards:
        assignment = sorted(h.assignments, key=lambda a: a.created_at or "")[-1] if h.assignments else None
        if assignment is None:
            continue
        deadline = _parse_dt(assignment.deadline)
        if deadline is None or deadline < now or deadline > now + datetime.timedelta(hours=24):
            continue
        already = (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == assignment.assignee_id,
                    Notification.type == "rectification_urge",
                    Notification.target_id == h.hazard_id,
                    Notification.created_at >= cutoff,
                )
            )
        ).scalar_one_or_none()
        if already:
            continue
        create_notification(
            db,
            assignment.assignee_id,
            "rectification_urge",
            "整改催办",
            f"隐患[{h.hazard_id}]整改截止日期临近，请尽快提交整改反馈。",
            "hazard",
            h.hazard_id,
        )
    await db.commit()


async def get_preferences(db: AsyncSession, ctx: AuthContext) -> dict:
    row = await db.get(NotificationPreference, ctx.user_id)
    if row is None:
        row = NotificationPreference(user_id=ctx.user_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return {field: bool(getattr(row, field)) for field in PREF_FIELDS}


async def update_preferences(db: AsyncSession, ctx: AuthContext, prefs: dict) -> dict:
    row = await db.get(NotificationPreference, ctx.user_id)
    if row is None:
        row = NotificationPreference(user_id=ctx.user_id)
        db.add(row)
    for field in PREF_FIELDS:
        if field in prefs:
            setattr(row, field, 1 if bool(prefs[field]) else 0)
    await db.commit()
    return await get_preferences(db, ctx)


async def cleanup_expired_notifications(db: AsyncSession) -> None:
    """删除超过 90 天的通知（DATABASE.md 保留策略）。"""
    tz = datetime.timezone(datetime.timedelta(hours=8))
    cutoff = (datetime.datetime.now(tz) - datetime.timedelta(days=90)).strftime(
        "%Y-%m-%dT%H:%M:%S+08:00"
    )
    await db.execute(delete(Notification).where(Notification.created_at < cutoff))
    await db.commit()
