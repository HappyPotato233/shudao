"""知识库管理接口集成测试（Admin only）。

通过 monkeypatch 替换 KnowledgeBaseService 类的 _get_embedder / _get_kb_client，
跳过真实向量化模型与 Chroma，验证接口权限、上传落库、过滤、状态、删除清理与分类 CRUD。
"""
import io
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.knowledge_service import KnowledgeBaseService

API = settings.API_V1_PREFIX

DOC_CONTENT = (
    "安全生产管理制度总则。进入施工现场必须佩戴安全帽并系好帽带，严禁穿拖鞋作业。"
    "高处作业必须系挂安全带，做到高挂低用，作业前检查安全带是否完好。"
    "动火作业须办理动火审批手续，现场配备灭火器材并设专人监护。"
)


class _FakeEmbedder:
    """固定维度（8）的假向量化器。"""

    def embed(self, texts):
        return [[0.1] * 8 for _ in texts]


class _FakeCollection:
    def __init__(self, store: dict):
        self._store = store

    def upsert(self, ids, documents, embeddings, metadatas):
        self._store["upserted"].extend(ids)

    def delete(self, where):
        self._store["deleted"].append(where)


class _FakeKBClient:
    """记录 upsert / delete 调用的假 Chroma 客户端。"""

    def __init__(self):
        self.store = {"upserted": [], "deleted": []}

    def get_or_create_collection(self, name):
        return _FakeCollection(self.store)

    def get_collection(self, name):
        return _FakeCollection(self.store)


@pytest.fixture()
def fake_kb(client, monkeypatch):
    """在类级别替换懒加载点，跳过真实模型与 Chroma。"""
    kb = _FakeKBClient()
    monkeypatch.setattr(KnowledgeBaseService, "_get_embedder", lambda self: _FakeEmbedder())
    monkeypatch.setattr(KnowledgeBaseService, "_get_kb_client", lambda self: kb)
    return kb


def _upload(client, headers, title, doc_type="regulation", filename="doc.txt",
            content=DOC_CONTENT, tags=None, category_id=None):
    files = {"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")}
    data = {"title": title, "doc_type": doc_type, "authority_level": "B"}
    if category_id is not None:
        data["category_id"] = str(category_id)
    if tags is not None:
        data["tags"] = tags
    return client.post(f"{API}/knowledge/documents", headers=headers, files=files, data=data)


def test_non_admin_forbidden(client, auth_headers, fake_kb):
    user = auth_headers("zhangsan")

    resp = _upload(client, user, title="未授权上传", doc_type="other")
    assert resp.status_code == 403
    assert resp.json()["code"] == 40303

    resp = client.delete(f"{API}/knowledge/categories/999", headers=user)
    assert resp.status_code == 403
    assert resp.json()["code"] == 40303


def test_admin_upload_txt_document_indexed(client, auth_headers, db, fake_kb):
    admin = auth_headers("admin")

    resp = _upload(client, admin, title="测试安全管理制度", doc_type="regulation", tags="安全,制度")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    doc_id = body["data"]["document_id"]
    assert doc_id
    assert body["data"]["status"] == "indexed"

    # 列表可查到且状态 indexed
    listed = client.get(f"{API}/knowledge/documents", headers=admin).json()["data"]
    item = next(i for i in listed["items"] if i["document_id"] == doc_id)
    assert item["title"] == "测试安全管理制度"
    assert item["doc_type"] == "regulation"
    assert item["status"] == "indexed"
    assert item["tags"] == ["安全", "制度"]
    assert item["chunk_count"] >= 1

    # 分块落库
    chunk_rows = db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id)
    ).all()
    assert chunk_rows
    assert all(c.content.strip() for c in chunk_rows)

    # 向量写入（mock 层记录）
    assert any(i.startswith(f"kb_{doc_id}_") for i in fake_kb.store["upserted"])

    # 文件保存到 UPLOAD_DIR/knowledge/
    doc = db.get(KnowledgeDocument, doc_id)
    assert doc.file_path.startswith("knowledge/")
    assert (Path(settings.UPLOAD_DIR) / doc.file_path).is_file()


