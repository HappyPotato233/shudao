"""知识库服务单元测试：向量化失败置 failed、分块参数从 rag_config 读取。

服务已 async 化：异步调用统一通过 asyncio.run + AsyncSessionLocal 执行
（async 引擎为 NullPool，无跨 loop 连接问题）；造数与断言仍用同步 db 夹具。
"""
import asyncio
import io

from sqlalchemy import select, text

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.knowledge_service import KnowledgeBaseService, _split_text


class _FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.file = io.BytesIO(content)

    async def read(self) -> bytes:
        return self.file.read()


async def _upload(service: KnowledgeBaseService, content: bytes = "测试正文内容。".encode("utf-8")) -> dict:
    return await service.upload_document(
        file=_FakeUploadFile("test.txt", content),
        title="单测文档",
        doc_type="other",
        category_id=None,
        tags=[],
        authority_level="B",
        created_by="U001",
    )


def _reset_chunk_config(db):
    """显式恢复 rag_config 分块参数（该表不在 ORM metadata，drop_all 不会重置）。"""
    db.execute(text("UPDATE rag_config SET config_value = '500' WHERE config_key = 'chunk_size'"))
    db.execute(text("UPDATE rag_config SET config_value = '50' WHERE config_key = 'chunk_overlap'"))
    db.commit()


def test_upload_marks_failed_when_embedding_fails(db, monkeypatch):
    class BoomEmbedder:
        def embed(self, texts):
            raise RuntimeError("embed boom")

    def _no_chroma():
        raise RuntimeError("no chroma client expected")

    async def _run():
        from app.models.base import AsyncSessionLocal

        async with AsyncSessionLocal() as adb:
            service = KnowledgeBaseService(adb)
            service._embedder = BoomEmbedder()
            monkeypatch.setattr(service, "_get_kb_client", _no_chroma)
            return await _upload(service)

    result = asyncio.run(_run())
    assert result["document_id"]
    assert result["status"] == "failed"

    doc = db.get(KnowledgeDocument, result["document_id"])
    assert doc.status == "failed"
    assert doc.error_message
    assert "embed boom" in doc.error_message


def test_upload_reads_chunk_size_from_rag_config(db, monkeypatch):
    _reset_chunk_config(db)
    db.execute(text("UPDATE rag_config SET config_value = '10' WHERE config_key = 'chunk_size'"))
    db.execute(text("UPDATE rag_config SET config_value = '0' WHERE config_key = 'chunk_overlap'"))
    db.commit()

    content = "安全生产责任重于泰山，人人有责。" * 4  # 56 字

    async def _run():
        from app.models.base import AsyncSessionLocal

        async with AsyncSessionLocal() as adb:
            service = KnowledgeBaseService(adb)
            monkeypatch.setattr(service, "_index_vectors", lambda doc, chunks: None)
            return await _upload(service, content.encode("utf-8"))

    result = asyncio.run(_run())
    assert result["status"] == "indexed"

    doc = db.get(KnowledgeDocument, result["document_id"])
    assert doc.chunk_count > 1
    chunks = db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.doc_id)
    ).all()
    assert chunks
    assert all(len(c.content) <= 10 for c in chunks)
    _reset_chunk_config(db)


def test_load_chunk_config_falls_back_on_invalid(db):
    _reset_chunk_config(db)

    async def _load():
        from app.models.base import AsyncSessionLocal

        async with AsyncSessionLocal() as adb:
            return await KnowledgeBaseService(adb)._load_chunk_config()

    # 返回三元组：(chunk_size, chunk_overlap, chunk_strategy)
    assert asyncio.run(_load()) == (500, 50, "fixed")

    db.execute(text("UPDATE rag_config SET config_value = '-5' WHERE config_key = 'chunk_size'"))
    db.commit()
    assert asyncio.run(_load()) == (500, 50, "fixed")
    _reset_chunk_config(db)


def test_split_text_accepts_custom_params():
    chunks = _split_text("一二三四五六七八九十甲乙丙丁戊己", chunk_size=6, chunk_overlap=2)
    assert chunks
    assert all(len(c) <= 6 for c in chunks)


def test_get_document_status_reports_failure(db, monkeypatch):
    class BoomEmbedder:
        def embed(self, texts):
            raise RuntimeError("embed boom")

    async def _run():
        from app.models.base import AsyncSessionLocal

        async with AsyncSessionLocal() as adb:
            service = KnowledgeBaseService(adb)
            service._embedder = BoomEmbedder()
            result = await _upload(service)
            status = await service.get_document_status(result["document_id"])
            return result, status

    result, status = asyncio.run(_run())
    assert result["document_id"]
    assert status["status"] == "failed"
    assert status["error_message"]
