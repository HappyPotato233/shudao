"""隐患相关 Schema"""
from pydantic import BaseModel, Field


class HazardCreate(BaseModel):
    title: str = Field(..., max_length=100)
    description: str = Field(..., max_length=2000)
    level: str
    category: str
    location: str
    location_coords: str | None = None
    occurred_at: str
    project: str


class AssignRequest(BaseModel):
    assignee_id: str
    requirements: str = Field(..., max_length=1000)
    deadline: str
    priority: str


class RectifyRequest(BaseModel):
    measures: str
    completed_at: str | None = None


class ReviewRequest(BaseModel):
    result: str
    comment: str | None = None
