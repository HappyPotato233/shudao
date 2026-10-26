"""考试工坊 MVP 接口测试。"""
import json

from sqlalchemy import text

from app.core.config import settings

API = settings.API_V1_PREFIX


def _published_question_ids(client, headers):
    resp = client.get(
        f"{API}/exam/questions?status=published&page=1&page_size=20",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    return [item["question_id"] for item in items]


def _create_paper(client, headers, question_ids):
    # 新需求：所有试卷强制总分 100 分，按题目数量均分分值
    n = len(question_ids)
    score = round(100 / n, 1)
    resp = client.post(
        f"{API}/exam/papers",
        json={
            "title": "考试工坊测试卷",
            "description": "用于自动化测试",
            "mode": "manual",
            "questions": [
                {"question_id": qid, "score": score, "order": index}
                for index, qid in enumerate(question_ids, start=1)
            ],
            "config": {
                "duration": 60,
                "pass_score": 60,
                "total_score": 100,
                "shuffle_questions": False,
                "shuffle_options": False,
                "anti_cheat": True,
                "max_switch_count": 3,
                "allow_retake": True,
                "max_retake_count": 2,
                "start_time": "2026-08-16T00:00:00+08:00",
                "end_time": "2099-08-16T00:00:00+08:00",
            },
            "assignees": {"type": "user", "ids": ["U003"]},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["paper_id"]


def test_seeded_published_questions_are_available(client, auth_headers):
    headers = auth_headers("zhangsan")
    ids = _published_question_ids(client, headers)
    assert len(ids) >= 4


def test_safety_officer_can_review_pending_question(client, auth_headers, db):
    db.execute(
        text(
            "INSERT INTO questions "
            "(type, content, options_json, answer, explanation, score, difficulty, "
            "category_id, tags_json, status, source, created_by, created_at, updated_at) "
            "VALUES "
            "('single_choice', '测试题？', '{\"A\":\"是\",\"B\":\"否\"}', 'A', '解析', 2, "
            "'easy', 1, '[]', 'pending_review', 'ai_generated', 'U002', "
            "'2026-08-16T00:00:00+08:00', '2026-08-16T00:00:00+08:00')"
        )
    )
    db.commit()
    qid = db.scalar(
        text("SELECT MAX(question_id) FROM questions")
    )

    resp = client.post(
        f"{API}/exam/review/{qid}",
        json={"action": "approve", "comment": ""},
        headers=auth_headers("zhangsan"),
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "published"


def test_create_manual_paper_and_publish(client, auth_headers):
    headers = auth_headers("zhangsan")
    question_ids = _published_question_ids(client, headers)[:2]
    paper_id = _create_paper(client, headers, question_ids)

    detail = client.get(f"{API}/exam/papers/{paper_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "draft"

    published = client.post(
        f"{API}/exam/papers/{paper_id}/publish", headers=headers
    )
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"


def test_delete_question_used_by_paper_fails(client, auth_headers):
    zh = auth_headers("zhangsan")
    question_ids = _published_question_ids(client, zh)[:1]
    _create_paper(client, zh, question_ids)

    resp = client.delete(
        f"{API}/exam/questions/{question_ids[0]}", headers=zh
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40021


def test_ai_generate_creates_pending_review_questions(client, auth_headers, monkeypatch):
    from app.services import llm as llm_module
    from app.services import rag as rag_module

    generated = {
        "questions": [
            {
                "type": "single_choice",
                "difficulty": "easy",
                "content": "AI 生成的测试题？",
                "options": {"A": "正确", "B": "错误"},
                "answer": "A",
                "explanation": "这是 AI 生成的解析",
            }
        ]
    }
    async def _fake_stream(messages):
        yield json.dumps(generated, ensure_ascii=False)

    monkeypatch.setattr(llm_module.llm_service, "stream_chat", _fake_stream)

    async def _fake_retrieve(query, top_k=5, threshold=None, filters=None):
        return {"results": [], "no_evidence": True}

    monkeypatch.setattr(rag_module.rag_service, "retrieve", _fake_retrieve)

    resp = client.post(
        f"{API}/exam/ai/generate",
        json={
            "mode": "knowledge",
            "knowledge_points": ["高处作业"],
            "types": ["single_choice"],
            "count": 1,
            "difficulty": "easy",
            "use_knowledge_base": True,
        },
        headers=auth_headers("zhangsan"),
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["count"] == 1
    items = resp.json()["data"]["items"]
    assert items[0]["status"] == "pending_review"


def test_check_duplicate_finds_similar_question(client, auth_headers):
    zh = auth_headers("zhangsan")
    question_id = _published_question_ids(client, zh)[0]
    question = client.get(
        f"{API}/exam/questions/{question_id}", headers=zh
    ).json()["data"]

    resp = client.post(
        f"{API}/exam/questions/check-duplicate",
        json={"content": question["content"]},
        headers=zh,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["has_duplicate"] is True
    assert any(item["question_id"] == question_id for item in data["similar_questions"])


def test_ai_generate_document_mode_uses_document(client, auth_headers, monkeypatch):
    import app.services.exam_service as exam_module
    from app.services import llm as llm_module

    generated = {
        "questions": [
            {
                "type": "true_false",
                "difficulty": "easy",
                "content": "文档生成的测试题？",
                "answer": "正确",
                "explanation": "基于文档内容",
            }
        ]
    }
    async def _fake_stream(messages):
        yield json.dumps(generated, ensure_ascii=False)

    monkeypatch.setattr(llm_module.llm_service, "stream_chat", _fake_stream)

    async def _fake_read_document_text(document_id):
        return "这是用于出题的安全文档正文"

    monkeypatch.setattr(exam_module, "_read_document_text", _fake_read_document_text)

    resp = client.post(
        f"{API}/exam/ai/generate",
        json={
            "mode": "document",
            "document_id": 123,
            "types": ["true_false"],
            "count": 1,
            "difficulty": "easy",
            "use_knowledge_base": False,
        },
        headers=auth_headers("zhangsan"),
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["count"] == 1
    assert resp.json()["data"]["items"][0]["status"] == "pending_review"


def test_download_question_import_template(client, auth_headers):
    from io import BytesIO

    import openpyxl

    resp = client.get(
        f"{API}/exam/questions/template", headers=auth_headers("zhangsan")
    )

    assert resp.status_code == 200, resp.text
    assert (
        resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = openpyxl.load_workbook(BytesIO(resp.content))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    assert "题型" in headers
    assert "题干" in headers
    assert "正确答案" in headers
    assert "解析" in headers
    assert "分值" in headers
    assert "难度" in headers
    assert sheet.auto_filter.ref is not None
    assert sheet.auto_filter.ref.startswith("A1:")
    assert len(sheet.data_validations.dataValidation) >= 2


def test_import_questions_from_excel_with_row_errors(client, auth_headers, db):
    from io import BytesIO

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "题型",
            "题干",
            "选项A",
            "选项B",
            "选项C",
            "选项D",
            "正确答案",
            "解析",
            "分值",
            "难度",
            "分类ID",
            "标签",
        ]
    )
    sheet.append(
        [
            "single_choice",
            "Excel导入单选题",
            "正确",
            "错误",
            "",
            "",
            "A",
            "这是解析",
            2,
            "easy",
            1,
            "测试,导入",
        ]
    )
    sheet.append(
        [
            "single_choice",
            "错误答案题目",
            "正确",
            "错误",
            "",
            "",
            "X",
            "错误解析",
            2,
            "easy",
            1,
            "测试",
        ]
    )
    sheet.append(
        [
            "true_false",
            "Excel导入判断题",
            "",
            "",
            "",
            "",
            "正确",
            "判断题解析",
            2,
            "easy",
            1,
            "测试",
        ]
    )
    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    before = db.scalar(text("SELECT COUNT(*) FROM questions WHERE source = 'import'"))
    resp = client.post(
        f"{API}/exam/questions/import",
        files={"file": ("questions.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers("zhangsan"),
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 3
    assert data["success"] == 2
    assert data["failed"] == 1
    assert any("正确答案'X'不在选项范围内" in item["reason"] for item in data["errors"])
    after = db.scalar(text("SELECT COUNT(*) FROM questions WHERE source = 'import'"))
    assert after - before == 2


def test_build_generation_prompt_includes_basis_when_enabled():
    from types import SimpleNamespace

    from app.services.exam_service import _build_generation_prompt

    req = SimpleNamespace(
        types=["single_choice"],
        count=1,
        difficulty="easy",
        knowledge_points=["高处作业"],
        topic=None,
        include_basis=True,
    )
    prompt = _build_generation_prompt(req, "参考依据正文")
    assert "出题依据条款" in prompt

    req.include_basis = False
    prompt = _build_generation_prompt(req, "参考依据正文")
    assert "出题依据条款" not in prompt


def test_import_without_enter_bank_marks_paper_attachment(client, auth_headers):
    from io import BytesIO

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "题型", "题干", "选项A", "选项B", "选项C", "选项D",
            "正确答案", "解析", "分值", "难度", "分类ID", "标签",
        ]
    )
    sheet.append(
        [
            "single_choice", "不进入题库的题目", "正确", "错误", "", "",
            "A", "解析", 2, "easy", 1, "测试",
        ]
    )
    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    resp = client.post(
        f"{API}/exam/questions/import?enter_bank=false",
        files={
            "file": (
                "questions.xlsx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers("zhangsan"),
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["success"] == 1
    assert data["question_ids"]

    bank_ids = _published_question_ids(client, auth_headers("zhangsan"))
    assert data["question_ids"][0] not in bank_ids
