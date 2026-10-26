"""隐患管理业务逻辑（async）"""
import datetime
import json
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext
from app.core.config import settings
from app.core.permissions import can_view_hazard, is_assignee
from app.core.response import BizError, ErrorCode
from app.models.hazard import (
    Hazard,
    HazardAssignment,
    HazardDetection,
    HazardMedia,
    HazardRectification,
    HazardReview,
    HazardTimeline,
)
from app.models.role import Role
from app.models.user_orm import User
from app.schemas.hazard import AssignRequest, HazardCreate, RectifyRequest, ReviewRequest
from app.services import notification_service
from app.services.annotator import annotate
from app.services.idgen import generate_hazard_id
from app.services.storage import public_url, save_upload


def now_cst() -> str:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


# AsyncSession 下 lazy load 会触发 MissingGreenlet，统一预加载详情所需关系
_HAZARD_DETAIL_LOADS = (
    selectinload(Hazard.reporter),
    selectinload(Hazard.media),
    selectinload(Hazard.detections),
    selectinload(Hazard.timeline),
    selectinload(Hazard.assignments).selectinload(HazardAssignment.assignee),
    selectinload(Hazard.rectifications),
    selectinload(Hazard.reviews),
)

# 列表摘要所需关系
_HAZARD_SUMMARY_LOADS = (
    selectinload(Hazard.reporter),
    selectinload(Hazard.media),
)

# commit 后 refresh 时的关系名（重新加载 summary 用）
_SUMMARY_REFRESH = ["reporter", "media"]


async def _get_hazard(db: AsyncSession, hazard_id: str, detail: bool = True) -> Hazard:
    """按 ID 获取隐患；detail=True 时预加载全部详情关系。"""
    q = select(Hazard).where(Hazard.hazard_id == hazard_id)
    if detail:
        q = q.options(*_HAZARD_DETAIL_LOADS)
    hazard = (await db.execute(q)).scalar_one_or_none()
    if hazard is None:
        raise BizError(*ErrorCode.HAZARD_NOT_FOUND)
    return hazard


def _latest(items):
    if not items:
        return None
    return sorted(items, key=lambda x: x.created_at or "")[-1]


def hazard_to_summary(h: Hazard) -> dict:
    return {
        "hazard_id": h.hazard_id,
        "title": h.title,
        "level": h.level,
        "status": h.status,
        "category": h.category,
        "reporter_name": h.reporter.name if h.reporter else "",
        "project": h.project,
        "created_at": h.created_at,
        "thumbnail_url": public_url(h.media[0].file_path) if h.media else None,
    }


def _timeline_nodes(h: Hazard) -> list[dict]:
    nodes = sorted(h.timeline, key=lambda t: t.created_at or "")
    return [
        {
            "node": t.action_type,
            "operator": t.operator.name if t.operator else "",
            "time": t.created_at,
            "note": t.note,
        }
        for t in nodes
    ]


def build_detail(h: Hazard) -> dict:
    assignment = _latest(h.assignments)
    rectification = _latest(h.rectifications)
    review = _latest(h.reviews)
    return {
        "hazard_id": h.hazard_id,
        "title": h.title,
        "description": h.description,
        "level": h.level,
        "category": h.category,
        "location": h.location,
        "location_coords": h.location_coords,
        "project": h.project,
        "reporter": {"id": h.reporter.user_id, "name": h.reporter.name} if h.reporter else None,
        "occurred_at": h.occurred_at,
        "created_at": h.created_at,
        "status": h.status,
        "media": {
            "images": [public_url(m.file_path) for m in h.media if m.media_type == "image_original"],
            "annotated_images": [public_url(m.file_path) for m in h.media if m.media_type == "image_annotated"],
            "detections": [
                {
                    "id": d.id,
                    "label": d.label,
                    "risk": d.risk,
                    "bbox_norm": json.loads(d.bbox_norm),
                    "bbox_px": json.loads(d.bbox_px) if d.bbox_px else None,
                    "color_bgr": json.loads(d.color_bgr),
                    "conf": d.conf,
                    "fix": d.fix,
                    "note": d.note,
                }
                for d in h.detections
            ],
        },
        "timeline": _timeline_nodes(h),
        "assignment": {
            "assignee": {"id": assignment.assignee.user_id, "name": assignment.assignee.name} if assignment and assignment.assignee else None,
            "requirements": assignment.requirements if assignment else None,
            "deadline": assignment.deadline if assignment else None,
            "priority": assignment.priority if assignment else None,
            "attachments": json.loads(assignment.attachments_json or "[]") if assignment else [],
        } if assignment else None,
        "rectification": {
            "measures": rectification.measures,
            "images": json.loads(rectification.images_json or "[]"),
            "attachments": json.loads(rectification.attachments_json or "[]"),
            "completed_at": rectification.completed_at,
            "round": rectification.round,
        } if rectification else None,
        "review": {
            "result": review.result,
            "comment": review.comment,
        } if review else None,
    }


