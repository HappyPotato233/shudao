"""认证服务 - 登录/登出/持久化会话与 Token 轮换管理（async）"""
import datetime
from uuid import uuid4

from app.core.config import settings
from app.core.response import BizError, ErrorCode
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user_orm import User
from app.models.auth_session import AuthSession
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# User 查询统一预加载 role（AsyncSession 下 lazy load 会触发 MissingGreenlet）
_USER_WITH_ROLE = selectinload(User.role)


def _now_iso() -> str:
    """返回当前 +08:00 时间，ISO 8601 秒级字符串。"""
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).isoformat(timespec="seconds")


def _expires_at(minutes: int) -> str:
    """返回从当前时间起 minutes 分钟后的 +08:00 ISO 字符串。"""
    return (
        datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        + datetime.timedelta(minutes=minutes)
    ).isoformat(timespec="seconds")


def _parse_iso(value: str | None) -> datetime.datetime | None:
    """解析 ISO 时间字符串；无时区时按 +08:00 处理。"""
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    return parsed


async def login(db: AsyncSession, username: str, password: str) -> dict:
    """
    用户登录：校验账号密码并签发 Token

    :raises BizError: 40101 用户名或密码错误 / 40102 账户已被禁用
    """
    user = (
        await db.execute(
            select(User).where(User.username == username).options(_USER_WITH_ROLE)
        )
    ).scalar_one_or_none()
    # 用户不存在或密码错误统一返回 40101，避免暴露用户是否存在
    if user is None or not verify_password(password, user.password_hash):
        raise BizError(*ErrorCode.BAD_CREDENTIALS)
    if not user.is_active:
        raise BizError(*ErrorCode.ACCOUNT_DISABLED)

    role_name = user.role.name if user.role else ""
    access_token, access_jti = create_access_token(user.user_id, extra={"role": role_name})
    refresh_token, refresh_jti = create_refresh_token(user.user_id)
    now = _now_iso()

    session = AuthSession(
        session_id="auth_" + uuid4().hex[:12],
        user_id=user.user_id,
        access_jti=access_jti,
        refresh_jti=refresh_jti,
        last_active_at=now,
        access_expires_at=_expires_at(settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        refresh_expires_at=_expires_at(settings.REFRESH_TOKEN_EXPIRE_MINUTES),
        revoked_at=None,
    )
    user.last_login_at = now
    db.add(session)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_info(),
    }


async def logout(db: AsyncSession, jti: str) -> None:
    """登出：持久化吊销当前会话。"""
    session = (
        await db.execute(select(AuthSession).where(AuthSession.access_jti == jti))
    ).scalar_one_or_none()
    if session is None:
        return
    now = _now_iso()
    session.revoked_at = now
    session.updated_at = now
    await db.commit()


def _is_session_idle(session: AuthSession, now: datetime.datetime) -> bool:
    last_active = _parse_iso(session.last_active_at)
    if last_active is None:
        return True
    return now - last_active > datetime.timedelta(
        minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES
    )


async def get_active_session_by_access_jti(db: AsyncSession, jti: str | None) -> AuthSession:
    """按 access jti 获取有效会话；缺失、吊销、过期或空闲超时返回 40100。"""
    if not jti:
        raise BizError(*ErrorCode.TOKEN_INVALID)

    session = (
        await db.execute(select(AuthSession).where(AuthSession.access_jti == jti))
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise BizError(*ErrorCode.TOKEN_INVALID)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    expires_at = _parse_iso(session.access_expires_at)
    if expires_at is None or now > expires_at:
        raise BizError(*ErrorCode.TOKEN_INVALID)
    if _is_session_idle(session, now):
        raise BizError(*ErrorCode.TOKEN_INVALID)

    return session


async def get_active_session_by_refresh_jti(db: AsyncSession, refresh_jti: str | None) -> AuthSession:
    """按 refresh jti 获取有效会话；缺失、吊销、过期或空闲超时返回 40103。"""
    if not refresh_jti:
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)

    session = (
        await db.execute(
            select(AuthSession).where(AuthSession.refresh_jti == refresh_jti)
        )
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    expires_at = _parse_iso(session.refresh_expires_at)
    if expires_at is None or now > expires_at:
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)
    if _is_session_idle(session, now):
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)

    return session


async def touch_session(db: AsyncSession, session: AuthSession) -> None:
    """节流更新会话最后活动时间，避免每个请求都写库。"""
    if session is None:
        return
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    last_active = _parse_iso(session.last_active_at)
    if last_active is None or now - last_active >= datetime.timedelta(seconds=60):
        session.last_active_at = _now_iso()
        session.updated_at = session.last_active_at
        await db.commit()


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """删除已吊销或 refresh token 已过期的会话。"""
    now = _now_iso()
    result = await db.execute(
        delete(AuthSession).where(
            or_(
                AuthSession.revoked_at.is_not(None),
                AuthSession.refresh_expires_at < now,
            )
        )
    )
    await db.commit()
    return result.rowcount or 0


async def get_user_info(db: AsyncSession, user_id: str) -> dict | None:
    """按用户 ID 获取用户信息"""
    user = await db.get(User, user_id)
    return user.to_info() if user else None


async def change_password(db: AsyncSession, user_id: str, old_password: str, new_password: str) -> None:
    """修改密码（校验旧密码 + BCrypt 存储新密码）。"""
    user = await db.get(User, user_id)
    if user is None or not verify_password(old_password, user.password_hash):
        raise BizError(*ErrorCode.OLD_PASSWORD_ERROR)
    user.password_hash = hash_password(new_password)
    await db.commit()


async def refresh(db: AsyncSession, refresh_token: str) -> dict:
    """用 refresh_token 换发新的 access_token 与 refresh_token。"""
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)

    if payload.get("type") != "refresh":
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)

    refresh_jti = payload.get("jti")
    user_id = payload.get("sub")
    user = (
        await db.execute(
            select(User).where(User.user_id == user_id).options(_USER_WITH_ROLE)
        )
    ).scalar_one_or_none() if user_id else None
    if user is None or not user.is_active:
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)

    session = await get_active_session_by_refresh_jti(db, refresh_jti)
    if session.user_id != user.user_id:
        raise BizError(*ErrorCode.REFRESH_TOKEN_INVALID)

    role_name = user.role.name if user.role else ""
    access_token, new_access_jti = create_access_token(
        user.user_id, extra={"role": role_name}
    )
    new_refresh_token, new_refresh_jti = create_refresh_token(user.user_id)

    now = _now_iso()
    session.access_jti = new_access_jti
    session.refresh_jti = new_refresh_jti
    session.access_expires_at = _expires_at(settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    session.refresh_expires_at = _expires_at(settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    session.last_active_at = now
    session.updated_at = now
    session.revoked_at = None
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_info(),
    }
