"""v1 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    auth,
    exam,
    hazards,
    knowledge,
    notifications,
    rag,
    statistics,
    users,
)

api_router = APIRouter()
api_router.include_router(ai.router)
api_router.include_router(auth.router)
api_router.include_router(exam.router)
api_router.include_router(hazards.router)
api_router.include_router(notifications.router)
api_router.include_router(rag.router)
api_router.include_router(admin.router)
api_router.include_router(users.router)
api_router.include_router(knowledge.router)
api_router.include_router(statistics.router)
