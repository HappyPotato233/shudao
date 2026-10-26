"""RAG 检索策略单元测试。"""
import asyncio

from app.core.config import settings
from app.models import (
    KbDocument,
    KbEvidenceUnit,
    KbKnowledgeEntry,
    KbQuarantine,
)
from app.services.rag import RagService, rrf_merge, tokenize_text
from app.services.rag import rag_service

API = settings.API_V1_PREFIX


def test_tokenize_text_splits_chinese():
    tokens = tokenize_text("高处作业安全带的使用标准")
    assert tokens
    assert "高处" in tokens or "安全带" in tokens


def test_rrf_merge_dedupes_and_ranks():
    vector = [
        {"evidence_id": "ev_a", "text": "a"},
        {"evidence_id": "ev_b", "text": "b"},
    ]
    keyword = [
        {"evidence_id": "ev_b", "text": "b2"},
        {"evidence_id": "ev_c", "text": "c"},
    ]
    merged = rrf_merge(vector, keyword, k=60.0)
    ids = [item["evidence_id"] for item in merged]
    assert "ev_b" in ids
    assert len(ids) == len(set(ids))
    assert ids[0] == "ev_b"


def test_rerank_threshold_filters_low_scores(monkeypatch):
    from app.services.embedding import RerankService

    class FakeModel:
        def predict(self, pairs):
            return [0.9, 0.1]

    reranker = RerankService()
    reranker._model = FakeModel()
    candidates = [{"text": "相关", "id": "a"}, {"text": "不相关", "id": "b"}]
    ranked = reranker.rerank("query", candidates, top_k=5, threshold=0.3)
    assert len(ranked) == 1
    assert ranked[0]["id"] == "a"


def test_bm25_keyword_search_hits_evidence(monkeypatch):
    service = RagService(embedder=object(), reranker=object())
    service._evidence_records = [
        {"evidence_id": "ev_1", "text": "高处作业安全带使用标准"},
        {"evidence_id": "ev_2", "text": "动火作业审批流程"},
        {"evidence_id": "ev_3", "text": "安全生产第一责任人"},
    ]
    asyncio.run(service._build_bm25())
    results = asyncio.run(service._keyword_search("安全带", top_k=2))
    assert results
    assert results[0]["evidence_id"] == "ev_1"


def _add_kb_document(db, document_id: str, source_id: str, version_status: str, jurisdiction: str):
    db.add(
        KbDocument(
            document_id=document_id,
            source_id=source_id,
            source_uri="u",
            title="t",
            publisher="p",
            document_type="法律",
            published_at="",
            effective_from="",
            effective_to="",
            version_status=version_status,
            jurisdiction=jurisdiction,
            applicable_roles_json="[]",
            applicable_activities_json="[]",
            authority_level="A",
            license_status="ok",
            content_hash="hash",
            retrieved_at="",
            section_locator="",
            review_status="机器初审",
            publication_layer="待核验层",
            raw_path="",
            text="正文",
            fetch_status="ok",
            governance_notes_json="{}",
        )
    )


def _add_kb_evidence(db, evidence_id: str, document_id: str):
    db.add(
        KbEvidenceUnit(
            evidence_id=evidence_id,
            document_id=document_id,
            source_uri="u",
            title="t",
            locator="l",
            text="正文",
            content_hash="hash",
            authority_level="A",
            review_status="机器初审",
        )
    )


def _add_kb_entry(db, knowledge_id: str, document_id: str, invalidated: int):
    db.add(
        KbKnowledgeEntry(
            knowledge_id=knowledge_id,
            document_id=document_id,
            topic="主题",
            document_type="法律",
            version_status="当前有效候选",
            risk_categories_json="[]",
            applicable_roles_json="[]",
            applicable_activities_json="[]",
            conclusion="结论",
            authority_level="A",
            review_status="机器初审",
            publication_layer="待核验层",
            invalidated=invalidated,
        )
    )


def _make_mini_kb(db):
    """向测试库写入迷你 KB 数据：有效 / 历史版本 / 隔离源 / 知识条目失效 四类文档。"""
    _add_kb_document(db, "doc_ok", "src_ok", "当前有效候选", "国家")
    _add_kb_document(db, "doc_old", "src_old", "历史版本", "国家")
    _add_kb_document(db, "doc_q", "src_q", "当前有效候选", "北京市")
    _add_kb_document(db, "doc_bad", "src_bad", "当前有效候选", "国家")

    _add_kb_entry(db, "k_ok", "doc_ok", 0)
    _add_kb_entry(db, "k_old", "doc_old", 0)
    _add_kb_entry(db, "k_q", "doc_q", 0)
    _add_kb_entry(db, "k_bad", "doc_bad", 1)

    _add_kb_evidence(db, "ev_ok", "doc_ok")
    _add_kb_evidence(db, "ev_old", "doc_old")
    _add_kb_evidence(db, "ev_quarantine", "doc_q")
    _add_kb_evidence(db, "ev_invalidated", "doc_bad")

    db.add(
        KbQuarantine(
            quarantine_id="q1",
            task_id="task1",
            source_id="src_q",
            record_json="{}",
        )
    )
    db.commit()


def test_read_evidence_filters_invalidated_and_quarantine(db):
    _make_mini_kb(db)
    rows = asyncio.run(RagService().read_evidence())
    ids = {row["evidence_id"] for row in rows}
    assert "ev_ok" in ids
    assert "ev_old" not in ids
    assert "ev_quarantine" not in ids
    assert "ev_invalidated" not in ids


