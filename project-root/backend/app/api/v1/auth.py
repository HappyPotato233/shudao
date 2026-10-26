"""认证路由 - 登录/登出/查看个人信息（对齐 API.md 2.1 / 2.3 / 2.4）"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context_async
from app.models.base import get_db
from app.core.response import success
from app.schemas.auth import LoginRequest, PasswordChangeRequest, RefreshRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证与用户管理"])


@router.post("/login", summary="登录")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录，返回 access_token / refresh_token / user"""
    data = await auth_service.login(db, req.username, req.password)
    return success(data)


@router.post("/logout", summary="退出登录")
async def logout(
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    """退出登录，吊销当前 access_token"""
    await auth_service.logout(db, ctx.jti)
    return success(None, message="已退出登录")


@router.post("/refresh", summary="刷新 Token")
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """用 refresh_token 换发新的 access_token 与 refresh_token。"""
    return success(await auth_service.refresh(db, req.refresh_token))


@router.get("/me", summary="获取当前用户信息")
async def me(ctx: AuthContext = Depends(get_auth_context_async)):
    """返回当前登录用户信息"""
    return success({
        "id": ctx.user_id,
        "username": ctx.username,
        "name": ctx.name,
        "role": ctx.role,
        "department": ctx.department,
        "project": ctx.project,
    })


@router.put("/password", summary="修改密码")
async def change_password(
    req: PasswordChangeRequest,
    ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户密码"""
    await auth_service.change_password(db, ctx.user_id, req.old_password, req.new_password)
    return success(None, message="密码修改成功")
