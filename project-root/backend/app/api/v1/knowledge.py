"""知识库管理接口（Admin only）。
对齐 API.md 第 8 章：
- 8.1 GET    /knowledge/documents            文档列表
- 8.2 POST   /knowledge/documents            上传文档
- 8.3 GET    /knowledge/documents/{id}/status 解析状态
- 8.4 DELETE /knowledge/documents/{id}       删除文档
- 8.5 GET/POST/PUT/DELETE /knowledge/categories 分类树管理"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_roles_async
from app.core.response import BizError, success
from app.models.base import get_db
from app.models.knowledge import KnowledgeCategory, KnowledgeDocument
from app.schemas.knowledge import CategoryCreateRequest, CategoryUpdateRequest
from app.services.knowledge_service import KnowledgeBaseService

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])

DOC_TYPES = {"regulation", "procedure", "case", "emergency", "other"}
AUTHORITY_LEVELS = {"A", "B", "C"}


# ---------- 文档管理 ----------

@router.get("/documents", summary="知识库文档列表")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: str | None = Query(None, alias="type"),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await KnowledgeBaseService(db).list_documents(page, page_size, type, status, keyword)
    return success(data)


@router.post("/documents", summary="上传知识库文档")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=200),
    doc_type: str = Form("other"),
    category_id: int | None = Form(None),
    tags: str | None = Form(None),
    authority_level: str = Form("B"),
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    if doc_type not in DOC_TYPES:
        raise BizError(40001, f"doc_type 不合法，可选 {', '.join(sorted(DOC_TYPES))}")
    if authority_level not in AUTHORITY_LEVELS:
        raise BizError(40001, "authority_level 不合法，可选 A / B / C")
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    data = await KnowledgeBaseService(db).upload_document(
        file=file,
        title=title,
        doc_type=doc_type,
        category_id=category_id,
        tags=tag_list,
        authority_level=authority_level,
        created_by=ctx.user_id,
    )
    return success(data)


@router.get("/documents/{doc_id}/status", summary="文档解析状态查询")
async def get_document_status(
    doc_id: int,
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    return success(await KnowledgeBaseService(db).get_document_status(doc_id))


@router.delete("/documents/{doc_id}", summary="删除知识库文档")
async def delete_document(
    doc_id: int,
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    await KnowledgeBaseService(db).delete_document(doc_id)
    return success(None, message="文档已删除")


# ---------- 分类管理 ----------

def _build_category_tree(rows: list[KnowledgeCategory]) -> list[dict]:
    """把扁平分类列表组装为分类树。"""
    nodes = {
        c.category_id: {
            "category_id": c.category_id,
            "name": c.name,
            "parent_id": c.parent_id,
            "level": c.level,
            "sort_order": c.sort_order,
            "children": [],
        }
        for c in rows
    }
    roots: list[dict] = []
    for c in rows:
        node = nodes[c.category_id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


@router.get("/categories", summary="知识库分类树")
async def list_categories(
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    # 固定分类体系：仅支持 国家规定 / 地方规定 / 内部规定 三类，缺失时自动补齐（幂等）
    fixed_names = ("国家规定", "地方规定", "内部规定")
    existing = {
        c.name
        for c in (
            await db.scalars(
                select(KnowledgeCategory).where(KnowledgeCategory.parent_id.is_(None))
            )
        ).all()
    }
    for idx, name in enumerate(fixed_names, start=1):
        if name not in existing:
            db.add(KnowledgeCategory(name=name, parent_id=None, level=1, sort_order=idx))
    await db.commit()

    rows = (
        await db.scalars(
            select(KnowledgeCategory).order_by(
                KnowledgeCategory.sort_order, KnowledgeCategory.category_id
            )
        )
    ).all()
    return success(_build_category_tree(rows))


@router.post("/categories", summary="创建知识库分类")
async def create_category(
    req: CategoryCreateRequest,
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    level = 1
    if req.parent_id is not None:
        parent = await db.get(KnowledgeCategory, req.parent_id)
        if parent is None:
            raise BizError(40401, "父分类不存在")
        level = (parent.level or 1) + 1
    category = KnowledgeCategory(
        name=req.name,
        parent_id=req.parent_id,
        level=level,
        sort_order=req.sort_order,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return success(
        {
            "category_id": category.category_id,
            "name": category.name,
            "parent_id": category.parent_id,
            "level": category.level,
            "sort_order": category.sort_order,
        },
        message="分类已创建",
    )


@router.put("/categories/{category_id}", summary="编辑知识库分类")
async def update_category(
    category_id: int,
    req: CategoryUpdateRequest,
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(KnowledgeCategory, category_id)
    if category is None:
        raise BizError(40401, "分类不存在")
    if req.name is not None:
        category.name = req.name
    if req.parent_id is not None:
        if req.parent_id == category_id:
            raise BizError(40001, "父分类不能是自身")
        parent = await db.get(KnowledgeCategory, req.parent_id)
        if parent is None:
            raise BizError(40401, "父分类不存在")
        category.parent_id = req.parent_id
        category.level = (parent.level or 1) + 1
    if req.sort_order is not None:
        category.sort_order = req.sort_order
    await db.commit()
    return success(None, message="分类已更新")


@router.delete("/categories/{category_id}", summary="删除知识库分类")
async def delete_category(
    category_id: int,
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(KnowledgeCategory, category_id)
    if category is None:
        raise BizError(40401, "分类不存在")
    child_count = await db.scalar(
        select(func.count())
        .select_from(KnowledgeCategory)
        .where(KnowledgeCategory.parent_id == category_id)
    ) or 0
    if child_count:
        raise BizError(40001, "该分类下存在子分类，无法删除")
    doc_count = await db.scalar(
        select(func.count())
        .select_from(KnowledgeDocument)
        .where(KnowledgeDocument.category_id == category_id)
    ) or 0
    if doc_count:
        raise BizError(40001, "该分类下存在文档，无法删除")
    await db.delete(category)
    await db.commit()
    return success(None, message="分类已删除")