def test_read_evidence_derives_standard_level(db):
    _make_mini_kb(db)
    rows = {row["evidence_id"]: row["standard_level"] for row in asyncio.run(RagService().read_evidence())}
    assert rows["ev_ok"] == "国家规范"


def test_rag_retrieve_endpoint(client, auth_headers, monkeypatch):
    async def _fake_retrieve(query, top_k=5, threshold=None, filters=None):
        return {
            "results": [
                {
                    "evidence_id": "ev_test",
                    "document_id": "doc_test",
                    "title": "测试规范",
                    "locator": "第1条",
                    "source_uri": "https://example.test",
                    "text": "证据正文",
                    "score": 0.9,
                }
            ],
            "no_evidence": False,
        }

    monkeypatch.setattr(rag_service, "retrieve", _fake_retrieve)
    resp = client.post(
        f"{API}/rag/retrieve",
        json={"query": "施工单位主要负责人的安全责任是什么？", "top_k": 5},
        headers=auth_headers("zhangsan"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["index_version"] == "safety_evidence_v1"
    assert body["data"]["results"][0]["evidence_id"] == "ev_test"


# ---------- B1：检索端融合证据集合与知识库集合 ----------


class _FakeReranker:
    def rerank(self, query, candidates, top_k=None, threshold=None):
        return candidates[:top_k] if top_k else candidates


def test_retrieve_merges_evidence_and_kb_collections(monkeypatch):
    service = RagService()

    async def _fake_config():
        return {
            "retrieval_top_k": 5,
            "similarity_threshold": 0.0,
            "rerank_enabled": True,
            "hybrid_search_enabled": True,
            "hybrid_keyword_weight": 0.5,
        }

    monkeypatch.setattr(service, "_load_rag_config", _fake_config)
    monkeypatch.setattr(service, "_get_reranker", lambda: _FakeReranker())
    monkeypatch.setattr(
        service,
        "_vector_search",
        lambda query, top_k: [
            {
                "evidence_id": "ev_1",
                "id": "ev_1",
                "text": "证据正文",
                "title": "证据标题",
                "source_collection": "safety_evidence_v1",
            }
        ],
    )
    monkeypatch.setattr(
        service,
        "_kb_vector_search",
        lambda query, top_k: [
            {
                "evidence_id": "kb_1_0",
                "id": "kb_1_0",
                "text": "知识库分块正文",
                "title": "上传文档",
                "document_id": "1",
                "source_collection": "safety_knowledge",
            }
        ],
    )

    async def _fake_keyword(query, top_k):
        return []

    monkeypatch.setattr(service, "_keyword_search", _fake_keyword)

    # _ensure_collection 依赖真实 Chroma，直接标记已缓存跳过（本测试 mock 了检索层）
    service._collection = object()

    result = asyncio.run(service.retrieve("安全带使用标准", top_k=5))
    assert result["no_evidence"] is False
    by_source = {item["source_collection"]: item for item in result["results"]}
    assert set(by_source) == {"safety_evidence_v1", "safety_knowledge"}
    assert by_source["safety_evidence_v1"]["evidence_id"] == "ev_1"
    assert by_source["safety_knowledge"]["evidence_id"] == "kb_1_0"
    assert by_source["safety_knowledge"]["document_id"] == "1"


def test_kb_vector_search_empty_when_collection_missing(monkeypatch):
    service = RagService()
    monkeypatch.setattr(service, "_kb_collection", lambda: None)
    assert service._kb_vector_search("任意查询", 5) == []


def test_kb_vector_search_maps_kb_hits(monkeypatch):
    class FakeEmbedder:
        def embed(self, texts):
            return [[0.1, 0.2]]

    class FakeCollection:
        def count(self):
            return 1

        def query(self, query_embeddings=None, n_results=None):
            return {
                "ids": [["kb_7_0"]],
                "documents": [["知识库分块正文"]],
                "metadatas": [
                    [
                        {
                            "doc_id": "7",
                            "title": "上传文档",
                            "doc_type": "regulation",
                            "authority_level": "B",
                            "chunk_index": 0,
                        }
                    ]
                ],
                "distances": [[0.25]],
            }

    service = RagService()
    service.embedder = FakeEmbedder()
    monkeypatch.setattr(service, "_kb_collection", lambda: FakeCollection())

    items = service._kb_vector_search("安全", 3)
    assert len(items) == 1
    item = items[0]
    assert item["evidence_id"] == "kb_7_0"
    assert item["id"] == "kb_7_0"
    assert item["document_id"] == "7"
    assert item["title"] == "上传文档"
    assert item["doc_type"] == "regulation"
    assert item["text"] == "知识库分块正文"
    assert abs(item["score"] - 0.75) < 1e-9
    assert item["source_collection"] == "safety_knowledge"


def test_vector_search_tags_source_collection(monkeypatch):
    class FakeEmbedder:
        def embed(self, texts):
            return [[0.1, 0.2]]

    class FakeCollection:
        def count(self):
            return 1

        def query(self, query_embeddings=None, n_results=None):
            return {
                "ids": [["ev_x"]],
                "documents": [["证据正文"]],
                "metadatas": [[{"evidence_id": "ev_x", "title": "证据标题"}]],
            }

    service = RagService()
    service.embedder = FakeEmbedder()
    monkeypatch.setattr(service, "_get_collection", lambda: FakeCollection())

    items = service._vector_search("查询", 5)
    assert len(items) == 1
    assert items[0]["source_collection"] == "safety_evidence_v1"
