"""模型评测：run 接口校验 + 指标计算 + vision/chat 评测服务"""
import asyncio
import json

import pytest
from sqlalchemy import text

from app.core.config import settings

API = settings.API_V1_PREFIX

# 固定测试时间戳：新表结构时间列不再有 DB 端默认值，造数需显式提供
_NOW = "2026-08-21T12:00:00+08:00"


@pytest.fixture(autouse=True)
def _cleanup_ai_tables(db):
    """清理本模块写入的 AI 测试表数据，避免 FK 残留阻塞后续 drop_all(users)。"""
    yield
    db.execute(text("DELETE FROM ai_test_results"))
    db.execute(text("DELETE FROM ai_test_items"))
    db.execute(text("DELETE FROM ai_test_sets"))
    db.execute(text("DELETE FROM ai_model_config"))
    db.commit()


# ---------- 造数工具 ----------

def _seed_model(db, model_type: str, name: str, base: str = "http://localhost:9", key: str = "sk-test") -> int:
    r = db.execute(text(
        "INSERT INTO ai_model_config (model_type, provider, model_name, api_base, api_key, is_active, created_at, updated_at) "
        "VALUES (:mt, 'test', :mn, :ab, :ak, 1, :cat, :uat)"),
        {"mt": model_type, "mn": name, "ab": base, "ak": key, "cat": _NOW, "uat": _NOW})
    db.commit()
    return r.lastrowid


def _seed_vision_set(db, ts_id: str) -> None:
    """2 张图：图1 真值2框 / 图2 真值1框，图片文件无需真实存在（调用会被 mock）。"""
    db.execute(text(
        "INSERT INTO ai_test_sets (test_set_id, name, model_type, image_count, created_by, created_at) "
        "VALUES (:id, '视觉测试集', 'vision', 2, 'U001', :cat)"), {"id": ts_id, "cat": _NOW})
    db.execute(text(
        "INSERT INTO ai_test_items (test_set_id, item_type, image_path, ground_truth, metadata_json) "
        "VALUES (:id, 'image', :p, :g, :m)"),
        [
            {"id": ts_id, "p": f"test_sets/{ts_id}/images/a.jpg",
             "g": json.dumps({"source": "加油站子集", "detections": [
                 {"class_id": 3, "name": "miehuoqi", "name_zh": "灭火器", "cx": 0.3, "cy": 0.3, "w": 0.2, "h": 0.2},
                 {"class_id": 4, "name": "zhuixingtong", "name_zh": "锥形桶", "cx": 0.7, "cy": 0.7, "w": 0.2, "h": 0.2},
             ]}), "m": "{}"},
            {"id": ts_id, "p": f"test_sets/{ts_id}/images/b.jpg",
             "g": json.dumps({"source": "隧道施工子集", "detections": [
                 {"class_id": 2, "name": "excavator", "name_zh": "挖掘机", "cx": 0.5, "cy": 0.5, "w": 0.4, "h": 0.4},
             ]}), "m": "{}"},
        ])
    db.commit()


def _seed_chat_set(db, ts_id: str) -> None:
    db.execute(text(
        "INSERT INTO ai_test_sets (test_set_id, name, model_type, question_count, created_by, created_at) "
        "VALUES (:id, '问答测试集', 'chat', 2, 'U001', :cat)"), {"id": ts_id, "cat": _NOW})
    db.execute(text(
        "INSERT INTO ai_test_items (test_set_id, item_type, ground_truth, expected_answer, metadata_json) "
        "VALUES (:id, 'question', :g, :e, :m)"),
        [
            {"id": ts_id, "g": json.dumps(["ev_1"]), "e": "灭火器应每月检查一次压力表。",
             "m": json.dumps({"query": "灭火器多久检查一次？"})},
            {"id": ts_id, "g": json.dumps(["ev_2", "ev_3"]), "e": "高处作业必须系挂安全带并设置警示标识。",
             "m": json.dumps({"query": "高处作业有什么要求？"})},
        ])
    db.commit()


# ---------- 纯函数：IoU 与检测框匹配 ----------

async def _run_eval(coro_fn):
    """在独立 event loop 中用 AsyncSession 执行评测协程（服务已 async 化）。"""
    from app.models.base import AsyncSessionLocal

    async with AsyncSessionLocal() as adb:
        return await coro_fn(adb)


def test_iou_identical_boxes():
    from app.services.model_eval_service import iou_xyxy
    assert iou_xyxy([0, 0, 1, 1], [0, 0, 1, 1]) == 1.0


def test_iou_disjoint_boxes():
    from app.services.model_eval_service import iou_xyxy
    assert iou_xyxy([0, 0, 0.5, 0.5], [0.5, 0.5, 1, 1]) == 0.0


