"""认证相关 Schema - 对齐 API.md 2.1 登录响应结构"""
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.core.security import validate_password_complexity


class Role(str, Enum):
    """用户角色，对齐 API.md 1.5 权限标识"""
    ADMIN = "Admin"
    USER = "User"


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名或工号")
    password: str = Field(..., min_length=8, description="密码（≥8 位，含大小写字母+数字+特殊字符）")


class UserInfo(BaseModel):
    """用户信息，对齐 API.md 2.1 user 字段"""
    id: str
    username: str
    name: str
    role: Role
    department: str
    project: str


class LoginData(BaseModel):
    """登录成功返回数据"""
    access_token: str
    refresh_token: str
    expires_in: int = Field(description="access_token 有效期（秒）")
    user: UserInfo


class TokenPayload(BaseModel):
    """JWT 解析结果"""
    sub: str
    type: str
    jti: str | None = None


class PasswordChangeRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def _check_complexity(cls, v: str) -> str:
        if not validate_password_complexity(v):
            raise ValueError("密码需至少 8 位且包含大写字母、小写字母、数字、特殊字符")
        return v


class RefreshRequest(BaseModel):
    """刷新 Token 请求"""

    refresh_token: str = Field(..., min_length=1)
