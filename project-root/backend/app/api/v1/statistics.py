"""AI 问答满意度统计接口（Admin only）。
对齐 API.md 7.1 GET /statistics/ai-satisfaction：
- 总反馈数、点赞数、点踩数、点赞率
- 踩原因分布（inaccurate / incomplete / misunderstanding / off_topic / other）
- 附加：平均响应时间、总问答数、模型使用分布（来源 ai_audit_log）"""
import json
from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_roles_async
from app.core.response import BizError, success
from app.models.ai_orm import AiAuditLog, MessageFeedback
from app.models.base import get_db

router = APIRouter(prefix="/statistics", tags=["统计"])

DISLIKE_REASON_KEYS = ["inaccurate", "incomplete", "misunderstanding", "off_topic", "other"]


@router.get("/ai-satisfaction", summary="AI 问答满意度统计")
async def ai_satisfaction(
    days: int | None = Query(None, ge=1, le=365, description="统计最近 N 天，不传则统计全部"),
    date_from: str | None = Query(None, description="开始日期 YYYY-MM-DD，与 date_to 二选一或组合使用"),
    date_to: str | None = Query(None, description="结束日期 YYYY-MM-DD，与 date_from 二选一或组合使用"),
    ctx=Depends(require_roles_async("Admin")),
    db: AsyncSession = Depends(get_db),
):
    # 日期范围优先：给定 date_from / date_to 就按范围过滤，否则回退 days
    use_range = date_from is not None or date_to is not None
    range_conditions = []
    if use_range:
        for label, value in (("date_from", date_from), ("date_to", date_to)):
            if value is None:
                continue
            if not _is_valid_date(value):
                raise BizError(40001, f"{label} 格式非法，应为 YYYY-MM-DD")
        if date_from is not None:
            range_conditions.append(MessageFeedback.created_at >= f"{date_from}T00:00:00")
        if date_to is not None:
            range_conditions.append(MessageFeedback.created_at <= f"{date_to}T23:59:59")

    # 1. 反馈统计（message_feedback）
    feedback_stmt = select(MessageFeedback)
    if use_range:
        feedback_stmt = feedback_stmt.where(*range_conditions)
    elif days is not None:
        feedback_stmt = feedback_stmt.where(
            MessageFeedback.created_at >= _days_ago(days)
        )
    feedbacks = (await db.scalars(feedback_stmt)).all()

    total_feedback = len(feedbacks)
    like_count = sum(1 for f in feedbacks if f.rating == "like")
    dislike_count = sum(1 for f in feedbacks if f.rating == "dislike")
    like_rate = round(like_count / total_feedback, 4) if total_feedback else 0.0

    reason_counter: Counter[str] = Counter()
    for f in feedbacks:
        if f.rating != "dislike":
            continue
        try:
            reasons = json.loads(f.reasons_json or "[]")
        except (json.JSONDecodeError, TypeError):
            reasons = []
        if not isinstance(reasons, list):
            reasons = []
        for r in reasons:
            if r in DISLIKE_REASON_KEYS:
                reason_counter[r] += 1
    dislike_reasons = {
        key: reason_counter.get(key, 0) for key in DISLIKE_REASON_KEYS
    }

    # 2. 问答审计统计（ai_audit_log）
    audit_stmt = select(AiAuditLog)
    if use_range:
        audit_conditions = []
        if date_from is not None:
            audit_conditions.append(AiAuditLog.created_at >= f"{date_from}T00:00:00")
        if date_to is not None:
            audit_conditions.append(AiAuditLog.created_at <= f"{date_to}T23:59:59")
        audit_stmt = audit_stmt.where(*audit_conditions)
    elif days is not None:
        audit_stmt = audit_stmt.where(AiAuditLog.created_at >= _days_ago(days))
    audits = (await db.scalars(audit_stmt)).all()

    total_questions = len(audits)
    avg_response_time_ms = (
        round(sum(a.response_time_ms or 0 for a in audits) / total_questions, 1)
        if total_questions
        else 0
    )
    model_counter: Counter[str] = Counter()
    for a in audits:
        if a.model_used:
            model_counter[a.model_used] += 1
    model_usage = [
        {"model": model, "count": count}
        for model, count in model_counter.most_common()
    ]

    return success(
        {
            "total_feedback_count": total_feedback,
            "like_count": like_count,
            "dislike_count": dislike_count,
            "like_rate": like_rate,
            "dislike_reasons": dislike_reasons,
            "total_questions": total_questions,
            "avg_response_time_ms": avg_response_time_ms,
            "model_usage": model_usage,
        }
    )


def _is_valid_date(value: str) -> bool:
    """校验 YYYY-MM-DD 日期字符串。"""
    from datetime import datetime

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    return True


def _days_ago(days: int) -> str:
    """返回 N 天前的 ISO 时间字符串（本地时区），用于 created_at 文本比较。"""
    from datetime import datetime, timedelta

    dt = datetime.now() - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")