async def create_hazard(
    db: AsyncSession,
    ctx: AuthContext,
    data: HazardCreate,
    files: list[UploadFile],
    detections_json: str | None = None,
) -> dict:
    files = files or []
    if len(files) > settings.MAX_HAZARD_IMAGES:
        raise BizError(*ErrorCode.IMAGE_COUNT_EXCEEDED)

    hazard_id = await generate_hazard_id(db)
    hazard = Hazard(
        hazard_id=hazard_id,
        title=data.title,
        description=data.description,
        level=data.level,
        category=data.category,
        location=data.location,
        location_coords=data.location_coords,
        project=data.project,
        reporter_id=ctx.user_id,
        status="pending",
        occurred_at=data.occurred_at,
    )
    db.add(hazard)
    await db.flush()

    media_objs: list[tuple[int, HazardMedia]] = []
    for idx, f in enumerate(files[: settings.MAX_HAZARD_IMAGES]):
        rel, size = save_upload(f, f"hazards/{hazard_id}")
        media = HazardMedia(
            hazard_id=hazard_id,
            media_type="image_original",
            file_path=rel,
            file_size=size,
            sort_order=idx,
            context="report",
        )
        db.add(media)
        await db.flush()
        media_objs.append((idx, media))

    if detections_json:
        await _persist_ai_detections(db, hazard_id, media_objs, detections_json)

    db.add(
        HazardTimeline(
            hazard_id=hazard_id,
            action_type="reported",
            operator_id=ctx.user_id,
            note="隐患首次上报",
        )
    )

    officers = (
        (
            await db.execute(
                select(User)
                .join(Role, Role.role_id == User.role_id)
                .where(Role.name == "Admin", User.project == data.project, User.is_active == 1)
            )
        )
        .scalars()
        .all()
    )
    for officer in officers:
        notification_service.create_notification(
            db,
            officer.user_id,
            "hazard_assigned",
            "您辖区有新的隐患上报",
            f"{ctx.name}上报了隐患[{hazard_id}]：{data.title}",
            "hazard",
            hazard_id,
        )

    await db.commit()
    await db.refresh(hazard, _SUMMARY_REFRESH)
    return hazard_to_summary(hazard)


def _draw_annotated(original_rel: str, detections: list[dict], index: int) -> tuple[str, int]:
    """在原图副本上绘制标注图，返回 (相对路径, 字节数)。"""
    src = Path(settings.UPLOAD_DIR) / original_rel
    p = Path(original_rel)
    annotated_rel = str(p.with_name(f"{p.stem}_annotated_{index}.png"))
    out = Path(settings.UPLOAD_DIR) / annotated_rel
    annotate(src, detections, out)
    return annotated_rel, out.stat().st_size