def test_list_documents_keyword_and_type_filters(client, auth_headers, fake_kb):
    admin = auth_headers("admin")
    assert _upload(client, admin, title="测试安全法规汇编", doc_type="regulation").status_code == 200
    assert _upload(client, admin, title="现场操作手册", doc_type="procedure").status_code == 200

    data = client.get(
        f"{API}/knowledge/documents", params={"keyword": "测试"}, headers=admin
    ).json()["data"]
    assert data["total"] == 1
    assert [i["title"] for i in data["items"]] == ["测试安全法规汇编"]

    data = client.get(
        f"{API}/knowledge/documents", params={"keyword": "不存在的关键词"}, headers=admin
    ).json()["data"]
    assert data["total"] == 0
    assert data["items"] == []

    data = client.get(
        f"{API}/knowledge/documents", params={"type": "procedure"}, headers=admin
    ).json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "现场操作手册"

    data = client.get(
        f"{API}/knowledge/documents", params={"status": "indexed"}, headers=admin
    ).json()["data"]
    assert data["total"] == 2


def test_document_status(client, auth_headers, fake_kb):
    admin = auth_headers("admin")
    doc_id = _upload(client, admin, title="状态查询文档", doc_type="case").json()["data"]["document_id"]

    resp = client.get(f"{API}/knowledge/documents/{doc_id}/status", headers=admin)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["document_id"] == doc_id
    assert data["status"] == "indexed"
    assert data["chunk_count"] >= 1
    assert data["error_message"] is None


def test_delete_document_cleans_up(client, auth_headers, db, fake_kb):
    admin = auth_headers("admin")
    doc_id = _upload(client, admin, title="待删除文档", doc_type="other").json()["data"]["document_id"]

    doc = db.get(KnowledgeDocument, doc_id)
    file_path = Path(settings.UPLOAD_DIR) / doc.file_path
    assert file_path.is_file()

    resp = client.delete(f"{API}/knowledge/documents/{doc_id}", headers=admin)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    # 列表不再包含
    listed = client.get(f"{API}/knowledge/documents", headers=admin).json()["data"]
    assert all(i["document_id"] != doc_id for i in listed["items"])
    assert listed["total"] == 0

    # 记录与分块清零、磁盘文件已删、向量已按 doc_id 清理
    db.expire_all()
    assert db.get(KnowledgeDocument, doc_id) is None
    assert db.scalar(
        select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id)
    ) == 0
    assert not file_path.exists()
    assert {"doc_id": str(doc_id)} in fake_kb.store["deleted"]


def test_category_crud_flow(client, auth_headers):
    admin = auth_headers("admin")

    created = client.post(f"{API}/knowledge/categories", json={"name": "法规类"}, headers=admin)
    assert created.status_code == 200
    cid = created.json()["data"]["category_id"]
    assert created.json()["data"]["level"] == 1

    tree = client.get(f"{API}/knowledge/categories", headers=admin).json()["data"]
    node = next(n for n in tree if n["category_id"] == cid)
    assert node["name"] == "法规类"
    assert node["children"] == []

    # 改名
    renamed = client.put(
        f"{API}/knowledge/categories/{cid}", json={"name": "法律法规类"}, headers=admin
    )
    assert renamed.json()["code"] == 0
    tree = client.get(f"{API}/knowledge/categories", headers=admin).json()["data"]
    assert next(n for n in tree if n["category_id"] == cid)["name"] == "法律法规类"

    # 建子分类（level=2，挂到父节点 children 下）
    child = client.post(
        f"{API}/knowledge/categories",
        json={"name": "国家法律", "parent_id": cid},
        headers=admin,
    )
    child_id = child.json()["data"]["category_id"]
    assert child.json()["data"]["level"] == 2
    tree = client.get(f"{API}/knowledge/categories", headers=admin).json()["data"]
    parent_node = next(n for n in tree if n["category_id"] == cid)
    assert any(c["category_id"] == child_id for c in parent_node["children"])

    # 删父分类被拒（存在子分类）
    blocked = client.delete(f"{API}/knowledge/categories/{cid}", headers=admin)
    assert blocked.status_code == 400
    assert blocked.json()["code"] == 40001

    # 删子成功 -> 删父成功
    assert client.delete(f"{API}/knowledge/categories/{child_id}", headers=admin).json()["code"] == 0
    assert client.delete(f"{API}/knowledge/categories/{cid}", headers=admin).json()["code"] == 0
    tree = client.get(f"{API}/knowledge/categories", headers=admin).json()["data"]
    assert all(n["category_id"] not in (cid, child_id) for n in tree)


def test_upload_rejects_unsupported_file_type(client, auth_headers, fake_kb):
    admin = auth_headers("admin")

    resp = client.post(
        f"{API}/knowledge/documents",
        headers=admin,
        files={"file": ("virus.exe", io.BytesIO(b"MZ fake exe"), "application/octet-stream")},
        data={"title": "非法文件", "doc_type": "other"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40020

    # 非法 doc_type 同样被拒
    resp = _upload(client, admin, title="非法类型", doc_type="movie")
    assert resp.status_code == 400
    assert resp.json()["code"] == 40001
