"""AI 智能助手接口请求/响应模型。"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None
    question: str = Field(..., min_length=1, max_length=500)


class SessionTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern="^(like|dislike)$")
    reasons: list[str] = Field(default_factory=list)
    comment: str | None = Field(None, max_length=200)


class BatchDeleteRequest(BaseModel):
    session_ids: list[str] = Field(default_factory=list)
