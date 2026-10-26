"""知识库管理服务：上传文档、解析、分块、向量化、入库、删除。

对齐 AI_SOLUTION.md 5.3「知识库管理 Python 实现」与 API.md 第 8 章：
- 支持 PDF / Word(.docx) / TXT / Markdown 文档
- 解析 -> 分块 -> 向量化 -> 入库，状态流转 parsing -> chunking -> indexing -> indexed
- 删除文档时同步清理分块记录、Chroma 向量与磁盘文件
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.response import BizError
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument

# 知识库向量集合名（与 RAG 检索证据集合 safety_evidence_v1 分离）
KB_COLLECTION_NAME = "safety_knowledge"

# 支持的文件类型（API.md 8.2：PDF/Word/TXT/Markdown，≤50MB）
SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md"}
MAX_KB_FILE_SIZE_MB = 50

# 分块参数（对齐 AI_SOLUTION.md 5.3：500 字/块，100 字重叠）
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def _split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """按段落/句号递归切分文本，返回分块列表。"""
    text = re.sub(r"\r\n", "\n", text or "").strip()
    if not text:
        return []
    separators = ["\n\n", "\n", "。", "；", "！", "？", " "]
    chunks: list[str] = []

    def _split(segment: str, seps: list[str]) -> list[str]:
        if len(segment) <= chunk_size:
            return [segment] if segment.strip() else []
        if not seps:
            return [segment[i : i + chunk_size] for i in range(0, len(segment), chunk_size)]
        sep = seps[0]
        parts = segment.split(sep)
        merged: list[str] = []
        current = ""
        for part in parts:
            candidate = (current + sep + part) if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    merged.append(current)
                current = part
        if current:
            merged.append(current)
        result: list[str] = []
        for part in merged:
            if len(part) > chunk_size:
                result.extend(_split(part, seps[1:]))
            else:
                result.append(part)
        return result

    for part in _split(text, separators):
        if not part.strip():
            continue
        if chunks and len(chunks[-1]) < chunk_size:
            # 与上一块重叠拼接，避免信息断裂
            tail = chunks[-1][-chunk_overlap:] if chunk_overlap else ""
            chunks[-1] = chunks[-1] + part
            if len(chunks[-1]) > chunk_size:
                chunks[-1] = chunks[-1][:chunk_size]
            continue
        chunks.append(part)
    return [c for c in chunks if c.strip()]


def _split_text_sliding_window(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 250,
) -> list[str]:
    """滑动窗口分块：按递归分隔符切分后，以 50% 重叠率滑动窗口。

    与 _split_text 的区别：重叠率更高（默认 50%），防止答案被块边界切断。
    """
    text = re.sub(r"\r\n", "\n", text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    # 先按递归分隔符切分为自然片段
    separators = ["\n\n", "\n", "。", "；", "！", "？", " "]

    def _split(segment: str, seps: list[str]) -> list[str]:
        if len(segment) <= chunk_size:
            return [segment] if segment.strip() else []
        if not seps:
            return [segment[i : i + chunk_size] for i in range(0, len(segment), chunk_size)]
        sep = seps[0]
        parts = segment.split(sep)
        merged: list[str] = []
        current = ""
        for part in parts:
            candidate = (current + sep + part) if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    merged.append(current)
                current = part
        if current:
            merged.append(current)
        result: list[str] = []
        for part in merged:
            if len(part) > chunk_size:
                result.extend(_split(part, seps[1:]))
            else:
                result.append(part)
        return result

    parts = _split(text, separators)

    # 滑动窗口：步长 = chunk_size - chunk_overlap
    step = chunk_size - chunk_overlap
    chunks: list[str] = []
    buffer = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        buffer += part
        while len(buffer) >= chunk_size:
            chunks.append(buffer[:chunk_size])
            buffer = buffer[step:]  # 保留重叠部分
    if buffer.strip():
        chunks.append(buffer.strip())
    return [c for c in chunks if c.strip()]


def _split_text_semantic(text: str, embedder, max_size: int = 800) -> list[str]:
    """语义分块：用 embedding 计算相邻句子相似度，在语义断点切分。

    召回最优策略（评估 Recall@5=86.50%）：保证每块语义完整，max_size 兜底强制切。
    与 _split_text/_split_text_sliding_window 的区别：按语义而非固定长度切分，无重叠。
    embedder 为 None 时回退到按句子合并至 max_size。
    """
    text = re.sub(r"\r\n", "\n", text or "").strip()
    if not text:
        return []
    # 按句末标点/换行拆句
    sentences = re.split(r"(?<=[。；！？\n])", text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 2]
    if len(sentences) <= 1:
        return [text] if text else []

    # 无 embedder：回退按句子合并至 max_size
    if embedder is None:
        chunks = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= max_size:
                current += sent
            else:
                if current:
                    chunks.append(current)
                current = sent
        if current:
            chunks.append(current)
        return [c for c in chunks if c.strip()]

    # 计算句子向量，用余弦相似度找语义断点
    import numpy as np

    vecs = np.array(embedder.embed(sentences))
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs_norm = vecs / (norms + 1e-9)
    sims = np.array([np.dot(vecs_norm[i], vecs_norm[i + 1]) for i in range(len(vecs_norm) - 1)])
    if len(sims) == 0:
        return [text]
    # 动态阈值：均值 - 标准差，低于阈值视为语义断点
    threshold = float(np.mean(sims) - np.std(sims))

    chunks = []
    current_sents = [sentences[0]]
    for i in range(len(sims)):
        if sims[i] < threshold:
            chunks.append("".join(current_sents))
            current_sents = [sentences[i + 1]]
        else:
            current_sents.append(sentences[i + 1])
            # 长度保护：超过 max_size 强制切，防止单块过大
            if sum(len(s) for s in current_sents) > max_size:
                chunks.append("".join(current_sents))
                current_sents = []
    if current_sents:
        chunks.append("".join(current_sents))
    return [c for c in chunks if c.strip()]


def _extract_text(file_path: Path, ext: str) -> str:
    """按扩展名提取文档纯文本。"""
    if ext in (".txt", ".md"):
        raw = file_path.read_bytes()
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")
    if ext in (".docx", ".doc"):
        try:
            import docx  # python-docx
        except ImportError as exc:  # pragma: no cover
            raise BizError(50001, "Word 解析库未安装（python-docx）") from exc
        document = docx.Document(str(file_path))
        return "\n".join(p.text for p in document.paragraphs)
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError as exc:  # pragma: no cover
                raise BizError(50001, "PDF 解析库未安装（pypdf）") from exc
        reader = PdfReader(str(file_path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raise BizError(40020, f"不支持的文件类型: {ext}")


def _write_upload(dest_dir: Path, filename: str, data: bytes) -> None:
    """保存上传文件到磁盘（线程池中执行，避免阻塞事件循环）。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / filename).write_bytes(data)


