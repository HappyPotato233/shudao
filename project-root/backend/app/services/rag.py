"""RAG 检索服务：业务库 kb_* 事实源 + Chroma 向量 + BM25 关键字 + BGE 重排。

2026-08-23 P4 全链路 async 化：read_evidence / _load_rag_config / retrieve /
build_index 均为 async；embedding 推理、BM25 构建、Chroma 查询、重排等
CPU 密集或本地阻塞操作统一经 asyncio.to_thread 下沉线程池执行。
"""
from __future__ import annotations

import asyncio

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.core.config import settings
from app.models import (
    AsyncSessionLocal,
    KbDocument,
    KbEvidenceUnit,
    KbKnowledgeEntry,
    KbQuarantine,
    RagConfig,
)


COLLECTION_NAME = "safety_evidence_v1"
# 知识库上传文档向量集合（与证据集合分离，见 knowledge_service.KB_COLLECTION_NAME）
KB_COLLECTION_NAME = "safety_knowledge"


def tokenize_text(text: str) -> list[str]:
    """中文分词，供 BM25 使用。"""
    return [token.strip() for token in jieba.lcut(text or "") if token.strip()]


def rrf_merge(
    vector_items: list[dict],
    keyword_items: list[dict],
    k: float = 60.0,
) -> list[dict]:
    """按 Reciprocal Rank Fusion 合并两路结果，并按 evidence_id 去重。"""
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for rank, item in enumerate(vector_items):
        key = item.get("evidence_id") or item.get("id")
        if not key:
            continue
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        items.setdefault(key, item)

    for rank, item in enumerate(keyword_items):
        key = item.get("evidence_id") or item.get("id")
        if not key:
            continue
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        items.setdefault(key, item)

    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [dict(items[key], _rrf_score=scores[key]) for key in ordered]


def _embedding_text(
    title: str,
    document_type: str,
    topic: str,
    locator: str,
    text: str,
) -> str:
    parts = [
        f"标题：{title or ''}",
        f"类型：{document_type or ''}",
        f"主题：{topic or ''}",
        f"位置：{locator or ''}",
        f"正文：{text or ''}",
    ]
    return "\n".join(parts)


def _standard_level(jurisdiction: str | None) -> str:
    """按文档辖区派生规范层级（对齐原 SQL 的 CASE 逻辑）。"""
    if jurisdiction == "国家":
        return "国家规范"
    if jurisdiction and any(k in jurisdiction for k in ("公司", "集团", "企业")):
        return "企业规范"
    return "地方规范"


