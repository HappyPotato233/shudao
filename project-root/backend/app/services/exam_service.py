"""考试工坊业务逻辑（async）。"""
from __future__ import annotations

import datetime
import difflib
import json
import random
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import AuthContext
from app.core.response import BizError, ErrorCode
from app.models.exam import (
    ExamPaper,
    PaperAssignee,
    PaperQuestion,
    Question,
    QuestionCategory,
)
from app.services.llm import llm_service
from app.services.rag import rag_service


ALLOWED_TYPES = {"single_choice", "multi_choice", "true_false", "essay"}
ALLOWED_DIFFICULTY = {"easy", "medium", "hard", "mixed"}
ESSAY_MAX_LENGTH = 2000


def _now_cst() -> str:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).isoformat(timespec="seconds")


def _parse_dt(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    return parsed


def _question_to_dict(q: Question) -> dict:
    return {
        "question_id": q.question_id,
        "type": q.type,
        "content": q.content,
        "options": json.loads(q.options_json or "{}") if q.options_json else None,
        "answer": q.answer,
        "explanation": q.explanation,
        "score": q.score,
        "difficulty": q.difficulty,
        "category_id": q.category_id,
        "tags": json.loads(q.tags_json or "[]"),
        "status": q.status,
        "source": q.source,
        "created_by": q.created_by,
        "created_at": q.created_at,
        "updated_at": q.updated_at,
    }


async def list_categories(db: AsyncSession) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(QuestionCategory).order_by(
                    QuestionCategory.level, QuestionCategory.sort_order, QuestionCategory.category_id
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "category_id": c.category_id,
            "name": c.name,
            "parent_id": c.parent_id,
            "level": c.level,
            "sort_order": c.sort_order,
        }
        for c in rows
    ]


