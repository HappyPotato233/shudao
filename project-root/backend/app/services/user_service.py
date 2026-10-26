"""用户管理服务：创建、编辑、软删除用户（async）。"""
from __future__ import annotations

import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import BizError, ErrorCode
from app.core.security import hash_password
from app.models.role import Role
from app.models.user_orm import User


def _now_cst() -> str:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


async def _role_id(db: AsyncSession, role_name: str) -> int:
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if role is None:
        raise BizError(40001, "角色不存在")
    return role.role_id


async def _next_user_id(db: AsyncSession) -> str:
    max_seq = (
        await db.execute(
            text("SELECT MAX(CAST(SUBSTR(user_id, 2) AS INTEGER)) FROM users WHERE user_id LIKE 'U%'")
        )
    ).scalar()
    seq = (max_seq or 0) + 1
    return f"U{seq:03d}"


async def create_user(db: AsyncSession, data) -> dict:
    existing = (
        await db.execute(select(User).where(User.username == data.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise BizError(*ErrorCode.USERNAME_EXISTS)

    user = User(
        user_id=await _next_user_id(db),
        username=data.username,
        password_hash=hash_password(data.password),
        name=data.name,
        role_id=await _role_id(db, data.role.value),
        department=data.department,
        project=data.project,
        phone=data.phone,
        is_active=1,
    )
    db.add(user)
    await db.commit()
    # AsyncSession 下 lazy load 会触发 MissingGreenlet，refresh 时显式加载 role
    await db.refresh(user, ["role"])
    return user.to_info()


async def update_user(db: AsyncSession, user_id: str, data) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise BizError(*ErrorCode.USER_NOT_FOUND)

    if data.username is not None:
        duplicate = (
            await db.execute(
                select(User).where(User.username == data.username, User.user_id != user_id)
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise BizError(*ErrorCode.USERNAME_EXISTS)
        user.username = data.username

    if data.name is not None:
        user.name = data.name
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    if data.role is not None:
        user.role_id = await _role_id(db, data.role.value)
    if data.department is not None:
        user.department = data.department
    if data.project is not None:
        user.project = data.project
    if data.phone is not None:
        user.phone = data.phone
    if data.is_active is not None:
        user.is_active = 1 if data.is_active else 0

    user.updated_at = _now_cst()
    await db.commit()
    # AsyncSession 下 lazy load 会触发 MissingGreenlet，refresh 时显式加载 role
    await db.refresh(user, ["role"])
    return user.to_info()


async def delete_user(db: AsyncSession, user_id: str) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise BizError(*ErrorCode.USER_NOT_FOUND)
    user.is_active = 0
    user.updated_at = _now_cst()
    await db.commit()
