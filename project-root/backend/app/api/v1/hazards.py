"""隐患管理接口（H01-H06, H09）"""
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import AuthContext, get_auth_context_async
from app.core.permissions import require_roles_async
from app.core.response import BizError, success
from app.models.base import get_db
from app.schemas.hazard import AssignRequest, HazardCreate, RectifyRequest, ReviewRequest
from app.services import hazard_service, pdf_export, vision

router = APIRouter(prefix="/hazards", tags=["隐患安全管理"])


@router.post("", summary="隐患上报")
async def report_hazard(
    title: str = Form(...),
    description: str = Form(...),
    level: str = Form(...),
    category: str = Form(...),
    location: str = Form(...),
    location_coords: str | None = Form(None),
    occurred_at: str = Form(...),
    project: str = Form(...),
    images: list[UploadFile] | None = File(None),
    detections_json: str | None = Form(None),
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    data = HazardCreate(
        title=title,
        description=description,
        level=level,
        category=category,
        location=location,
        location_coords=location_coords,
        occurred_at=occurred_at,
        project=project,
    )
    return success(await hazard_service.create_hazard(db, ctx, data, images or [], detections_json))


@router.post("/ai-detect", summary="隐患 AI 识别（H09）")
async def ai_detect(
    images: list[UploadFile] = File(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    # 模型推理为 CPU 密集同步操作，放线程池避免阻塞事件循环
    return success(await run_in_threadpool(vision.detect_and_annotate, images, title, description))


@router.get("", summary="隐患列表（H02）")
async def list_hazards(
    page: int = Query(1),
    page_size: int = Query(20),
    status: str | None = Query(None),
    level: str | None = Query(None),
    category: str | None = Query(None),
    project: str | None = Query(None),
    keyword: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    ctx: AuthContext = Depends(require_roles_async("User", "Admin")),
    db: AsyncSession = Depends(get_db),
):
    filters = {
        "page": page,
        "page_size": page_size,
        "status": status,
        "level": level,
        "category": category,
        "project": project,
        "keyword": keyword,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    return success(await hazard_service.list_hazards(db, ctx, filters))


@router.get("/{hazard_id}", summary="隐患详情（H03）")
async def get_hazard(
    hazard_id: str,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await hazard_service.get_hazard(db, ctx, hazard_id))


@router.get("/{hazard_id}/export", summary="隐患详情 PDF 导出（H03）")
async def export_hazard(
    hazard_id: str,
    format: str = Query("pdf"),
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    if format.lower() != "pdf":
        raise BizError(40001, "当前仅支持 PDF 格式导出")

    detail = await hazard_service.get_hazard(db, ctx, hazard_id)
    content = await run_in_threadpool(pdf_export.build_hazard_pdf, detail)
    filename = f"{hazard_id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/{hazard_id}/assign", summary="隐患派单（H04）")
async def assign_hazard(
    hazard_id: str,
    assignee_id: str = Form(...),
    requirements: str = Form(...),
    deadline: str = Form(...),
    priority: str = Form(...),
    attachments: list[UploadFile] | None = File(None),
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    req = AssignRequest(
        assignee_id=assignee_id,
        requirements=requirements,
        deadline=deadline,
        priority=priority,
    )
    return success(await hazard_service.assign_hazard(db, ctx, hazard_id, req, attachments or []))


@router.post("/{hazard_id}/rectify", summary="整改反馈（H05）")
async def rectify_hazard(
    hazard_id: str,
    measures: str = Form(...),
    completed_at: str | None = Form(None),
    images_after: list[UploadFile] | None = File(None),
    attachments: list[UploadFile] | None = File(None),
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    req = RectifyRequest(measures=measures, completed_at=completed_at)
    return success(
        await hazard_service.rectify_hazard(db, ctx, hazard_id, req, images_after or [], attachments or [])
    )


@router.post("/{hazard_id}/review", summary="隐患验收（H06）")
async def review_hazard(
    hazard_id: str,
    req: ReviewRequest,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await hazard_service.review_hazard(db, ctx, hazard_id, req))


@router.delete("/{hazard_id}", summary="删除隐患")
async def delete_hazard(
    hazard_id: str,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    await hazard_service.delete_hazard(db, ctx, hazard_id)
    return success(None)