async def list_questions(db: AsyncSession, filters: dict) -> dict:
    q = select(Question).where(
        Question.is_deleted == 0,
        Question.source != "paper_attachment",
    )
    if filters.get("type"):
        q = q.where(Question.type == filters["type"])
    if filters.get("difficulty"):
        q = q.where(Question.difficulty == filters["difficulty"])
    if filters.get("category_id"):
        q = q.where(Question.category_id == filters["category_id"])
    if filters.get("tag"):
        q = q.where(Question.tags_json.like(f"%{filters['tag']}%"))
    if filters.get("status"):
        q = q.where(Question.status == filters["status"])
    if filters.get("keyword"):
        q = q.where(Question.content.like(f"%{filters['keyword']}%"))

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    page = int(filters.get("page") or 1)
    page_size = int(filters.get("page_size") or 20)
    rows = (
        (
            await db.execute(
                q.order_by(Question.updated_at.desc(), Question.question_id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [_question_to_dict(item) for item in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


async def _get_question(db: AsyncSession, question_id: int) -> Question:
    question = await db.get(Question, question_id)
    if question is None or question.is_deleted:
        raise BizError(40403, "题目不存在", 404)
    return question


async def create_question(db: AsyncSession, ctx: AuthContext, data) -> dict:
    if data.type not in ALLOWED_TYPES:
        raise BizError(*ErrorCode.VALIDATION_FAILED)
    if data.type in {"single_choice", "multi_choice"} and not data.options:
        raise BizError(*ErrorCode.VALIDATION_FAILED)

    question = Question(
        type=data.type,
        content=data.content,
        options_json=json.dumps(data.options, ensure_ascii=False) if data.options else None,
        answer=data.answer,
        explanation=data.explanation,
        score=data.score,
        difficulty=data.difficulty,
        category_id=data.category_id,
        tags_json=json.dumps(data.tags or [], ensure_ascii=False),
        status="published" if ctx.role == "Admin" else "pending_review",
        source="manual",
        created_by=ctx.user_id,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return _question_to_dict(question)


async def update_question(db: AsyncSession, question_id: int, data) -> dict:
    question = await _get_question(db, question_id)
    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        if key == "options" and value is not None:
            question.options_json = json.dumps(value, ensure_ascii=False)
        elif key == "tags" and value is not None:
            question.tags_json = json.dumps(value, ensure_ascii=False)
        elif hasattr(question, key):
            setattr(question, key, value)
    question.updated_at = _now_cst()
    await db.commit()
    await db.refresh(question)
    return _question_to_dict(question)


async def delete_question(db: AsyncSession, question_id: int) -> None:
    question = await _get_question(db, question_id)
    used = (
        await db.execute(
            select(func.count()).select_from(PaperQuestion).where(
                PaperQuestion.question_id == question_id
            )
        )
    ).scalar() or 0
    if used:
        raise BizError(40021, "题目已使用，不可删除", 400)
    question.is_deleted = 1
    question.updated_at = _now_cst()
    await db.commit()


def _question_similarity(left: str, right: str) -> float:
    """计算题目文本相似度，取序列相似度和字符 Jaccard 的较大值。"""
    if not left or not right:
        return 0.0
    sequence_ratio = difflib.SequenceMatcher(None, left, right).ratio()
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return sequence_ratio
    jaccard = len(left_set & right_set) / len(union)
    return max(sequence_ratio, jaccard)


async def check_duplicate(db: AsyncSession, content: str) -> dict:
    """检测题库中与目标题干相似度超过 0.8 的题目。"""
    rows = (
        (await db.execute(select(Question).where(Question.is_deleted == 0)))
        .scalars()
        .all()
    )
    similar = []
    for question in rows:
        similarity = _question_similarity(content, question.content)
        if similarity > 0.8:
            similar.append(
                {
                    "question_id": question.question_id,
                    "content": question.content,
                    "similarity": round(similarity, 4),
                }
            )
    similar.sort(key=lambda item: item["similarity"], reverse=True)
    return {
        "has_duplicate": bool(similar),
        "similar_questions": similar[:5],
    }


async def _read_document_text(document_id: int) -> str:
    """从知识库读取文档正文，用于 document 出题模式。

    document_id 对应 kb_documents.row_id（源库 rowid 语义）。
    """
    from app.models import AsyncSessionLocal, KbDocument

    async with AsyncSessionLocal() as db:
        doc = await db.get(KbDocument, document_id)
    if doc is None:
        raise BizError(40406, "知识库文档不存在", 404)
    title = doc.title or ""
    text = doc.text or ""
    return f"{title}\n{text}".strip()


def _extract_json(text: str) -> dict | list:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    end = max(text.rfind("}"), text.rfind("]"))
    if start < 0 or end < 0 or end <= start:
        raise BizError(40205, "AI 返回内容无法解析", 502)
    return json.loads(text[start : end + 1])


def _build_generation_prompt(req, evidence: str) -> str:
    types = "、".join(req.types)
    difficulty = req.difficulty
    points = "、".join(req.knowledge_points) or req.topic or ""
    basis_instruction = ""
    if req.include_basis:
        basis_instruction = (
            "要求：explanation 字段需包含两段，用换行分隔。"
            "第一段为「答案解析」，第二段为「出题依据条款」，"
            "格式为「依据：法规名称+条款号」。"
        )
    return (
        "你是企业安全生产考试出题专家。请严格只输出 JSON，不要输出解释。"
        "JSON 结构为：{\"questions\":[{\"type\":\"single_choice|multi_choice|true_false|essay\","
        "\"difficulty\":\"easy|medium|hard\",\"content\":\"题干\","
        "\"options\":{\"A\":\"选项\"},\"answer\":\"正确答案\",\"explanation\":\"解析\"}]}。"
        f"题型：{types}；数量：{req.count}；难度：{difficulty}；知识点：{points}。"
        f"{basis_instruction}"
        f"参考依据：\n{evidence or '无可用依据，请基于通用安全知识生成。'}"
    )


async def _collect_evidence(req) -> str:
    """收集出题依据（RAG 检索 + 知识库文档读取）。"""
    evidence = ""
    if req.mode == "knowledge" and req.use_knowledge_base and req.knowledge_points:
        # retrieve 内部已把 embedding/BM25/重排等 CPU 密集操作下沉线程池
        retrieval = await rag_service.retrieve(" ".join(req.knowledge_points), top_k=5)
        evidence = "\n".join(
            f"{item.get('title','')} {item.get('locator','')} {item.get('text','')}"
            for item in retrieval.get("results", [])
        )
    elif req.mode == "document":
        if not req.document_id:
            raise BizError(40001, "文档出题必须提供 document_id", 400)
        evidence = await _read_document_text(req.document_id)
    elif req.mode == "free":
        if req.use_knowledge_base and req.topic:
            retrieval = await rag_service.retrieve(req.topic, top_k=5)
            evidence = "\n".join(
                f"{item.get('title','')} {item.get('locator','')} {item.get('text','')}"
                for item in retrieval.get("results", [])
            )
        else:
            evidence = req.topic or ""
    return evidence


async def _call_llm(prompt: str, db: AsyncSession) -> str:
    """调用 LLM 异步流式接口并拼接完整文本。"""
    cfg = await llm_service.resolve_config(db)
    if not cfg:
        raise BizError(*ErrorCode.AI_UNAVAILABLE)
    chunks = []
    async for token in llm_service.stream_chat(
        [
            {"role": "system", "content": "你是企业安全生产出题专家。"},
            {"role": "user", "content": prompt},
        ],
        cfg,
    ):
        chunks.append(token)
    return "".join(chunks)


async def generate_ai_questions(db: AsyncSession, ctx: AuthContext, req) -> dict:
    if not req.types:
        raise BizError(*ErrorCode.VALIDATION_FAILED)
    evidence = await _collect_evidence(req)
    prompt = _build_generation_prompt(req, evidence)
    text = await _call_llm(prompt, db)
    payload = _extract_json(text)
    generated = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(generated, list):
        raise BizError(40205, "AI 返回结构错误", 502)

    generation_id = "gen_" + uuid.uuid4().hex[:12]
    items = []
    for item in generated[: req.count]:
        q_type = item.get("type")
        content = item.get("content")
        answer = item.get("answer")
        if q_type not in ALLOWED_TYPES or not content or answer is None:
            continue
        options = item.get("options")
        if q_type in {"single_choice", "multi_choice"} and not options:
            continue
        question = Question(
            type=q_type,
            content=str(content),
            options_json=json.dumps(options, ensure_ascii=False) if options else None,
            answer=str(answer),
            explanation=str(item.get("explanation") or ""),
            score=2,
            difficulty=item.get("difficulty") if item.get("difficulty") in ALLOWED_DIFFICULTY else "easy",
            tags_json="[]",
            status="pending_review",
            source="ai_generated",
            ai_generation_id=generation_id,
            created_by=ctx.user_id,
        )
        db.add(question)
        items.append(question)

    await db.commit()
    return {
        "generation_id": generation_id,
        "count": len(items),
        "items": [_question_to_dict(q) for q in items],
    }


async def pending_review_questions(db: AsyncSession, page: int = 1, page_size: int = 20) -> dict:
    return await list_questions(db, {"status": "pending_review", "page": page, "page_size": page_size})


async def review_question(db: AsyncSession, ctx: AuthContext, question_id: int, req) -> dict:
    question = await _get_question(db, question_id)
    if req.action == "approve":
        question.status = "published"
    elif req.action == "reject":
        if not req.comment:
            raise BizError(40011, "驳回时必须填写原因", 400)
        question.status = "rejected"
        question.review_comment = req.comment
    elif req.action == "edit_approve":
        if not req.edited_content:
            raise BizError(40001, "编辑后通过必须提交题目内容", 400)
        question = update_question_from_payload(db, question, req.edited_content)
        question.status = "published"
    else:
        raise BizError(40001, "不支持的审核操作", 400)
    question.reviewed_by = ctx.user_id
    question.reviewed_at = _now_cst()
    question.updated_at = _now_cst()
    await db.commit()
    await db.refresh(question)
    return _question_to_dict(question)


def update_question_from_payload(db: AsyncSession, question: Question, payload: dict) -> Question:
    """纯内存更新题目字段（无 IO），由调用方 commit。"""
    for key, value in payload.items():
        if key == "options" and value is not None:
            question.options_json = json.dumps(value, ensure_ascii=False)
        elif key == "tags" and value is not None:
            question.tags_json = json.dumps(value, ensure_ascii=False)
        elif hasattr(question, key):
            setattr(question, key, value)
    return question


async def batch_review_questions(db: AsyncSession, ctx: AuthContext, req) -> int:
    count = 0
    for question_id in req.question_ids:
        await review_question(db, ctx, question_id, req)
        count += 1
    return count


def _paper_to_dict(paper: ExamPaper, detail: bool = False) -> dict:
    data = {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "description": paper.description,
        "mode": paper.mode,
        "total_score": paper.total_score,
        "pass_score": paper.pass_score,
        "duration": paper.duration,
        "shuffle_questions": bool(paper.shuffle_questions),
        "shuffle_options": bool(paper.shuffle_options),
        "anti_cheat": bool(paper.anti_cheat),
        "max_switch_count": paper.max_switch_count,
        "allow_retake": bool(paper.allow_retake),
        "max_retake_count": paper.max_retake_count,
        "start_time": paper.start_time,
        "end_time": paper.end_time,
        "status": paper.status,
        "created_by": paper.created_by,
        "created_at": paper.created_at,
        "updated_at": paper.updated_at,
        "exam_url": getattr(paper, "exam_url", None),
    }
    if detail and paper.mode == "auto" and paper.strategy_json:
        data["strategy"] = json.loads(paper.strategy_json)
    return data


async def list_papers(db: AsyncSession, page: int = 1, page_size: int = 20, status: str | None = None, keyword: str | None = None) -> dict:
    q = select(ExamPaper)
    if status:
        q = q.where(ExamPaper.status == status)
    if keyword:
        q = q.where(ExamPaper.title.like(f"%{keyword}%"))
    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    rows = (
        (
            await db.execute(
                q.order_by(ExamPaper.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [_paper_to_dict(p) for p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


async def get_paper(db: AsyncSession, paper_id: str) -> dict:
    paper = await db.get(ExamPaper, paper_id)
    if paper is None:
        raise BizError(40404, "试卷不存在", 404)
    return _paper_to_dict(paper, detail=True)


def _insert_paper_questions(db: AsyncSession, paper_id: str, rows: list[tuple[int, float, int]]) -> None:
    for question_id, score, order in rows:
        db.add(
            PaperQuestion(
                paper_id=paper_id,
                question_id=question_id,
                score=score,
                order=order,
            )
        )


def _insert_assignees(db: AsyncSession, paper_id: str, assignees) -> None:
    for assignee_id in assignees.ids or []:
        db.add(
            PaperAssignee(
                paper_id=paper_id,
                assignee_type=assignees.type,
                assignee_id=assignee_id,
            )
        )


async def create_paper(db: AsyncSession, ctx: AuthContext, data) -> dict:
    if data.mode not in {"manual", "auto"}:
        raise BizError(*ErrorCode.VALIDATION_FAILED)
    if data.config.duration not in {30, 60, 90}:
        raise BizError(40001, "考试时长仅支持 30/60/90 分钟", 400)
    if abs(data.config.total_score - 100.0) > 0.01:
        raise BizError(40001, f"试卷总分必须为100分，当前为{data.config.total_score}分", 400)

    paper_id = "paper_" + uuid.uuid4().hex[:12]
    paper = ExamPaper(
        paper_id=paper_id,
        title=data.title,
        description=data.description,
        mode=data.mode,
        total_score=data.config.total_score,
        pass_score=data.config.pass_score,
        duration=data.config.duration,
        shuffle_questions=1 if data.config.shuffle_questions else 0,
        shuffle_options=1 if data.config.shuffle_options else 0,
        anti_cheat=1 if data.config.anti_cheat else 0,
        max_switch_count=data.config.max_switch_count,
        allow_retake=1 if data.config.allow_retake else 0,
        max_retake_count=data.config.max_retake_count,
        start_time=data.config.start_time,
        end_time=data.config.end_time,
        status="draft",
        created_by=ctx.user_id,
    )
    db.add(paper)
    await db.flush()

    if data.mode == "auto":
        paper.strategy_json = json.dumps(data.strategy or {}, ensure_ascii=False)
        rows = await _select_auto_questions(db, data.strategy or {})
        _insert_paper_questions(db, paper_id, rows)
    else:
        if not data.questions:
            raise BizError(40001, "手动组卷至少选择一道题", 400)
        rows = []
        for item in data.questions:
            question = await db.get(Question, item.question_id)
            if question is None or question.is_deleted or question.status != "published":
                raise BizError(40001, f"题目 {item.question_id} 不可用", 400)
            rows.append((item.question_id, item.score, item.order))
        _insert_paper_questions(db, paper_id, rows)

    _insert_assignees(db, paper_id, data.assignees)
    # 生成考试链接
    exam_url = f"http://localhost:5173/exam/take/{paper_id}"
    paper.exam_url = exam_url
    await db.commit()
    return _paper_to_dict(paper)


async def _select_auto_questions(db: AsyncSession, strategy: dict) -> list[tuple[int, float, int]]:
    rows = []
    order = 1
    for item in strategy.get("distribution", []) or []:
        q_type = item.get("type")
        count = int(item.get("count") or 0)
        score = float(item.get("score_per") or 2)
        q = select(Question).where(
            Question.is_deleted == 0,
            Question.status == "published",
            Question.type == q_type,
        )
        candidates = (await db.execute(q)).scalars().all()
        random.shuffle(candidates)
        for question in candidates[:count]:
            rows.append((question.question_id, score, order))
            order += 1
    return rows


async def publish_paper(db: AsyncSession, paper_id: str) -> dict:
    paper = await db.get(ExamPaper, paper_id)
    if paper is None:
        raise BizError(40404, "试卷不存在", 404)
    if paper.status != "draft":
        raise BizError(40001, "仅草稿试卷可发布", 400)
    paper.status = "published"
    paper.exam_url = f"http://localhost:5173/exam/take/{paper_id}"
    paper.updated_at = _now_cst()
    await db.commit()
    return _paper_to_dict(paper)


async def end_paper(db: AsyncSession, paper_id: str) -> dict:
    paper = await db.get(ExamPaper, paper_id)
    if paper is None:
        raise BizError(40404, "试卷不存在", 404)
    paper.status = "ended"
    paper.updated_at = _now_cst()
    await db.commit()
    return _paper_to_dict(paper)
