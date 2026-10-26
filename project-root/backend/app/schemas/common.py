"""通用 Schema - 分页等公共模型"""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """分页元信息"""
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class PaginatedData(BaseModel, Generic[T]):
    """分页数据结构，对齐 API.md 1.4"""
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