async def _persist_ai_detections(
    db: AsyncSession,
    hazard_id: str,
    media_objs: list[tuple[int, HazardMedia]],
    detections_json: str,
) -> None:
    """把 AI 检测结果写入 hazard_detections，并为对应原图生成标注图。"""
    try:
        payload = json.loads(detections_json)
    except json.JSONDecodeError:
        raise BizError(40001, "detections_json 格式错误")
    if not isinstance(payload, list):
        raise BizError(40001, "detections_json 必须为 JSON 数组")

    by_image: dict[int, list[dict]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        index = item.get("image_index", 0)
        detections = item.get("detections") or []
        by_image[index] = detections if isinstance(detections, list) else []

    for index, media in media_objs:
        detections = by_image.get(index, [])
        if not detections:
            continue
        for det in detections:
            db.add(
                HazardDetection(
                    hazard_id=hazard_id,
                    media_id=media.media_id,
                    label=str(det.get("label", "")),
                    risk=str(det.get("risk", "")),
                    bbox_norm=json.dumps(det.get("bbox_norm") or []),
                    bbox_px=json.dumps(det["bbox_px"]) if det.get("bbox_px") else None,
                    color_bgr=json.dumps(det.get("color_bgr") or []),
                    conf=float(det.get("conf", 0.0)),
                    fix=det.get("fix"),
                    note=det.get("note"),
                )
            )
        annotated_rel, annotated_size = _draw_annotated(media.file_path, detections, index)
        db.add(
            HazardMedia(
                hazard_id=hazard_id,
                media_type="image_annotated",
                parent_media_id=media.media_id,
                file_path=annotated_rel,
                file_size=annotated_size,
                sort_order=index,
                context="report",
            )
        )


async def list_hazards(db: AsyncSession, ctx: AuthContext, filters: dict) -> dict:
    q = select(Hazard)
    # 普通用户仅查看自己上报的隐患；管理员可查看全部
    if ctx.role != "Admin":
        q = q.where(Hazard.reporter_id == ctx.user_id)

    if filters.get("status"):
        q = q.where(Hazard.status.in_([s for s in filters["status"].split(",") if s]))
    if filters.get("level"):
        q = q.where(Hazard.level.in_([s for s in filters["level"].split(",") if s]))
    if filters.get("category"):
        q = q.where(Hazard.category == filters["category"])
    if filters.get("project"):
        q = q.where(Hazard.project == filters["project"])
    if filters.get("keyword"):
        kw = f"%{filters['keyword']}%"
        q = q.where(
            or_(Hazard.title.like(kw), Hazard.description.like(kw), Hazard.hazard_id.like(kw))
        )
    if filters.get("date_from"):
        q = q.where(Hazard.created_at >= filters["date_from"])
    if filters.get("date_to"):
        q = q.where(Hazard.created_at <= filters["date_to"])

    sort_by = filters.get("sort_by") or "created_at"
    sort_order = filters.get("sort_order") or "desc"
    if sort_by == "urgency":
        order_col = case(
            (Hazard.level == "critical", 1),
            (Hazard.level == "major", 2),
            (Hazard.level == "minor", 3),
            else_=4,
        )
    else:
        order_col = Hazard.created_at
    q = q.order_by(order_col.desc() if sort_order == "desc" else order_col.asc())

    page = int(filters.get("page") or 1)
    page_size = int(filters.get("page_size") or 20)
    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    hazards = (
        (
            await db.execute(
                q.options(*_HAZARD_SUMMARY_LOADS)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [hazard_to_summary(h) for h in hazards],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_hazard(db: AsyncSession, ctx: AuthContext, hazard_id: str) -> dict:
    hazard = await _get_hazard(db, hazard_id)
    if not can_view_hazard(ctx, hazard):
        raise BizError(*ErrorCode.HAZARD_FORBIDDEN)
    return build_detail(hazard)


async def assign_hazard(
    db: AsyncSession,
    ctx: AuthContext,
    hazard_id: str,
    req: AssignRequest,
    attachments: list[UploadFile] | None = None,
) -> dict:
    hazard = await _get_hazard(db, hazard_id)
    # 普通用户可为自己的隐患派单
    if hazard.reporter_id != ctx.user_id:
        raise BizError(*ErrorCode.HAZARD_FORBIDDEN)
    if hazard.status != "pending":
        raise BizError(*ErrorCode.STATUS_NOT_ASSIGNABLE)

    deadline_date = datetime.date.fromisoformat(req.deadline[:10])
    today = datetime.date.today()
    if deadline_date < today:
        raise BizError(*ErrorCode.INVALID_DEADLINE)
    if hazard.level == "critical" and deadline_date > today + datetime.timedelta(days=7):
        raise BizError(*ErrorCode.CRITICAL_DEADLINE)

    assignee = await db.get(User, req.assignee_id)
    if assignee is None or not assignee.is_active:
        raise BizError(40001, "被指派人不存在或已禁用")

    attachment_rels = _save_attachments(attachments, hazard_id)
    db.add(
        HazardAssignment(
            hazard_id=hazard_id,
            assigner_id=ctx.user_id,
            assignee_id=req.assignee_id,
            requirements=req.requirements,
            deadline=req.deadline,
            priority=req.priority,
            attachments_json=json.dumps(attachment_rels, ensure_ascii=False),
        )
    )
    hazard.status = "processing"
    db.add(
        HazardTimeline(
            hazard_id=hazard_id,
            action_type="assigned",
            operator_id=ctx.user_id,
            note=f"指派{assignee.name}处理，截止{req.deadline}",
        )
    )
    notification_service.create_notification(
        db,
        req.assignee_id,
        "hazard_assigned",
        "您有一条新的隐患整改任务",
        f"隐患[{hazard_id}]已指派给您，整改要求：{req.requirements}",
        "hazard",
        hazard_id,
    )
    await db.commit()
    await db.refresh(hazard, _SUMMARY_REFRESH)
    return hazard_to_summary(hazard)


async def rectify_hazard(
    db: AsyncSession,
    ctx: AuthContext,
    hazard_id: str,
    req: RectifyRequest,
    files: list[UploadFile],
    attachments: list[UploadFile] | None = None,
) -> dict:
    hazard = await _get_hazard(db, hazard_id)
    if hazard.status not in ("processing", "rejected"):
        raise BizError(*ErrorCode.STATUS_NOT_RECTIFIABLE)
    if not is_assignee(ctx, hazard):
        raise BizError(*ErrorCode.NOT_ASSIGNEE)
    if len(req.measures.strip()) < 20:
        raise BizError(*ErrorCode.MEASURES_TOO_SHORT)
    if not files:
        raise BizError(*ErrorCode.NO_RECTIFY_IMAGES)
    if len(files) > settings.MAX_HAZARD_IMAGES:
        raise BizError(*ErrorCode.IMAGE_COUNT_EXCEEDED)

    rels = [save_upload(f, f"hazards/{hazard_id}")[0] for f in files[: settings.MAX_HAZARD_IMAGES]]
    attachment_rels = _save_attachments(attachments, hazard_id)
    round_num = (_latest(hazard.rectifications).round + 1) if hazard.rectifications else 1
    db.add(
        HazardRectification(
            hazard_id=hazard_id,
            assignee_id=ctx.user_id,
            measures=req.measures,
            images_json=json.dumps(rels, ensure_ascii=False),
            attachments_json=json.dumps(attachment_rels, ensure_ascii=False),
            completed_at=req.completed_at or now_cst(),
            round=round_num,
        )
    )
    hazard.status = "pending_review"
    db.add(
        HazardTimeline(
            hazard_id=hazard_id,
            action_type="rectified",
            operator_id=ctx.user_id,
            note=f"提交整改反馈（第{round_num}轮）",
        )
    )
    latest_assignment = _latest(hazard.assignments)
    if latest_assignment:
        notification_service.create_notification(
            db,
            latest_assignment.assigner_id,
            "rectification_submitted",
            "隐患整改反馈已提交",
            f"隐患[{hazard_id}]已由{ctx.name}提交整改反馈，请验收。",
            "hazard",
            hazard_id,
        )
    await db.commit()
    await db.refresh(hazard, _SUMMARY_REFRESH)
    return hazard_to_summary(hazard)


def _save_attachments(files: list[UploadFile] | None, hazard_id: str) -> list[str]:
    files = files or []
    if len(files) > settings.MAX_ATTACHMENT_COUNT:
        raise BizError(40001, f"附件数量超限（最多 {settings.MAX_ATTACHMENT_COUNT} 个）")
    rels = []
    for f in files:
        rel, _size = save_upload(f, f"hazards/{hazard_id}/attachments", kind="attachment")
        rels.append(rel)
    return rels


async def delete_hazard(db: AsyncSession, ctx: AuthContext, hazard_id: str) -> None:
    hazard = await _get_hazard(db, hazard_id, detail=False)
    # 普通用户可为自己的隐患派单
    if hazard.reporter_id != ctx.user_id:
        raise BizError(*ErrorCode.HAZARD_FORBIDDEN)
    await db.delete(hazard)
    await db.commit()


async def review_hazard(db: AsyncSession, ctx: AuthContext, hazard_id: str, req: ReviewRequest) -> dict:
    hazard = await _get_hazard(db, hazard_id)
    # 普通用户可为自己的隐患派单
    if hazard.reporter_id != ctx.user_id:
        raise BizError(*ErrorCode.HAZARD_FORBIDDEN)
    if hazard.status != "pending_review":
        raise BizError(*ErrorCode.STATUS_NOT_REVIEWABLE)
    if req.result == "approved":
        hazard.status = "closed"
    elif req.result == "rejected":
        if not req.comment or len(req.comment.strip()) < 10:
            raise BizError(*ErrorCode.REJECT_NEEDS_REASON)
        hazard.status = "rejected"
    else:
        raise BizError(40001, "参数校验失败")

    db.add(
        HazardReview(
            hazard_id=hazard_id,
            reviewer_id=ctx.user_id,
            result=req.result,
            comment=req.comment,
        )
    )
    db.add(
        HazardTimeline(
            hazard_id=hazard_id,
            action_type="reviewed",
            operator_id=ctx.user_id,
            note=f"验收{'通过' if req.result == 'approved' else '驳回'}"
            + (f"：{req.comment}" if req.result == "rejected" else ""),
        )
    )
    notification_service.create_notification(
        db,
        hazard.reporter_id,
        "review_result",
        "隐患验收结果",
        f"隐患[{hazard_id}]验收{'通过' if req.result == 'approved' else '被驳回'}。",
        "hazard",
        hazard_id,
    )
    await db.commit()
    await db.refresh(hazard, _SUMMARY_REFRESH)
    return hazard_to_summary(hazard)
