"""考试工坊接口。"""
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import AuthContext, get_auth_context_async
from app.core.permissions import require_roles_async
from app.core.response import BizError, success
from app.models.base import get_db
from app.schemas.exam import (
    AiGenerateRequest,
    BatchReviewRequest,
    DuplicateCheckRequest,
    PaperCreate,
    QuestionCreate,
    QuestionReviewRequest,
    QuestionUpdate,
)
from app.services import exam_excel, exam_service

router = APIRouter(prefix="/exam", tags=["考试工坊"])


@router.get("/categories", summary="题目分类列表")
async def categories(
    _ctx: AuthContext = Depends(get_auth_context_async),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.list_categories(db))


@router.get("/questions", summary="题目列表")
async def list_questions(
    page: int = Query(1),
    page_size: int = Query(20),
    type: str | None = Query(None),
    difficulty: str | None = Query(None),
    category_id: int | None = Query(None),
    tag: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    filters = {
        "page": page,
        "page_size": page_size,
        "type": type,
        "difficulty": difficulty,
        "category_id": category_id,
        "tag": tag,
        "status": status,
        "keyword": keyword,
    }
    return success(await exam_service.list_questions(db, filters))


@router.post("/questions", summary="手动录入题目")
async def create_question(
    req: QuestionCreate,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.create_question(db, ctx, req))


@router.post("/questions/check-duplicate", summary="题目查重")
async def check_duplicate(
    req: DuplicateCheckRequest,
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.check_duplicate(db, req.content))


@router.get("/questions/template", summary="下载题目导入模板")
async def question_template(
    _ctx: AuthContext = Depends(require_roles_async("User")),
):
    content = await run_in_threadpool(exam_excel.build_question_template)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=question_import_template.xlsx"},
    )


@router.post("/questions/import", summary="批量导入题目")
async def import_questions(
    file: UploadFile = File(...),
    enter_bank: bool = Query(True),
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    return success(await exam_excel.import_questions_from_excel(db, ctx, content, enter_bank))


@router.get("/questions/{question_id}", summary="题目详情")
async def get_question(
    question_id: int,
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    question = await exam_service._get_question(db, question_id)
    return success(exam_service._question_to_dict(question))


@router.put("/questions/{question_id}", summary="编辑题目")
async def update_question(
    question_id: int,
    req: QuestionUpdate,
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.update_question(db, question_id, req))


@router.delete("/questions/{question_id}", summary="删除题目")
async def delete_question(
    question_id: int,
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    await exam_service.delete_question(db, question_id)
    return success(None, message="题目已删除")


@router.post("/ai/generate", summary="AI 出题")
async def ai_generate(
    req: AiGenerateRequest,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.generate_ai_questions(db, ctx, req))


@router.get("/review/pending", summary="待审核题目列表")
async def review_pending(
    page: int = Query(1),
    page_size: int = Query(20),
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.pending_review_questions(db, page, page_size))


@router.post("/review/batch", summary="批量审核")
async def review_batch(
    req: BatchReviewRequest,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    count = await exam_service.batch_review_questions(db, ctx, req)
    return success({"count": count})


@router.post("/review/{question_id}", summary="审核单题")
async def review_question(
    question_id: int,
    req: QuestionReviewRequest,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.review_question(db, ctx, question_id, req))


@router.get("/papers", summary="试卷列表")
async def list_papers(
    page: int = Query(1),
    page_size: int = Query(20),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.list_papers(db, page, page_size, status, keyword))


@router.post("/papers", summary="创建试卷")
async def create_paper(
    req: PaperCreate,
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.create_paper(db, ctx, req))


@router.put("/papers/{paper_id}/questions/{question_id}", summary="替换试卷题目")
async def replace_paper_question(
    paper_id: str,
    question_id: int,
    new_question_id: int = Form(...),
    ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    # 删除旧题目关联
    await db.execute(
        text("DELETE FROM paper_questions WHERE paper_id = :pid AND question_id = :qid"),
        {"pid": paper_id, "qid": question_id},
    )
    # 获取新题目分数
    q = (
        await db.execute(
            text("SELECT score FROM questions WHERE question_id = :qid"),
            {"qid": new_question_id},
        )
    ).fetchone()
    if not q:
        raise BizError(40404, "题目不存在")
    # 获取当前最大排序
    max_order = (
        await db.execute(
            text("SELECT MAX([order]) FROM paper_questions WHERE paper_id = :pid"),
            {"pid": paper_id},
        )
    ).scalar() or 0
    # 插入新题目
    await db.execute(
        text("INSERT INTO paper_questions (paper_id, question_id, score, [order]) VALUES (:pid, :qid, :s, :o)"),
        {"pid": paper_id, "qid": new_question_id, "s": q.score, "o": max_order + 1},
    )
    # 重新计算总分
    total = (
        await db.execute(
            text("SELECT COALESCE(SUM(score), 0) FROM paper_questions WHERE paper_id = :pid"),
            {"pid": paper_id},
        )
    ).scalar()
    if abs(total - 100.0) > 0.01:
        raise BizError(40001, f"替换后试卷总分必须为100分，当前为{total}分")
    await db.commit()
    return success(None)


@router.get("/papers/{paper_id}", summary="试卷详情")
async def get_paper(
    paper_id: str,
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.get_paper(db, paper_id))


@router.post("/papers/{paper_id}/publish", summary="发布试卷")
async def publish_paper(
    paper_id: str,
    _ctx: AuthContext = Depends(require_roles_async("User")),
    db: AsyncSession = Depends(get_db),
):
    return success(await exam_service.publish_paper(db, paper_id))
