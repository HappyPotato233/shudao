"""公共依赖 - 当前用户/Token 解析"""
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import get_db
from app.models.user_orm import User
from app.core.response import BizError, ErrorCode
from app.core.security import decode_token
from app.services import auth_service
from jose import JWTError


@dataclass
class AuthContext:
    """鉴权上下文：当前用户信息 + Token 标识"""
    user_id: str
    username: str
    name: str
    role: str
    department: str
    project: str
    jti: str


def _extract_bearer(request: Request) -> str:
    """从 Authorization 头提取 Bearer Token"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        # 未携带 Token
        raise BizError(*ErrorCode.UNAUTHORIZED)
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise BizError(*ErrorCode.TOKEN_INVALID)
    return parts[1]


async def get_auth_context_async(
    request: Request, db: AsyncSession = Depends(get_db)
) -> AuthContext:
    """异步鉴权依赖：解析 Token 并返回鉴权上下文。

    User 查询预加载 role 避免 AsyncSession 下
    lazy load 触发 MissingGreenlet。

    :raises BizError: 40100 未携带 Token / Token 无效或已过期
    """
    token = _extract_bearer(request)
    try:
        payload = decode_token(token)
    except JWTError:
        raise BizError(*ErrorCode.TOKEN_INVALID)

    # 仅接受 access_token
    if payload.get("type") != "access":
        raise BizError(*ErrorCode.TOKEN_INVALID)

    jti = payload.get("jti")
    session = await auth_service.get_active_session_by_access_jti(db, jti)

    user_id = payload.get("sub")
    if not user_id or session.user_id != user_id:
        raise BizError(*ErrorCode.TOKEN_INVALID)

    user = (
        await db.execute(
            select(User)
            .where(User.user_id == user_id)
            .options(selectinload(User.role))
        )
    ).scalar_one_or_none() if user_id else None
    if user is None or not user.is_active:
        raise BizError(*ErrorCode.TOKEN_INVALID)

    await auth_service.touch_session(db, session)

    return AuthContext(
        user_id=user.user_id,
        username=user.username,
        name=user.name,
        role=user.role.name if user.role else "",
        department=user.department,
        project=user.project,
        jti=jti,
    )
