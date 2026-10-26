"""用户管理请求模型。"""
from pydantic import BaseModel, Field, field_validator

from app.core.security import validate_password_complexity
from app.schemas.auth import Role


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8)
    role: Role
    department: str = Field(..., min_length=1)
    project: str = Field(..., min_length=1)
    phone: str | None = None

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        if not validate_password_complexity(v):
            raise ValueError("密码需至少 8 位且包含大写字母、小写字母、数字、特殊字符")
        return v


class UserUpdateRequest(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=50)
    password: str | None = Field(None, min_length=8)
    role: Role | None = None
    department: str | None = None
    project: str | None = None
    phone: str | None = None
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str | None) -> str | None:
        if v is not None and not validate_password_complexity(v):
            raise ValueError("密码需至少 8 位且包含大写字母、小写字母、数字、特殊字符")
        return v
