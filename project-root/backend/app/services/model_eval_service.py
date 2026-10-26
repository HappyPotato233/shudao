"""模型评测服务

支持两类评测：
- vision：逐图调用被测视觉模型，与 YOLO 真值按类别+IoU 匹配，计算 precision/recall/F1
- chat：逐题用指定 embedding+crossencoder 构造 RAG 检索，计算 recall@5/MRR，
  并调用被测 chat 模型生成回答，与期望答案按字符 bigram 重合率判定正确性

评测结果统一写入 ai_test_results；长耗时评测通过 start_eval_task 在主事件循环上
create_task 后台异步执行（评测与请求共享同一 loop，避免跨 loop 连接池问题）。

2026-08-23 P4：DB 访问全量 async 化（AsyncSession），模型网络调用经
asyncio.to_thread 下沉线程池。
2026-08-30：评测后台执行从"线程+自建 event loop"改为主循环 create_task
（asyncpg 连接绑定创建时的 loop，跨 loop 取池中连接会静默崩溃）。
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.response import BizError
from app.services.annotator import encode_image_data_url, extract_json_array, imread_unicode
from app.services.embedding import EmbeddingService, RerankService
from app.services.rag import RagService
from app.services.vision import SYSTEM_PROMPT

# 回答与期望答案的 bigram 重合率阈值（≥ 判定该题回答正确）
ANSWER_SIM_THRESHOLD = 0.25
# 检测框匹配的 IoU 阈值
IOU_THRESHOLD = 0.5

# 评测专用物体检测 prompt：与 YOLO 真值语义对齐（全量物体框，非隐患识别）。
# 不能直接复用生产 SYSTEM_PROMPT——其"无隐患输出[]"语义会让模型在正常
# 场景图上返回空数组，导致 recall 被错误压低。
_EVAL_DETECT_PROMPT_PREFIX = (
    "你是施工场景物体检测专家。\n"
    "任务规则：\n"
    "1. 检测图中所有属于类别列表的物体，无论物体状态是否正常，全部输出。\n"
    "2. 参考物体类别列表：\n"
)

# 从生产 SYSTEM_PROMPT 截取类别列表段（从首个"【"场景行到 risk 规则之前），
# 拼接评测专用 prompt，保证类别 ID 与 YOLO 真值口径一致且随生产列表同步更新
_EVAL_DETECT_PROMPT = _EVAL_DETECT_PROMPT_PREFIX + SYSTEM_PROMPT[
    SYSTEM_PROMPT.index("【"):SYSTEM_PROMPT.index("3. risk风险等级判定规则")
] + (
    "3. 输出严格JSON数组，禁止任何解释、说明、markdown。图中没有类别列表中的物体才输出[]。\n"
    "数组每一个对象字段：\n"
    "id：整数，物体对应的类别ID；\n"
    "label：字符串，物体名称；\n"
    "conf：0-1浮点数，检测置信度；\n"
    "bbox_norm：[x1,y1,x2,y2]，归一化坐标0-1，x1<x2,y1<y2；\n"
)


# ---------- 纯函数：几何与指标 ----------

def iou_xyxy(a: list[float], b: list[float]) -> float:
    """两个 [x1,y1,x2,y2] 归一化框的 IoU。"""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def yolo_to_xyxy(cx: float, cy: float, w: float, h: float) -> list[float]:
    """YOLO 中心点坐标转角点坐标（均归一化）。"""
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def match_detections(
    gt_dets: list[dict],
    pred_dets: list[dict],
    iou_thr: float = IOU_THRESHOLD,
) -> tuple[int, int, int]:
    """按类别一致 + IoU≥阈值贪心匹配，返回 (TP, FP, FN)。

    gt 条目含 class_id/cx/cy/w/h；pred 条目含 id/bbox_norm(xyxy)。
    """
    gt_boxes = [(d["class_id"], yolo_to_xyxy(d["cx"], d["cy"], d["w"], d["h"])) for d in gt_dets]
    preds = sorted(pred_dets, key=lambda p: float(p.get("conf", 0)), reverse=True)
    matched_gt: set[int] = set()
    tp = fp = 0
    for p in preds:
        box = p.get("bbox_norm")
        cid = p.get("id")
        if not box or len(box) != 4 or cid is None:
            fp += 1  # 无法解析的预测按误检计
            continue
        best_iou, best_idx = 0.0, -1
        for gi, (gcid, gbox) in enumerate(gt_boxes):
            if gi in matched_gt or gcid != int(cid):
                continue
            cur = iou_xyxy(box, gbox)
            if cur > best_iou:
                best_iou, best_idx = cur, gi
        if best_idx >= 0 and best_iou >= iou_thr:
            matched_gt.add(best_idx)
            tp += 1
        else:
            fp += 1
    fn = len(gt_boxes) - len(matched_gt)
    return tp, fp, fn


def summarize_metrics(total: int, tp: int, fp: int, fn: int, avg_latency_ms: float) -> dict:
    """汇总为 ai_test_results 字段（vision：accuracy=TP/(TP+FP+FN)）。"""
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    denom = tp + fp + fn
    return {
        "total_items": total,
        "correct_items": tp,
        "accuracy": tp / denom if denom else 0.0,
        "precision_val": precision,
        "recall_val": recall,
        "f1_score": f1,
        "avg_latency_ms": avg_latency_ms,
    }


def bigram_overlap(answer: str, expected: str) -> float:
    """回答与期望答案的字符 bigram 集合 Jaccard 相似度。"""
    def grams(s: str) -> set[str]:
        s = (s or "").replace("\n", "").replace(" ", "")
        return {s[i:i + 2] for i in range(len(s) - 1)}
    ga, ge = grams(answer), grams(expected)
    if not ga or not ge:
        return 0.0
    return len(ga & ge) / len(ga | ge)


# ---------- 模型调用 ----------

def _make_client(cfg: dict) -> OpenAI:
    """评测专用客户端：短超时 + 1 次重试，避免错误端点导致单条长时间挂起。"""
    return OpenAI(
        api_key=cfg.get("api_key") or "none",
        base_url=cfg["api_base"],
        timeout=60,
        max_retries=1,
    )


def _usage(resp) -> dict:
    """从 OpenAI 兼容响应中安全提取 token 用量。"""
    u = getattr(resp, "usage", None)
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
        "total_tokens": getattr(u, "total_tokens", 0) or 0,
    }


def _detect_with_config(client: OpenAI, model: str, image_path: Path) -> tuple[list[dict], dict]:
    """用被测 vision 配置识别单图（评测专用物体检测 prompt），返回 (检测数组, token 用量)。"""
    h, w = imread_unicode(image_path).shape[:2]
    resp = client.chat.completions.create(
        model=model,
        messages=[
            # 评测用全量物体检测语义，与 YOLO 真值对齐；非生产的隐患识别语义
            {"role": "system", "content": _EVAL_DETECT_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": f"原图像素尺寸: width={w}, height={h}。请据此填写 bbox_norm。"},
                {"type": "image_url", "image_url": {"url": encode_image_data_url(image_path)}},
            ]},
        ],
        temperature=0.2,
        # qwen3.x 思考模型关闭思考链，避免单图评测耗时 90s+ 触发超时
        extra_body={"enable_thinking": False},
    )
    return extract_json_array(resp.choices[0].message.content or "[]"), _usage(resp)


def _chat_answer(client: OpenAI, model: str, query: str, contexts: list[str]) -> tuple[str, dict]:
    """基于检索上下文让被测 chat 模型生成回答，返回 (回答, token 用量)。"""
    context_text = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts)) or "（无检索结果）"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是安全生产知识问答助手，仅依据提供的参考资料回答，简洁准确。"},
            {"role": "user", "content": f"参考资料：\n{context_text}\n\n问题：{query}"},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content or "", _usage(resp)


def build_rag_service(emb_cfg: dict | None, rerank_cfg: dict | None) -> RagService:
    """按评测指定的模型配置构造独立 RAG 实例（不影响线上 rag_service 单例）。"""
    embedder = EmbeddingService(model_dir=emb_cfg["api_base"]) if emb_cfg else None
    reranker = RerankService(model_dir=rerank_cfg["api_base"]) if rerank_cfg else None
    return RagService(embedder=embedder, reranker=reranker)


# ---------- 结果写库 ----------

async def _insert_result(db: AsyncSession, test_set_id: str, cfg: dict, user_id: str, metrics: dict, detail: dict) -> str:
    """写入一条评测结果行（参数化 SQL），返回 result_id。"""
    from app.models.mixins import now_cst
    result_id = f"res_{uuid.uuid4().hex[:12]}"
    await db.execute(text(
        "INSERT INTO ai_test_results (result_id, test_set_id, model_config_id, model_type, "
        "total_items, correct_items, accuracy, precision_val, recall_val, f1_score, avg_latency_ms, "
        "detail_json, executed_by, executed_at) "
        "VALUES (:rid, :ts, :mid, :mt, :total, :correct, :acc, :prec, :rec, :f1, :lat, :detail, :uid, :eat)"),
        {"rid": result_id, "ts": test_set_id, "mid": cfg["id"], "mt": cfg["model_type"],
         "total": metrics["total_items"], "correct": metrics["correct_items"],
         "acc": metrics["accuracy"], "prec": metrics["precision_val"], "rec": metrics["recall_val"],
         "f1": metrics["f1_score"], "lat": metrics["avg_latency_ms"],
         "detail": json.dumps(detail, ensure_ascii=False), "uid": user_id, "eat": now_cst()})
    await db.commit()
    return result_id


async def _load_items(db: AsyncSession, test_set_id: str, item_type: str) -> list:
    rows = (await db.execute(text(
        "SELECT id, image_path, ground_truth, expected_answer, metadata_json FROM ai_test_items "
        "WHERE test_set_id = :id AND item_type = :it ORDER BY id"),
        {"id": test_set_id, "it": item_type})).fetchall()
    if not rows:
        raise BizError(40004, f"测试集没有可评测的 {item_type} 条目")
    return rows


# ---------- vision 评测 ----------

async def _eval_vision(db: AsyncSession, test_set_id: str, cfg: dict) -> tuple[dict, dict]:
    """逐图评测，返回 (指标, 逐条详情)。不写结果表。"""
    rows = await _load_items(db, test_set_id, "image")
    client = _make_client(cfg)
    started = time.perf_counter()
    tp = fp = fn = 0
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    details: list[dict] = []
    latencies: list[float] = []
    for r in rows:
        gt = json.loads(r.ground_truth or "{}")
        gt_dets = gt.get("detections", [])
        image_path = Path(settings.UPLOAD_DIR) / r.image_path
        start = time.perf_counter()
        try:
            # 模型调用为同步网络请求，放线程池
            preds, usage = await asyncio.to_thread(
                _detect_with_config, client, cfg["model_name"], image_path
            )
            for k in tokens:
                tokens[k] += usage.get(k, 0)
            item_tp, item_fp, item_fn = match_detections(gt_dets, preds)
            error = None
        except Exception as exc:  # 单条失败不中断整体评测；失败图按全部漏检计（fn=真值数）
            preds, item_tp, item_fp, item_fn, error = [], 0, 0, len(gt_dets), str(exc)[:200]
        latencies.append((time.perf_counter() - start) * 1000)
        tp += item_tp
        fp += item_fp
        fn += item_fn
        details.append({
            "item_id": r.id,
            "image_path": r.image_path,
            "gt_count": len(gt_dets),
            "pred_count": len(preds),
            "tp": item_tp, "fp": item_fp, "fn": item_fn,
            "error": error,
        })
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    metrics = summarize_metrics(len(rows), tp, fp, fn, avg_latency)
    detail = {
        "status": "done",
        "duration_s": round(time.perf_counter() - started, 1),
        "tokens": tokens,
        "tp": tp, "fp": fp, "fn": fn,
        "items": details,
    }
    return metrics, detail


async def run_vision_eval(db: AsyncSession, test_set_id: str, cfg: dict, user_id: str) -> dict:
    """执行 vision 评测并写入 ai_test_results，返回指标。"""
    metrics, detail = await _eval_vision(db, test_set_id, cfg)
    await _insert_result(db, test_set_id, cfg, user_id, metrics, detail)
    return metrics


# ---------- chat 评测 ----------

async def _eval_chat(db: AsyncSession, test_set_id: str, cfg: dict, emb_cfg: dict | None, rerank_cfg: dict | None) -> tuple[dict, dict]:
    """逐题评测检索与回答，返回 (指标, 逐条详情)。不写结果表。"""
    rows = await _load_items(db, test_set_id, "question")
    rag = build_rag_service(emb_cfg, rerank_cfg)
    client = _make_client(cfg)
    started = time.perf_counter()
    correct = 0
    recall_sum = 0.0
    mrr_sum = 0.0
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    details: list[dict] = []
    latencies: list[float] = []
    for r in rows:
        meta = json.loads(r.metadata_json or "{}")
        query = meta.get("query") or ""
        gt_ids = set(json.loads(r.ground_truth or "[]"))
        start = time.perf_counter()
        error = None
        recall5, rr, similarity = 0.0, 0.0, 0.0
        try:
            retrieved = await rag.retrieve(query, top_k=5)
            results = retrieved.get("results", [])
            hit_ids = [it.get("evidence_id") or it.get("id") for it in results[:5]]
            recall5 = 1.0 if gt_ids & set(hit_ids) else 0.0
            for rank, hid in enumerate(hit_ids, start=1):
                if hid in gt_ids:
                    rr = 1.0 / rank
                    break
            contexts = [it.get("text") or "" for it in results]
            # 模型调用为同步网络请求，放线程池
            answer, usage = await asyncio.to_thread(
                _chat_answer, client, cfg["model_name"], query, contexts
            )
            for k in tokens:
                tokens[k] += usage.get(k, 0)
            similarity = bigram_overlap(answer, r.expected_answer or "")
        except Exception as exc:  # 单条失败不中断整体评测
            error = str(exc)[:200]
        latencies.append((time.perf_counter() - start) * 1000)
        is_correct = similarity >= ANSWER_SIM_THRESHOLD
        if is_correct:
            correct += 1
        recall_sum += recall5
        mrr_sum += rr
        details.append({
            "item_id": r.id,
            "query": query,
            "recall_at_5": recall5,
            "reciprocal_rank": rr,
            "similarity": round(similarity, 4),
            "correct": is_correct,
            "error": error,
        })
    total = len(rows)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    metrics = {
        "total_items": total,
        "correct_items": correct,
        "accuracy": correct / total if total else 0.0,
        "precision_val": None,
        "recall_val": recall_sum / total if total else 0.0,  # 检索 recall@5 均值
        "f1_score": None,
        "avg_latency_ms": avg_latency,
    }
    detail = {
        "status": "done",
        "duration_s": round(time.perf_counter() - started, 1),
        "tokens": tokens,
        "mrr": round(mrr_sum / total, 4) if total else 0.0,
        "items": details,
    }
    return metrics, detail


async def run_chat_eval(db: AsyncSession, test_set_id: str, cfg: dict, emb_cfg: dict | None, rerank_cfg: dict | None, user_id: str) -> dict:
    """执行 chat 评测并写入 ai_test_results，返回指标。"""
    metrics, detail = await _eval_chat(db, test_set_id, cfg, emb_cfg, rerank_cfg)
    await _insert_result(db, test_set_id, cfg, user_id, metrics, detail)
    return metrics


# ---------- 异步任务 ----------

# 评测后台任务的强引用集合：防止 create_task 的 task 被 GC 回收
_EVAL_TASKS: set = set()


async def start_eval_task(test_set_id: str, cfg: dict, emb_cfg: dict | None, rerank_cfg: dict | None, user_id: str) -> str:
    """创建 running 状态的结果行并在主事件循环上调度后台评测任务，立即返回 result_id。

    注意：不能用 threading.Thread + asyncio.run 自建事件循环——asyncpg 连接与
    创建它的 loop 绑定，跨 loop 从共享连接池取连接会抛
    "attached to a different loop"，导致评测线程静默死亡、状态卡在 running。
    """
    from app.models.base import AsyncSessionLocal

    metrics = {k: 0 for k in ("total_items", "correct_items", "accuracy", "precision_val", "recall_val", "f1_score", "avg_latency_ms")}
    # 初始行用独立短生命周期 Session 写入（不依赖请求级 Session，任务调度后请求即返回）
    async with AsyncSessionLocal() as init_session:
        result_id = await _insert_result(init_session, test_set_id, cfg, user_id, metrics, {"status": "running"})

    async def _worker():
        async with AsyncSessionLocal() as session:
            result_metrics = metrics  # 初始零值：eval 失败时按零指标回写 failed 状态
            try:
                if cfg["model_type"] == "vision":
                    result_metrics, detail = await _eval_vision(session, test_set_id, cfg)
                else:
                    result_metrics, detail = await _eval_chat(session, test_set_id, cfg, emb_cfg, rerank_cfg)
                await _update_result(session, result_id, result_metrics, detail)
            except Exception as exc:
                await _update_result(session, result_id, result_metrics,
                                     {"status": "failed", "error": str(exc)[:500]})

    # 在当前（主）事件循环上调度后台任务：与请求处理共享同一 loop，
    # 连接池天然同循环；评测内的同步模型调用已用 asyncio.to_thread 下沉线程池
    task = asyncio.get_running_loop().create_task(_worker())
    _EVAL_TASKS.add(task)
    task.add_done_callback(_EVAL_TASKS.discard)
    return result_id


async def _update_result(session: AsyncSession, result_id: str, metrics: dict, detail: dict) -> None:
    """评测完成后回写指标与详情。"""
    await session.execute(text(
        "UPDATE ai_test_results SET total_items = :total, correct_items = :correct, accuracy = :acc, "
        "precision_val = :prec, recall_val = :rec, f1_score = :f1, avg_latency_ms = :lat, "
        "detail_json = :detail WHERE result_id = :rid"),
        {"total": metrics["total_items"], "correct": metrics["correct_items"], "acc": metrics["accuracy"],
         "prec": metrics["precision_val"], "rec": metrics["recall_val"], "f1": metrics["f1_score"],
         "lat": metrics["avg_latency_ms"], "detail": json.dumps(detail, ensure_ascii=False), "rid": result_id})
    await session.commit()
