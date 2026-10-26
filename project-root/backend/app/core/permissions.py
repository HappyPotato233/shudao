"""RBAC 权限与数据范围判断

新权限模型（2026-08-17 重构）：
- Admin：配置管理、知识库、AI模型测试、用户管理；可查看全部隐患列表（只读巡视）
- User（普通用户）：隐患管理（上报/识别/派单/整改），AI智能问答，考试工坊
"""
from fastapi import Depends

from app.api.deps import AuthContext, get_auth_context_async
from app.core.response import BizError, ErrorCode


def require_roles_async(*roles: str):
    """依赖工厂：要求当前用户角色在 roles 中，否则 40303（鉴权走 AsyncSession）。"""
    def dep(ctx: AuthContext = Depends(get_auth_context_async)):
        if ctx.role not in roles:
            raise BizError(*ErrorCode.FORBIDDEN)
        return ctx

    return dep


# ---- 隐患管理权限（仅普通用户 User） ----

def can_view_hazard(ctx: AuthContext, hazard) -> bool:
    """隐患可见性：仅普通用户可查看自己上报的隐患。"""
    return hazard.reporter_id == ctx.user_id


def can_manage_hazard(ctx: AuthContext, hazard) -> bool:
    """隐患管理权：仅普通用户可管理自己上报的隐患。"""
    return hazard.reporter_id == ctx.user_id


def is_assignee(ctx: AuthContext, hazard) -> bool:
    """是否为最新一次派单的被指派人。"""
    if not hazard.assignments:
        return False
    latest = sorted(hazard.assignments, key=lambda a: a.created_at or "")[-1]
    return latest.assignee_id == ctx.user_id


# ---- 考试工坊权限（普通用户 User） ----

def can_manage_exam(ctx: AuthContext) -> bool:
    """考试管理权：普通用户（User）可出题/组卷/发布/统计。"""
    return ctx.role == "User"


# ---- 管理端权限（Admin） ----

def can_manage_config(ctx: AuthContext) -> bool:
    """配置管理权：仅 Admin 可管理模型/RAG/知识库/用户。"""
    return ctx.role == "Admin"
