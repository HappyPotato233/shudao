"""RAG 检索请求模型。"""
from pydantic import BaseModel, Field


class RagRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(5, ge=1, le=20)
    threshold: float | None = None
    filters: dict = Field(default_factory=dict)