class RagService:
    def __init__(self, embedder=None, reranker=None, client=None):
        self.embedder = embedder
        self.reranker = reranker
        self._client = client
        self._collection = None
        self._kb_collection_cache = None
        self._evidence_records: list[dict] | None = None
        self._bm25: BM25Okapi | None = None
        self._bm25_ids: list[str] = []

    def _get_client(self):
        if self._client is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        return self._client

    async def _ensure_collection(self):
        """确保证据向量集合并缓存，缺失时自愈重建索引。"""
        if self._collection is not None:
            return

        def _try_get():
            collection = self._get_client().get_collection(COLLECTION_NAME)
            collection.count()
            return collection

        try:
            self._collection = await asyncio.to_thread(_try_get)
        except Exception:
            await self.build_index()

    def _get_collection(self):
        """获取证据集合（调用前应先经 _ensure_collection 完成缓存/自愈）。"""
        if self._collection is not None:
            return self._collection
        client = self._get_client()
        collection = client.get_collection(COLLECTION_NAME)
        collection.count()
        self._collection = collection
        return collection

    def _kb_collection(self):
        """获取知识库上传文档集合（safety_knowledge），不存在时返回 None。

        容错：未上传过知识库文档时该集合不存在，返回 None 而不影响证据检索；
        获取失败不缓存，待知识库建立后可再次探测。
        """
        if self._kb_collection_cache is not None:
            return self._kb_collection_cache
        try:
            collection = self._get_client().get_collection(KB_COLLECTION_NAME)
            collection.count()
        except Exception:
            return None
        self._kb_collection_cache = collection
        return collection

    def _get_embedder(self):
        if self.embedder is None:
            from app.services.embedding import embedding_service

            self.embedder = embedding_service
        return self.embedder

    def _get_reranker(self):
        if self.reranker is None:
            from app.services.embedding import rerank_service

            self.reranker = rerank_service
        return self.reranker

    async def read_evidence(self, limit: int | None = None) -> list[dict]:
        """读取业务库 kb_* 表中可引用的证据单元，并应用准入过滤。

        过滤规则（对齐原 transport_safety_kb.sqlite3 直连 SQL）：
        - 证据正文与 content_hash 非空
        - 文档 version_status 非「历史版本」（文档缺失时视为 NULL，不过滤）
        - 文档 source_id 未被隔离（quarantine）
        - 文档存在 invalidated=0 的知识条目（EXISTS 准入）
        - topic 取该文档按 entry_id 顺序第一条有效条目（原 rowid 语义）
        """
        async with AsyncSessionLocal() as db:
            quarantined = {
                sid
                for (sid,) in (
                    await db.execute(
                        select(KbQuarantine.source_id).where(
                            KbQuarantine.source_id.isnot(None)
                        )
                    )
                ).all()
                if sid
            }
            topic_by_doc: dict[str, str] = {}
            for doc_id, topic in (
                await db.execute(
                    select(KbKnowledgeEntry.document_id, KbKnowledgeEntry.topic)
                    .where(KbKnowledgeEntry.invalidated == 0)
                    .order_by(KbKnowledgeEntry.entry_id)
                )
            ).all():
                topic_by_doc.setdefault(doc_id, topic)
            doc_by_id = {
                d.document_id: d
                for d in (await db.scalars(select(KbDocument))).all()
            }

            rows: list[dict] = []
            for e in (
                await db.scalars(
                    select(KbEvidenceUnit).order_by(KbEvidenceUnit.evidence_id)
                )
            ).all():
                if e.document_id not in topic_by_doc:
                    continue
                doc = doc_by_id.get(e.document_id)
                if doc is not None and doc.version_status == "历史版本":
                    continue
                if doc is not None and doc.source_id in quarantined:
                    continue
                if not (e.text or "").strip() or not (e.content_hash or "").strip():
                    continue
                rows.append(
                    {
                        "evidence_id": e.evidence_id,
                        "document_id": e.document_id,
                        "source_uri": e.source_uri,
                        "title": e.title,
                        "locator": e.locator,
                        "text": e.text,
                        "content_hash": e.content_hash,
                        "authority_level": e.authority_level,
                        "review_status": e.review_status,
                        "document_type": doc.document_type if doc is not None else None,
                        "topic": topic_by_doc.get(e.document_id),
                        "publication_layer": doc.publication_layer if doc is not None else None,
                        "standard_level": _standard_level(doc.jurisdiction if doc is not None else None),
                    }
                )
        return rows[:limit] if limit else rows

    async def _get_evidence_records(self) -> list[dict]:
        if self._evidence_records is None:
            self._evidence_records = await self.read_evidence()
        return self._evidence_records

    async def _build_bm25(self) -> None:
        records = await self._get_evidence_records()

        def _build() -> BM25Okapi:
            # jieba 分词 2000+ 文档为 CPU 密集操作，放线程池执行
            corpus = [tokenize_text(record["text"]) for record in records]
            return BM25Okapi(corpus)

        self._bm25 = await asyncio.to_thread(_build)
        self._bm25_ids = [record["evidence_id"] for record in records]

    async def _get_bm25(self) -> BM25Okapi:
        if self._bm25 is None:
            await self._build_bm25()
        return self._bm25

    async def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        records = await self._get_evidence_records()
        bm25 = await self._get_bm25()
        scores = bm25.get_scores(tokenize_text(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for idx in ranked:
            if scores[idx] <= 0 or len(results) >= top_k:
                break
            results.append(records[idx])
        return results

    def _vector_search(self, query: str, top_k: int) -> list[dict]:
        collection = self._get_collection()
        if collection.count() == 0:
            return []
        embedder = self._get_embedder()
        query_vec = embedder.embed([query])[0]
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=min(max(top_k, 1), collection.count()),
        )
        ids = result.get("ids") or [[]]
        metadatas = result.get("metadatas") or [[]]
        documents = result.get("documents") or [[]]
        candidates = []
        for i, doc_id in enumerate(ids[0]):
            meta = metadatas[0][i] if i < len(metadatas[0]) else {}
            text = documents[0][i] if i < len(documents[0]) else ""
            candidates.append(
                {
                    "id": doc_id,
                    "text": text,
                    **{key: value for key, value in meta.items() if value is not None},
                    "source_collection": COLLECTION_NAME,
                }
            )
        return candidates

    def _kb_vector_search(self, query: str, top_k: int) -> list[dict]:
        """查询知识库上传文档集合，返回与 _vector_search 同构的候选列表。

        集合不存在或查询异常时返回 []，不影响证据集合检索。
        集合内 id 为分块唯一 id（kb_{doc_id}_{chunk_index}），
        metadata 含 doc_id/title/doc_type/authority_level/chunk_index，documents 为分块文本。
        """
        collection = self._kb_collection()
        if collection is None:
            return []
        try:
            query_vec = self._get_embedder().embed([query])[0]
            result = collection.query(query_embeddings=[query_vec], n_results=max(top_k, 1))
        except Exception:
            return []
        ids = result.get("ids") or [[]]
        metadatas = result.get("metadatas") or [[]]
        documents = result.get("documents") or [[]]
        distances = result.get("distances") or [[]]
        candidates = []
        for i, chunk_id in enumerate(ids[0]):
            meta = metadatas[0][i] if i < len(metadatas[0]) else {}
            text = documents[0][i] if i < len(documents[0]) else ""
            distance = distances[0][i] if i < len(distances[0]) else None
            item = {
                "id": chunk_id,
                "evidence_id": chunk_id,
                "text": text,
                "score": 1.0 - float(distance) if distance is not None else None,
                "document_id": meta.get("doc_id"),
                **{key: value for key, value in meta.items() if value is not None},
                "source_collection": KB_COLLECTION_NAME,
            }
            candidates.append(item)
        return candidates

    async def build_index(self, limit: int | None = None) -> int:
        """把业务库证据写入 Chroma，返回写入条数。"""
        rows = await self.read_evidence(limit=limit)
        if not rows:
            return 0

        client = self._get_client()
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        collection = client.get_or_create_collection(COLLECTION_NAME)

        embedder = self._get_embedder()

        def _embed_all():
            # 逐条 embedding 为 CPU 密集操作，整段放线程池执行
            ids = []
            documents = []
            embeddings = []
            metadatas = []
            for row in rows:
                doc_text = _embedding_text(
                    row["title"],
                    row["document_type"],
                    row["topic"],
                    row["locator"],
                    row["text"],
                )
                vector = embedder.embed([doc_text])[0]
                ids.append(row["evidence_id"])
                documents.append(doc_text)
                embeddings.append(vector)
                metadatas.append(
                    {
                        "evidence_id": row["evidence_id"],
                        "document_id": row["document_id"],
                        "source_uri": row["source_uri"] or "",
                        "title": row["title"] or "",
                        "document_type": row["document_type"] or "",
                        "locator": row["locator"] or "",
                        "authority_level": row["authority_level"] or "",
                        "review_status": row["review_status"] or "",
                        "publication_layer": row["publication_layer"] or "",
                        "standard_level": row["standard_level"] or "",
                        "topic": row["topic"] or "",
                    }
                )
            return ids, documents, embeddings, metadatas

        ids, documents, embeddings, metadatas = await asyncio.to_thread(_embed_all)
        await asyncio.to_thread(
            collection.add,
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        self._collection = collection
        # 关键字索引与证据记录同源，重新构建向量后保持同步。
        self._evidence_records = rows if limit else await self.read_evidence()
        self._bm25 = None
        self._bm25_ids = []
        return len(ids)

    async def _load_rag_config(self) -> dict:
        """从业务库 rag_config 读取检索参数，缺失时回退默认值。

        ORM 查询跟随 DATABASE_URL（原 sqlite3 直连硬编码 app.db 路径，
        测试环境下读不到测试库）。
        """
        defaults = {
            "retrieval_top_k": 5,
            "similarity_threshold": settings.RAG_RERANK_THRESHOLD,
            "rerank_enabled": True,
            "hybrid_search_enabled": True,
            "hybrid_keyword_weight": 0.5,
        }
        try:
            async with AsyncSessionLocal() as db:
                rows = (
                    await db.execute(
                        select(RagConfig.config_key, RagConfig.config_value)
                    )
                ).all()
        except Exception:
            return defaults

        config = dict(defaults)
        for key, raw in rows:
            if key == "retrieval_top_k":
                config[key] = int(float(raw))
            elif key == "similarity_threshold":
                config[key] = float(raw)
            elif key in ("rerank_enabled", "hybrid_search_enabled"):
                config[key] = str(raw) in ("1", "true", "True")
            elif key == "hybrid_keyword_weight":
                config[key] = float(raw)
        return config

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float | None = None,
        filters: dict | None = None,
    ) -> dict:
        """按 rag_config 动态选择检索策略，支持混合/单一检索与重排开关。"""
        del filters  # 本轮保留为接口占位，暂不启用服务端强过滤。
        cfg = await self._load_rag_config()
        if top_k == 5:
            top_k = int(cfg["retrieval_top_k"])
        recall = max(top_k * 2, 10)
        await self._ensure_collection()
        # 向量召回融合证据集合与知识库上传文档集合
        # （embedding 推理 + Chroma 查询为 CPU/本地 IO 密集，放线程池执行）
        vector_items = await asyncio.to_thread(self._vector_search, query, recall)
        kb_items = await asyncio.to_thread(self._kb_vector_search, query, recall)
        keyword_items = await self._keyword_search(query, recall)

        if cfg["hybrid_search_enabled"]:
            merged = rrf_merge(
                vector_items + kb_items,
                keyword_items,
                k=settings.RAG_RRF_K * (1 - cfg["hybrid_keyword_weight"] + 1),
            )
        else:
            merged = (vector_items + kb_items) or keyword_items
        if not merged:
            return {"results": [], "no_evidence": True}

        if cfg["rerank_enabled"]:
            reranker = self._get_reranker()
            # BGE 重排为 CPU 密集操作，放线程池执行
            ranked = await asyncio.to_thread(
                reranker.rerank,
                query,
                merged,
                top_k=top_k,
                threshold=threshold if threshold is not None else cfg["similarity_threshold"],
            )
        else:
            ranked = merged[:top_k]
        results = [
            {
                "evidence_id": item.get("evidence_id") or item.get("id"),
                "document_id": item.get("document_id"),
                "title": item.get("title"),
                "locator": item.get("locator"),
                "source_uri": item.get("source_uri"),
                "standard_level": item.get("standard_level"),
                "text": item.get("text"),
                "score": item.get("score"),
                "source_collection": item.get("source_collection") or COLLECTION_NAME,
            }
            for item in ranked
        ]
        return {"results": results, "no_evidence": not results}


rag_service = RagService()
