"""知识库管理接口请求模型。"""
from pydantic import BaseModel, Field


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    parent_id: int | None = None
    sort_order: int = 0


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    parent_id: int | None = None
    sort_order: int | None = None
