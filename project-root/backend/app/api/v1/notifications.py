"""消息通知接口（H08）"""
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context_async
from app.core.permissions import require_roles_async
from app.core.response import success
from app.models.base import get_db
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["消息通知"])


@router.post("/send", summary="管理员推送消息")
async def send_notification(
    payload: dict = Body(...),
    ctx: AuthContext = Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    """管理员向指定用户推送消息。"""
    user_ids = payload.get("user_ids") or []
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    type_ = payload.get("type") or "system_message"
    if not user_ids:
        from app.core.response import BizError

        raise BizError(40001, "请选择目标用户")
    if not title or not content:
        from app.core.response import BizError

        raise BizError(40001, "标题和内容不能为空")
    records = await notification_service.send_to_users(db, user_ids, title, content, type_)
    return success({"sent": records, "count": len(records)})


@router.get("", summary="消息列表")
async def list_notifications(
    page: int = Query(1),
    page_size: int = Query(20),
    read_status: str = Query("all"),
    type: str | None = Query(None),
    category: str | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(
        await notification_service.list_notifications(db, ctx, read_status, type, category, page, page_size)
    )


@router.get("/unread-count", summary="未读消息数量")
async def unread_count(
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await notification_service.unread_count(db, ctx))


@router.post("/read-all", summary="全部标记已读")
async def read_all(
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    await notification_service.mark_all_read(db, ctx)
    return success(None, message="已全部标记为已读")


@router.post("/batch-delete", summary="批量删除消息")
async def batch_delete(
    payload: dict = Body(...),
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    ids = payload.get("notification_ids") or []
    await notification_service.batch_delete(db, ctx, ids)
    return success(None, message="批量删除成功")


@router.get("/preferences", summary="获取通知偏好")
async def get_preferences(
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await notification_service.get_preferences(db, ctx))


@router.put("/preferences", summary="更新通知偏好")
async def update_preferences(
    payload: dict = Body(...),
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await notification_service.update_preferences(db, ctx, payload))


@router.get("/{notification_id}", summary="消息详情")
async def get_notification(
    notification_id: str,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    n = await notification_service.get_notification(db, ctx, notification_id)
    return success(notification_service.to_dict(n))


@router.put("/{notification_id}/read", summary="标记已读")
async def mark_read(
    notification_id: str,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    await notification_service.mark_read(db, ctx, notification_id)
    return success(None, message="已标记为已读")


@router.delete("/{notification_id}", summary="删除消息")
async def delete_notification(
    notification_id: str,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    await notification_service.delete_notification(db, ctx, notification_id)
    return success(None, message="已删除")
