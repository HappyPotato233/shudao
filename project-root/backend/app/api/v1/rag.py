"""RAG 检索接口"""
from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_auth_context_async
from app.core.config import settings
from app.core.response import success
from app.schemas.rag import RagRetrieveRequest
from app.services.rag import COLLECTION_NAME, rag_service

router = APIRouter(prefix="/rag", tags=["RAG 检索"])


@router.post("/retrieve", summary="RAG 混合检索")
async def retrieve(
    req: RagRetrieveRequest,
    _ctx: AuthContext = Depends(get_auth_context_async),
):
    threshold = req.threshold if req.threshold is not None else settings.RAG_RERANK_THRESHOLD
    # retrieve 内部已把 embedding/BM25/重排等 CPU 密集操作下沉线程池
    data = await rag_service.retrieve(
        req.query,
        top_k=req.top_k,
        threshold=threshold,
        filters=req.filters,
    )
    data["index_version"] = COLLECTION_NAME
    return success(data)
