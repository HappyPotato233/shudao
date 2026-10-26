"""本地 BGE 向量化与重排服务。"""
from __future__ import annotations

from app.core.config import settings


class EmbeddingService:
    """基于 bge-large 的文本向量化封装，首次使用时懒加载。"""

    def __init__(self, model_dir: str | None = None):
        self.model_dir = model_dir or settings.EMBEDDING_MODEL_DIR
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_dir)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


class RerankService:
    """基于 bge-base-rerank 的 CrossEncoder 重排封装。"""

    def __init__(self, model_dir: str | None = None):
        self.model_dir = model_dir or settings.RERANK_MODEL_DIR
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_dir)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[dict]:
        if not candidates:
            return []
        pairs = [(query, c.get("text") or "") for c in candidates]
        scores = self._get_model().predict(pairs)
        scored = [
            {**candidate, "score": float(score)}
            for candidate, score in zip(candidates, scores)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        if threshold is not None:
            scored = [item for item in scored if item["score"] > threshold]
        if top_k:
            scored = scored[:top_k]
        return scored


embedding_service = EmbeddingService()
rerank_service = RerankService()
