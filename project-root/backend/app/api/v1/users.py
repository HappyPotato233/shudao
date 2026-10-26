"""用户列表（派单选人用）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext, get_auth_context_async
from app.core.permissions import require_roles_async
from app.core.response import success
from app.models.base import get_db
from app.models.user_orm import User
from app.schemas.user import UserCreateRequest, UserUpdateRequest
from app.services import user_service

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", summary="用户列表")
async def list_users(
    keyword: str | None = Query(None),
    department: str | None = Query(None),
    project: str | None = Query(None),
    page: int = Query(1),
    page_size: int = Query(20),
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    q = select(User).where(User.is_active == 1).options(selectinload(User.role))
    if keyword:
        kw = f"%{keyword}%"
        q = q.where(or_(User.username.like(kw), User.name.like(kw)))
    if department:
        q = q.where(User.department == department)
    if project:
        q = q.where(User.project == project)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    users = (
        (
            await db.execute(
                q.order_by(User.user_id).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return success(
        {
            "items": [u.to_info() for u in users],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        }
    )


@router.post("", summary="创建用户")
async def create_user(
    req: UserCreateRequest,
    ctx: AuthContext = Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    """管理员创建用户。"""
    return success(await user_service.create_user(db, req))


@router.put("/{user_id}", summary="编辑用户信息")
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    ctx: AuthContext = Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    """管理员编辑用户信息。"""
    return success(await user_service.update_user(db, user_id, req))


@router.delete("/{user_id}", summary="删除用户（软删除）")
async def delete_user(
    user_id: str,
    ctx: AuthContext = Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    """管理员软删除用户。"""
    await user_service.delete_user(db, user_id)
    return success(None, message="用户已删除")