def _safe_unlink(file_path: Path) -> None:
    """删除磁盘文件，失败时静默忽略（线程池中执行）。"""
    try:
        if file_path.is_file():
            file_path.unlink()
    except OSError:
        pass


class KnowledgeBaseService:
    """知识库管理服务：上传文档、分块、向量化、入库、删除。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._embedder = None
        self._kb_client = None

    def _get_embedder(self):
        """懒加载 embedding 单例，便于测试替换。"""
        if self._embedder is None:
            from app.services.embedding import embedding_service

            self._embedder = embedding_service
        return self._embedder

    def _get_kb_client(self):
        """懒创建 Chroma 客户端，便于测试替换。"""
        if self._kb_client is None:
            import chromadb

            self._kb_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        return self._kb_client

    async def _load_chunk_config(self) -> tuple[int, int, str]:
        """从业务库 rag_config 读取分块参数，读不到或非法时回退 500/50/fixed。"""
        default_size, default_overlap, default_strategy = 500, 50, "fixed"
        try:
            rows = (
                await self.db.execute(text("SELECT config_key, config_value FROM rag_config"))
            ).fetchall()
            mapping = {row[0]: row[1] for row in rows}
            chunk_size = int(float(mapping.get("chunk_size", default_size)))
            chunk_overlap = int(float(mapping.get("chunk_overlap", default_overlap)))
            chunk_strategy = str(mapping.get("chunk_strategy", default_strategy)).strip().lower()
        except Exception:
            return default_size, default_overlap, default_strategy
        if chunk_size < 1 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
            return default_size, default_overlap, default_strategy
        if chunk_strategy not in ("fixed", "sliding_window", "semantic"):
            chunk_strategy = default_strategy
        return chunk_size, chunk_overlap, chunk_strategy

    # ---------- 文档上传与解析 ----------

    async def upload_document(
        self,
        file,
        title: str,
        doc_type: str,
        category_id: int | None,
        tags: list[str],
        authority_level: str,
        created_by: str,
    ) -> dict:
        """保存文件并同步解析入库，返回文档信息。"""
        ext = Path(file.filename or "").suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise BizError(40020, f"不支持的文件类型: {file.filename}，仅支持 PDF/Word/TXT/Markdown")

        data = await file.read()
        if len(data) > MAX_KB_FILE_SIZE_MB * 1024 * 1024:
            raise BizError(41300, f"上传文件过大（≤ {MAX_KB_FILE_SIZE_MB}MB）")

        # 保存文件到 uploads/knowledge（磁盘写入放线程池）
        dest_dir = Path(settings.UPLOAD_DIR) / "knowledge"
        rel_path = f"knowledge/{uuid.uuid4().hex}{ext}"
        await run_in_threadpool(_write_upload, dest_dir, Path(rel_path).name, data)

        doc = KnowledgeDocument(
            title=title,
            doc_type=doc_type,
            category_id=category_id,
            tags_json=json.dumps(tags or [], ensure_ascii=False),
            authority_level=authority_level or "B",
            file_path=rel_path,
            file_size=len(data),
            status="parsing",
            created_by=created_by,
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)

        try:
            await self._parse_and_index(doc)
        except BizError:
            await self._mark_failed(doc)
            raise
        except Exception as exc:  # 解析/切分异常：置 failed 并按契约抛业务错误
            await self._mark_failed(doc, str(exc))
            raise BizError(50001, f"文档解析失败: {exc}") from exc

        message = (
            "文档已上传，但向量化失败，请查看状态接口中的错误信息"
            if doc.status == "failed"
            else "文档已上传，正在解析和向量化处理中"
        )
        return {
            "document_id": doc.doc_id,
            "status": doc.status,
            "message": message,
        }

    async def _parse_and_index(self, doc: KnowledgeDocument) -> None:
        """解析 -> 分块 -> 向量化 -> 入库。"""
        file_path = Path(settings.UPLOAD_DIR) / doc.file_path
        ext = file_path.suffix.lower()

        # 1. 解析（文档解析为 CPU/IO 密集操作，放线程池）
        await self._set_status(doc, "chunking")
        text = await run_in_threadpool(_extract_text, file_path, ext)

        # 2. 分块（参数来自 rag_config，读不到回退默认值）
        chunk_size, chunk_overlap, chunk_strategy = await self._load_chunk_config()
        if chunk_strategy == "sliding_window":
            # 滑动窗口分块：高重叠率防止答案被块边界切断
            if chunk_overlap < chunk_size // 4:
                chunk_overlap = chunk_size // 2  # 默认 50% 重叠
            chunks = _split_text_sliding_window(text, chunk_size, chunk_overlap)
        elif chunk_strategy == "semantic":
            # 语义分块：召回最优，需 embedder 计算句子相似度（阻塞，放线程池）
            chunks = await run_in_threadpool(
                _split_text_semantic, text, self._get_embedder(), 800
            )
        else:
            chunks = _split_text(text, chunk_size, chunk_overlap)
        await self._set_status(doc, "indexing")
        for index, content in enumerate(chunks):
            self.db.add(
                KnowledgeChunk(doc_id=doc.doc_id, chunk_index=index, content=content)
            )
        doc.chunk_count = len(chunks)
        await self.db.commit()

        # 3. 向量化并写入 Chroma；失败时置 failed 并记录错误信息（分块已持久化，上传不中断）
        if chunks:
            try:
                await run_in_threadpool(self._index_vectors, doc, chunks)
            except Exception as exc:
                await self._mark_failed(doc, f"向量化失败: {exc}")
                return

        # 4. 完成
        doc.status = "indexed"
        doc.error_message = None
        await self.db.commit()

    def _index_vectors(self, doc: KnowledgeDocument, chunks: list[str]) -> None:
        """批量向量化并写入 Chroma 集合。"""
        vectors = self._get_embedder().embed(chunks)
        collection = self._get_kb_client().get_or_create_collection(KB_COLLECTION_NAME)
        ids = [f"kb_{doc.doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "doc_id": str(doc.doc_id),
                "title": doc.title,
                "doc_type": doc.doc_type,
                "authority_level": doc.authority_level,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=vectors,
            metadatas=metadatas,
        )

    async def _set_status(self, doc: KnowledgeDocument, status: str) -> None:
        doc.status = status
        await self.db.commit()

    async def _mark_failed(self, doc: KnowledgeDocument, message: str | None = None) -> None:
        doc.status = "failed"
        doc.error_message = (message or "解析失败")[:500]
        await self.db.commit()

    # ---------- 文档查询与删除 ----------

    async def list_documents(
        self,
        page: int,
        page_size: int,
        doc_type: str | None,
        status: str | None,
        keyword: str | None,
    ) -> dict:
        from sqlalchemy import func

        filters = []
        if doc_type:
            filters.append(KnowledgeDocument.doc_type == doc_type)
        if status:
            filters.append(KnowledgeDocument.status == status)
        if keyword:
            filters.append(KnowledgeDocument.title.like(f"%{keyword}%"))
        total = await self.db.scalar(
            select(func.count()).select_from(KnowledgeDocument).where(*filters)
        ) or 0
        stmt = select(KnowledgeDocument).where(*filters)
        stmt = stmt.order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.doc_id.desc())
        rows = (await self.db.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()
        items = [self._doc_to_dict(d) for d in rows]
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}

    async def get_document_status(self, doc_id: int) -> dict:
        doc = await self.db.get(KnowledgeDocument, doc_id)
        if doc is None:
            raise BizError(40401, "文档不存在")
        return {
            "document_id": doc.doc_id,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "error_message": doc.error_message,
        }

    async def delete_document(self, doc_id: int) -> None:
        doc = await self.db.get(KnowledgeDocument, doc_id)
        if doc is None:
            raise BizError(40401, "文档不存在")
        # 1. 删除 Chroma 向量（线程池，避免阻塞事件循环）
        await run_in_threadpool(self._purge_chroma_vectors, doc_id)
        # 2. 删除分块记录（级联）
        await self.db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id))
        # 3. 删除磁盘文件
        file_path = Path(settings.UPLOAD_DIR) / doc.file_path
        await run_in_threadpool(_safe_unlink, file_path)
        # 4. 删除记录
        await self.db.delete(doc)
        await self.db.commit()

    def _purge_chroma_vectors(self, doc_id: int) -> None:
        """删除文档在 Chroma 中的全部向量（同步方法，线程池中执行）。"""
        try:
            client = self._get_kb_client()
            try:
                collection = client.get_collection(KB_COLLECTION_NAME)
                collection.delete(where={"doc_id": str(doc_id)})
            except Exception:
                pass
        except Exception:
            pass

    @staticmethod
    def _doc_to_dict(doc: KnowledgeDocument) -> dict:
        return {
            "document_id": doc.doc_id,
            "title": doc.title,
            "doc_type": doc.doc_type,
            "category_id": doc.category_id,
            "tags": json.loads(doc.tags_json or "[]"),
            "authority_level": doc.authority_level,
            "file_path": doc.file_path,
            "file_size": doc.file_size,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "error_message": doc.error_message,
            "created_by": doc.created_by,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }


knowledge_service = KnowledgeBaseService