def test_yolo_to_xyxy():
    from app.services.model_eval_service import yolo_to_xyxy
    assert yolo_to_xyxy(0.5, 0.5, 0.4, 0.4) == [0.3, 0.3, 0.7, 0.7]


def test_match_detections_counts_tp_fp_fn():
    from app.services.model_eval_service import match_detections
    gt = [{"class_id": 3, "cx": 0.3, "cy": 0.3, "w": 0.2, "h": 0.2},
          {"class_id": 4, "cx": 0.7, "cy": 0.7, "w": 0.2, "h": 0.2}]
    pred = [
        {"id": 3, "bbox_norm": [0.2, 0.2, 0.4, 0.4], "conf": 0.9},   # 命中 gt[0]
        {"id": 3, "bbox_norm": [0.0, 0.0, 0.2, 0.2], "conf": 0.8},   # 类别对但位置偏 → FP
        {"id": 9, "bbox_norm": [0.65, 0.65, 0.75, 0.75], "conf": 0.7},  # 类别错 → FP
    ]
    tp, fp, fn = match_detections(gt, pred, iou_thr=0.5)
    assert (tp, fp, fn) == (1, 2, 1)


def test_match_detections_edge_cases():
    from app.services.model_eval_service import match_detections
    gt_one = [{"class_id": 3, "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.2}]
    # 空预测 → 全 FN
    assert match_detections(gt_one, []) == (0, 0, 1)
    # 空真值 → 预测全 FP
    assert match_detections([], [{"id": 3, "bbox_norm": [0, 0, 1, 1], "conf": 0.9}]) == (0, 1, 0)
    # 双空 → 全零
    assert match_detections([], []) == (0, 0, 0)
    # 非法预测框（缺 bbox_norm）→ 按 FP 计
    assert match_detections(gt_one, [{"id": 3, "conf": 0.9}]) == (0, 1, 1)


def test_bigram_overlap_edge_cases():
    from app.services.model_eval_service import bigram_overlap
    assert bigram_overlap("", "答案") == 0.0
    assert bigram_overlap("完全一致的回答", "完全一致的回答") == 1.0
    assert bigram_overlap("abc", "xyz") == 0.0


def test_summarize_metrics():
    from app.services.model_eval_service import summarize_metrics
    m = summarize_metrics(total=10, tp=6, fp=2, fn=4, avg_latency_ms=100.0)
    assert m["precision_val"] == 0.75
    assert m["recall_val"] == 0.6
    assert abs(m["f1_score"] - 2 * 0.75 * 0.6 / (0.75 + 0.6)) < 1e-9
    assert m["accuracy"] == 6 / 12
    assert m["correct_items"] == 6


# ---------- vision 评测服务 ----------

def test_run_vision_eval_writes_result(db, monkeypatch):
    from app.services import model_eval_service as svc

    ts_id = "ts_vision_eval"
    _seed_vision_set(db, ts_id)
    mid = _seed_model(db, "vision", "test-v")
    cfg = {"id": mid, "model_type": "vision", "model_name": "test-v", "api_base": "http://x", "api_key": "sk"}

    # mock 视觉调用：图1 返回1个命中+1个误检，图2 返回1个命中（附带 token 用量）
    def fake_detect(client, model, image_path):
        return (
            [{"id": 3, "bbox_norm": [0.2, 0.2, 0.4, 0.4], "conf": 0.9},
             {"id": 3, "bbox_norm": [0.0, 0.0, 0.2, 0.2], "conf": 0.8}],
            {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        ) if image_path.name == "a.jpg" else (
            [{"id": 2, "bbox_norm": [0.3, 0.3, 0.7, 0.7], "conf": 0.9}],
            {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
        )

    monkeypatch.setattr(svc, "_detect_with_config", fake_detect)
    metrics = asyncio.run(_run_eval(
        lambda adb: svc.run_vision_eval(adb, ts_id, cfg, user_id="U001")
    ))

    assert metrics["total_items"] == 2
    assert metrics["correct_items"] == 2  # 两个命中
    row = db.execute(text("SELECT * FROM ai_test_results WHERE test_set_id = :t"), {"t": ts_id}).fetchone()
    assert row is not None
    detail = json.loads(row.detail_json)
    assert detail["status"] == "done"
    assert len(detail["items"]) == 2
    assert detail["tokens"]["total_tokens"] == 250  # token 用量累计入详情
    assert detail["duration_s"] >= 0


def test_run_vision_eval_empty_testset(db):
    from app.services.model_eval_service import run_vision_eval
    import pytest
    from app.core.response import BizError
    db.execute(text("INSERT INTO ai_test_sets (test_set_id, name, model_type, created_by, created_at) "
                    "VALUES ('ts_empty', '空集', 'vision', 'U001', :cat)"), {"cat": _NOW})
    db.commit()
    with pytest.raises(BizError):
        asyncio.run(_run_eval(
            lambda adb: run_vision_eval(adb, "ts_empty", {"id": 1, "model_type": "vision"}, user_id="U001")
        ))


def test_run_vision_eval_model_error_counts_as_fn(db, monkeypatch):
    """模型调用失败的图按全部漏检计（fn=真值数），不计 FP。"""
    from app.services import model_eval_service as svc

    ts_id = "ts_vision_err"
    _seed_vision_set(db, ts_id)  # 图1 真值2框，图2 真值1框
    mid = _seed_model(db, "vision", "err-v")
    cfg = {"id": mid, "model_type": "vision", "model_name": "err-v", "api_base": "http://x", "api_key": "sk"}

    def boom(client, model, image_path):
        raise RuntimeError("api down")

    monkeypatch.setattr(svc, "_detect_with_config", boom)
    metrics = asyncio.run(_run_eval(
        lambda adb: svc.run_vision_eval(adb, ts_id, cfg, user_id="U001")
    ))
    assert metrics["total_items"] == 2
    assert metrics["correct_items"] == 0
    assert metrics["precision_val"] == 0.0
    # 3 个真值全部漏检
    row = db.execute(text("SELECT detail_json FROM ai_test_results WHERE test_set_id = :t"), {"t": ts_id}).fetchone()
    detail = json.loads(row[0])
    assert all(it["fn"] == it["gt_count"] and it["fp"] == 0 and it["error"] for it in detail["items"])


# ---------- chat 评测服务 ----------

def test_run_chat_eval_writes_result(db, monkeypatch):
    from app.services import model_eval_service as svc

    ts_id = "ts_chat_eval"
    _seed_chat_set(db, ts_id)
    chat_mid = _seed_model(db, "chat", "test-c")
    emb_mid = _seed_model(db, "embedding", "test-e", base="/models/embed")
    rerank_mid = _seed_model(db, "rerank", "test-r", base="/models/rerank")
    cfg = {"id": chat_mid, "model_type": "chat", "model_name": "test-c", "api_base": "http://x", "api_key": "sk"}
    emb_cfg = {"id": emb_mid, "model_type": "embedding", "api_base": "/models/embed"}
    rerank_cfg = {"id": rerank_mid, "model_type": "rerank", "api_base": "/models/rerank"}

    # mock 检索（结构与真实 rag_service.retrieve 一轨：{"results": [...]}）：
    # query1 命中 ev_1（第2位），query2 命中 ev_2（第2位）
    async def fake_retrieve(self, query, top_k=5, threshold=None, filters=None):
        hit = "ev_1" if "灭火器" in query else "ev_2"
        return {"results": [{"evidence_id": "ev_x", "text": "噪声"}, {"evidence_id": hit, "text": "命中"}], "no_evidence": False}

    def fake_chat(client, model, query, contexts):
        return ("灭火器应每月检查一次压力表。" if "灭火器" in query else "高处作业必须系挂安全带。",
                {"prompt_tokens": 60, "completion_tokens": 30, "total_tokens": 90})

    monkeypatch.setattr(svc.RagService, "retrieve", fake_retrieve)
    monkeypatch.setattr(svc, "_chat_answer", fake_chat)

    metrics = asyncio.run(_run_eval(
        lambda adb: svc.run_chat_eval(adb, ts_id, cfg, emb_cfg, rerank_cfg, user_id="U001")
    ))

    assert metrics["total_items"] == 2
    assert metrics["correct_items"] == 2  # 两条回答均与期望答案高重合
    row = db.execute(text("SELECT * FROM ai_test_results WHERE test_set_id = :t"), {"t": ts_id}).fetchone()
    detail = json.loads(row.detail_json)
    assert detail["status"] == "done"
    assert detail["tokens"]["total_tokens"] == 180  # 2 题 × 90
    assert detail["items"][0]["recall_at_5"] == 1.0  # ev_1 在 top5
    assert detail["items"][1]["recall_at_5"] == 1.0


# ---------- run 接口校验（vision / chat 分接口） ----------

def _post_vision(client, headers, ts_id, body):
    return client.post(f"{API}/admin/test-sets/{ts_id}/run-vision", json=body, headers=headers)


def _post_chat(client, headers, ts_id, body):
    return client.post(f"{API}/admin/test-sets/{ts_id}/run-chat", json=body, headers=headers)


def test_run_vision_rejects_chat_model(client, auth_headers, db):
    """vision 接口只接受 vision 类型被测模型。"""
    _seed_vision_set(db, "ts_v1")
    chat_mid = _seed_model(db, "chat", "chat-m")
    resp = _post_vision(client, auth_headers("admin"), "ts_v1", {"model_config_id": chat_mid})
    assert resp.status_code == 400
    assert "类型" in resp.json()["message"]


def test_run_vision_rejects_chat_testset(client, auth_headers, db):
    """测试集类型与接口不匹配时应报错。"""
    _seed_chat_set(db, "ts_c0")
    vision_mid = _seed_model(db, "vision", "vision-m")
    resp = _post_vision(client, auth_headers("admin"), "ts_c0", {"model_config_id": vision_mid})
    assert resp.status_code == 400
    assert "chat" in resp.json()["message"]


def test_run_chat_requires_aux_models(client, auth_headers, db):
    """chat 接口缺少 embedding / crossencoder 属请求体不合法（全局校验错误返回 400）。"""
    _seed_chat_set(db, "ts_c1")
    chat_mid = _seed_model(db, "chat", "chat-m")
    resp = _post_chat(client, auth_headers("admin"), "ts_c1", {"model_config_id": chat_mid})
    assert resp.status_code == 400


def test_run_chat_rejects_vision_testset(client, auth_headers, db):
    """vision 测试集不能走 chat 接口。"""
    _seed_vision_set(db, "ts_v5")
    chat_mid = _seed_model(db, "chat", "chat-m")
    emb_mid = _seed_model(db, "embedding", "emb-m", base="/models/e")
    rerank_mid = _seed_model(db, "rerank", "rerank-m", base="/models/r")
    resp = _post_chat(client, auth_headers("admin"), "ts_v5", {
        "model_config_id": chat_mid,
        "embedding_model_id": emb_mid,
        "crossencoder_model_id": rerank_mid,
    })
    assert resp.status_code == 400
    assert "vision" in resp.json()["message"]


def test_run_chat_rejects_wrong_aux_type(client, auth_headers, db):
    """embedding 位置传入 rerank 模型应被类型校验拦截。"""
    _seed_chat_set(db, "ts_c2")
    chat_mid = _seed_model(db, "chat", "chat-m")
    rerank_mid = _seed_model(db, "rerank", "rerank-m", base="/models/r")
    resp = _post_chat(client, auth_headers("admin"), "ts_c2", {
        "model_config_id": chat_mid,
        "embedding_model_id": rerank_mid,
        "crossencoder_model_id": rerank_mid,
    })
    assert resp.status_code == 400


def test_run_unknown_testset(client, auth_headers, db):
    mid = _seed_model(db, "vision", "vision-m")
    resp = _post_vision(client, auth_headers("admin"), "ts_not_exist", {"model_config_id": mid})
    assert resp.status_code == 404


def test_run_returns_result_id(client, auth_headers, db, monkeypatch):
    from app.services import model_eval_service as svc
    _seed_vision_set(db, "ts_v3")
    vision_mid = _seed_model(db, "vision", "vision-m")

    async def _fake_start(*args, **kwargs):
        return "res_mock_123"

    monkeypatch.setattr(svc, "start_eval_task", _fake_start)
    resp = _post_vision(client, auth_headers("admin"), "ts_v3", {"model_config_id": vision_mid})
    assert resp.status_code == 200
    assert resp.json()["data"]["result_id"] == "res_mock_123"


def test_run_chat_returns_result_id(client, auth_headers, db, monkeypatch):
    from app.services import model_eval_service as svc
    _seed_chat_set(db, "ts_c3")
    chat_mid = _seed_model(db, "chat", "chat-m")
    emb_mid = _seed_model(db, "embedding", "emb-m", base="/models/e")
    rerank_mid = _seed_model(db, "rerank", "rerank-m", base="/models/r")

    async def _fake_start(*args, **kwargs):
        return "res_chat_456"

    monkeypatch.setattr(svc, "start_eval_task", _fake_start)
    resp = _post_chat(client, auth_headers("admin"), "ts_c3", {
        "model_config_id": chat_mid,
        "embedding_model_id": emb_mid,
        "crossencoder_model_id": rerank_mid,
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["result_id"] == "res_chat_456"


def test_run_non_admin_forbidden(client, auth_headers, db):
    _seed_vision_set(db, "ts_v4")
    mid = _seed_model(db, "vision", "vision-m")
    resp = _post_vision(client, auth_headers("zhangsan"), "ts_v4", {"model_config_id": mid})
    assert resp.status_code == 403


# ---------- regenerate 已移除 ----------

def test_regenerate_endpoint_removed(client, auth_headers):
    # regenerate 处理器已删除：该路径现仅匹配 DELETE /test-sets/{id} 路由 → 405，或无匹配 → 404
    resp = client.post(f"{API}/admin/test-sets/regenerate",
                       data={"count": 10}, headers=auth_headers("admin"))
    assert resp.status_code in (404, 405)
