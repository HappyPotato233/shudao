"""AI 智能助手测试集构建与检索策略评估脚本

从知识库抽取 200 条去重测试数据（重复率 ≤5%）：
- 120 条 query-1chunk（答案在单个证据块）
- 50 条 query-2chunk（答案跨 2 个证据块）
- 30 条 query-3chunk（答案跨 3 个证据块）

然后对比不同检索策略（向量/BM25/混合）的检索效果，
每条测试记录实时输出到控制台，最终生成测试报告到 test_report/ 目录。
"""
import json
import random
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime

# 路径配置
SCRIPT_DIR = Path(__file__).resolve().parent                  # test/
PROJECT_ROOT = SCRIPT_DIR / "project-root"                     # test/project-root/
KB_PATH = PROJECT_ROOT / "database" / "transport_safety_kb.sqlite3"
REPORT_DIR = SCRIPT_DIR / "test_report"                        # test/test_report/
REPORT_PATH = REPORT_DIR / "rag_retrieval_eval_report.md"
TESTSET_JSON_PATH = REPORT_DIR / "ai_testset_200.json"
DETAILED_LOG_PATH = REPORT_DIR / "test_detail_log.json"        # 每条测试的详细记录

REPORT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)


# ============ 1. 读取知识库证据块 ============
def load_evidence():
    con = sqlite3.connect(f"file:{KB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT e.evidence_id, e.document_id, e.source_uri, e.title, e.locator,
               e.text, e.content_hash, e.authority_level,
               (SELECT k2.topic FROM knowledge_entries k2
                WHERE k2.document_id = e.document_id AND k2.invalidated = 0
                ORDER BY k2.rowid LIMIT 1) AS topic,
               d.document_type,
               CASE
                   WHEN d.jurisdiction = '国家' THEN '国家规范'
                   WHEN d.jurisdiction LIKE '%公司%' OR d.jurisdiction LIKE '%集团%'
                        OR d.jurisdiction LIKE '%企业%' THEN '企业规范'
                   ELSE '地方规范'
               END AS standard_level
        FROM evidence_units e
        LEFT JOIN documents d ON d.document_id = e.document_id
        WHERE e.text IS NOT NULL AND trim(e.text) != ''
          AND e.content_hash IS NOT NULL AND e.content_hash != ''
        ORDER BY e.document_id, e.locator
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ============ 2. 去重与抽样（重复率 ≤5%） ============
def dedupe_and_sample(evidence, target=330):
    """去重后抽样，target=330 保证 120+50*2+30*3=310 个块足够。"""
    seen_hash = set()
    unique = []
    for ev in evidence:
        h = ev["content_hash"]
        if h in seen_hash:
            continue
        seen_hash.add(h)
        unique.append(ev)
    if len(unique) <= target:
        return unique
    return random.sample(unique, target)


# ============ 3. 生成查询（query）与黄金答案（chunks） ============
import re

# 噪声清洗：去掉"第X条"前缀、引用编号 [N]、页码、多余换行
_NOISE_PATTERNS = [
    re.compile(r'第[一二三四五六七八九十百千零\d]+条\s*[:：]?'),
    re.compile(r'\[\d+\]'),
    re.compile(r'-\s*\d+\s*-'),
    re.compile(r'\n+'),
]


def _clean_text(text: str) -> str:
    """清洗证据块文本噪声，返回可读句子。"""
    clean = text or ""
    for pat in _NOISE_PATTERNS:
        clean = pat.sub(" ", clean)
    clean = clean.strip()
    # 取前两句完整句子（以句号/分号分隔）
    parts = re.split(r'[。；]', clean)
    sentences = [p.strip() for p in parts if len(p.strip()) > 8]
    return "。".join(sentences[:2]) + "。" if sentences else clean[:60]


def make_query(ev):
    """从证据块内容提取关键词，构造真实用户场景的自然语言问题。"""
    import jieba.analyse

    text = ev.get("text") or ""
    title = ev.get("title") or ""
    clean = _clean_text(text)

    # 提取 top-3 关键词（去掉标题中已有的词，避免 query 和 title 过度重合）
    title_words = set(jieba.lcut(title))
    keywords = jieba.analyse.extract_tags(clean, topK=8, withWeight=False)
    kw = [k for k in keywords if k not in title_words and len(k) > 1][:3]

    if not kw:
        # 关键词提取失败时回退到原文片段
        return f"{title}中关于{clean[:25]}有什么规定？"

    kw_str = "".join(kw)

    # 根据文档类型选择不同的问题模板，模拟真实用户提问方式
    if "法" in title and ("安全" in title or "道路" in title):
        return f"{kw_str}的法律责任是怎么规定的？"
    elif "制度" in title:
        return f"{title}中对{kw_str}有什么具体要求？"
    elif "应急" in title or "预案" in title:
        return f"发生{kw_str}时应急处置流程是什么？"
    elif "事故" in title or "调查报告" in title:
        return f"{title}中关于{kw_str}的情况是怎样的？"
    elif "规程" in title or "规范" in title:
        return f"{kw_str}的操作规程是什么？"
    else:
        return f"{title}中关于{kw_str}有哪些规定？"


def build_test_items(sampled):
    """按 document 内 locator 相邻性分组，生成 120+50+30 条测试项。"""
    items = []
    by_doc = {}
    for ev in sorted(sampled, key=lambda x: (x["document_id"], x["locator"])):
        by_doc.setdefault(ev["document_id"], []).append(ev)

    def make_item(evs, group):
        return {
            "group": group,
            "query": make_query(evs[0]),
            "chunk_ids": [e["evidence_id"] for e in evs],
            "golden_answer": "\n".join(e["text"] or "" for e in evs),
            "title": evs[0]["title"],
            "topic": evs[0].get("topic"),
            "standard_level": evs[0].get("standard_level"),
        }

    # 1-chunk
    singles = []
    for doc_evs in by_doc.values():
        for ev in doc_evs:
            if len(singles) >= 120:
                break
            singles.append([ev])
        if len(singles) >= 120:
            break
    for evs in singles:
        items.append(make_item(evs, "query-1chunk"))

    # 2-chunk
    pairs = []
    for doc_evs in by_doc.values():
        for i in range(len(doc_evs) - 1):
            if len(pairs) >= 50:
                break
            a, b = doc_evs[i], doc_evs[i + 1]
            if a["evidence_id"] in {s[0]["evidence_id"] for s in singles}:
                continue
            if b["evidence_id"] in {s[0]["evidence_id"] for s in singles}:
                continue
            pairs.append([a, b])
        if len(pairs) >= 50:
            break
    for evs in pairs:
        items.append(make_item(evs, "query-2chunk"))

    # 3-chunk
    triples = []
    used_ids = {e for evs in (singles + pairs) for e in [x["evidence_id"] for x in evs]}
    for doc_evs in by_doc.values():
        for i in range(len(doc_evs) - 2):
            if len(triples) >= 30:
                break
            a, b, c = doc_evs[i], doc_evs[i + 1], doc_evs[i + 2]
            if a["evidence_id"] in used_ids or b["evidence_id"] in used_ids or c["evidence_id"] in used_ids:
                continue
            triples.append([a, b, c])
        if len(triples) >= 30:
            break
    for evs in triples:
        items.append(make_item(evs, "query-3chunk"))

    return items


# ============ 4. 检索策略评估（逐条输出到控制台） ============
def tokenize(text):
    try:
        import jieba
        return [t.strip() for t in jieba.lcut(text or "") if t.strip()]
    except Exception:
        return (text or "").split()


def eval_retrieval_strategies(items, evidence):
    """对比不同检索策略，逐条输出测试记录，返回统计结果 + 逐条详情。"""
    from rank_bm25 import BM25Okapi

    corpus = [tokenize(ev["text"]) for ev in evidence]
    bm25 = BM25Okapi(corpus)

    # 向量检索初始化
    import numpy as np
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    try:
        from app.services.embedding import embedding_service
        embedder = embedding_service
    except Exception as e:
        print(f"  [警告] 向量检索初始化失败: {e}，跳过向量检索")
        embedder = None

    # 预计算证据块向量
    evidence_vectors = []
    if embedder is not None:
        print("  预计算证据块向量...")
        for ev in evidence:
            vec = embedder.embed([ev["text"] or ""])[0]
            evidence_vectors.append(np.array(vec))
    evidence_matrix = np.array(evidence_vectors) if evidence_vectors else None

    # rerank 模型初始化（bge-rerank CrossEncoder）
    reranker = None
    try:
        from app.services.embedding import rerank_service
        reranker = rerank_service
        print("  rerank 模型加载完成")
    except Exception as e:
        print(f"  [警告] rerank 模型初始化失败: {e}，跳过 rerank 策略")

    # evidence_id -> text 映射，供 rerank 使用
    eid_to_text = {ev["evidence_id"]: (ev["text"] or "") for ev in evidence}

    strategies = [
        ("BM25-only", "bm25"),
        ("Vector-only", "vector"),
        ("Hybrid(BM25+Vector)", "hybrid"),
        ("Hybrid+Rerank", "hybrid_rerank"),
    ]

    results = {}
    all_details = []  # 逐条测试记录

    for name, method in strategies:
        print(f"\n{'='*70}")
        print(f"  策略: {name}")
        print(f"{'='*70}")

        recall5 = 0
        ctx_precision_sum = 0.0
        total = len(items)
        t_strategy_start = time.perf_counter()

        for idx, item in enumerate(items):
            query = item["query"]
            target_ids = set(item["chunk_ids"])
            group = item["group"]

            # BM25 检索
            bm25_scores = bm25.get_scores(tokenize(query))
            bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
            bm25_hits = [evidence[i]["evidence_id"] for i in bm25_ranked if bm25_scores[i] > 0][:50]

            # 向量检索
            vector_hits = []
            if embedder is not None and evidence_matrix is not None and evidence_matrix.size > 0:
                try:
                    qvec = np.array(embedder.embed([query])[0])
                    qnorm = np.linalg.norm(qvec)
                    enorms = np.linalg.norm(evidence_matrix, axis=1)
                    sims = np.dot(evidence_matrix, qvec) / (enorms * qnorm + 1e-9)
                    top_idx = np.argsort(sims)[::-1][:50]
                    vector_hits = [evidence[i]["evidence_id"] for i in top_idx if sims[i] > 0]
                except Exception:
                    vector_hits = []

            # 融合
            if method == "bm25":
                final_hits = bm25_hits
            elif method == "vector":
                final_hits = vector_hits
            elif method == "hybrid_rerank":
                rrf = {}
                for rank, eid in enumerate(bm25_hits):
                    rrf[eid] = rrf.get(eid, 0.0) + 1.0 / (60 + rank + 1)
                for rank, eid in enumerate(vector_hits):
                    rrf[eid] = rrf.get(eid, 0.0) + 1.0 / (60 + rank + 1)
                merged_top = sorted(rrf, key=lambda x: rrf[x], reverse=True)[:20]
                if reranker is not None and merged_top:
                    pairs = [(query, eid_to_text.get(eid, "")) for eid in merged_top]
                    scores = reranker._get_model().predict(pairs)
                    final_hits = [eid for eid, _ in sorted(zip(merged_top, scores), key=lambda x: float(x[1]), reverse=True)]
                else:
                    final_hits = merged_top
            else:  # hybrid: RRF
                rrf = {}
                for rank, eid in enumerate(bm25_hits):
                    rrf[eid] = rrf.get(eid, 0.0) + 1.0 / (60 + rank + 1)
                for rank, eid in enumerate(vector_hits):
                    rrf[eid] = rrf.get(eid, 0.0) + 1.0 / (60 + rank + 1)
                final_hits = sorted(rrf, key=lambda x: rrf[x], reverse=True)

            # 计算 Recall@5 与 Context Precision@5
            top5 = final_hits[:5]
            hit5 = target_ids.intersection(top5)
            if hit5:
                recall5 += 1
            ctx_precision_sum += len(hit5) / 5

            # 逐条输出到控制台
            hit5_str = "Y" if hit5 else "N"
            ctx_p = len(hit5) / 5
            query_short = query[:45] + "..." if len(query) > 45 else query
            print(f"  [{idx+1:3d}/{total}] {group:14s} | R@5={hit5_str} CP@5={ctx_p:.0%} | {query_short}")

            # 记录详细数据（top5_hits 供 LLM 评估用）
            all_details.append({
                "strategy": name,
                "index": idx + 1,
                "group": group,
                "query": query,
                "target_ids": list(target_ids),
                "top5_hits": top5,
                "top5_texts": [eid_to_text.get(eid, "")[:200] for eid in top5],
                "recall@5": bool(hit5),
                "context_precision@5": round(ctx_p, 2),
            })

        elapsed = time.perf_counter() - t_strategy_start
        results[name] = {
            "recall@5": recall5 / total,
            "context_precision@5": ctx_precision_sum / total,
            "elapsed_s": round(elapsed, 1),
        }

        print(f"\n  --- {name} 汇总 ---")
        print(f"  Recall@5={recall5/total:.2%}  Context Precision@5={ctx_precision_sum/total:.2%}  耗时={elapsed:.1f}s")

    return results, all_details


# ============ 4b. LLM 评估（忠实度 + 响应相关性） ============
def eval_llm_metrics(all_details, sample_size=50):
    """从全量测试中抽样，用 LLM 生成答案并评估忠实度与响应相关性。

    忠实度（Faithfulness）：答案中的陈述是否都能在检索证据中找到支持（0-1）。
    响应相关性（Answer Relevance）：答案是否直接回答了问题（0-1）。
    """
    import random as _rng
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from app.core.config import settings
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=120,
        max_retries=1,
    )

    # 按策略分组抽样
    strategies_seen = sorted(set(d["strategy"] for d in all_details))
    sampled = []
    for s in strategies_seen:
        s_details = [d for d in all_details if d["strategy"] == s]
        n = min(sample_size, len(s_details))
        sampled.extend(_rng.sample(s_details, n))

    print(f"\n  LLM 评估样本：{len(sampled)} 条（每策略 {sample_size} 条）")
    print(f"  模型：{settings.LLM_MODEL_NAME}\n")

    llm_details = []
    total = len(sampled)

    for idx, detail in enumerate(sampled):
        strategy = detail["strategy"]
        query = detail["query"]
        evidence_texts = detail.get("top5_texts", [])
        evidence = "\n\n".join(f"[{i+1}] {t}" for i, t in enumerate(evidence_texts)) or "无可用依据"

        # 一次调用：生成答案 + 自评忠实度 + 响应相关性
        prompt = (
            f"你是安全生产领域的助手。请基于以下证据回答问题，并评估你的回答质量。\n\n"
            f"问题：{query}\n\n"
            f"证据：\n{evidence}\n\n"
            f"要求：\n"
            f"1. 基于证据回答问题，不要编造证据之外的信息\n"
            f"2. 评估忠实度：你的回答中每个陈述是否都能在证据中找到支持？（0.0-1.0）\n"
            f"3. 评估响应相关性：你的回答是否直接回答了问题？（0.0-1.0）\n\n"
            f"请严格按以下 JSON 格式输出（不要输出其他内容）：\n"
            f'{{"answer": "你的回答", "faithfulness": 0.0, "answer_relevance": 0.0}}'
        )

        try:
            resp = client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是安全生产助手，严格按 JSON 格式输出。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                extra_body={"enable_thinking": False},
            )
            raw = resp.choices[0].message.content.strip()
            # 提取 JSON
            import re as _re
            m = _re.search(r'\{[^{}]*"answer"[^{}]*"faithfulness"[^{}]*"answer_relevance"[^{}]*\}', raw, _re.DOTALL)
            if m:
                obj = json.loads(m.group())
                answer = obj.get("answer", "")[:200]
                faithfulness = float(obj.get("faithfulness", 0))
                answer_relevance = float(obj.get("answer_relevance", 0))
            else:
                answer = raw[:200]
                faithfulness = 0.0
                answer_relevance = 0.0
        except Exception as e:
            answer = f"[LLM 调用失败: {e}]"
            faithfulness = 0.0
            answer_relevance = 0.0

        llm_details.append({
            "strategy": strategy,
            "index": detail["index"],
            "query": query[:60],
            "answer": answer,
            "faithfulness": round(faithfulness, 2),
            "answer_relevance": round(answer_relevance, 2),
        })

        if (idx + 1) % 10 == 0 or idx == total - 1:
            print(f"  [{idx+1}/{total}] {strategy} | faith={faithfulness:.2f} rel={answer_relevance:.2f}")

    # 按策略汇总
    llm_results = {}
    for s in strategies_seen:
        s_items = [d for d in llm_details if d["strategy"] == s]
        n = len(s_items)
        if n == 0:
            continue
        llm_results[s] = {
            "faithfulness": sum(d["faithfulness"] for d in s_items) / n,
            "answer_relevance": sum(d["answer_relevance"] for d in s_items) / n,
            "sample_size": n,
        }
        print(f"\n  --- {s} LLM 评估汇总 ---")
        print(f"  忠实度={llm_results[s]['faithfulness']:.3f}  响应相关性={llm_results[s]['answer_relevance']:.3f}  （{n} 条）")

    return llm_results, llm_details


# ============ 5. 生成 Markdown 报告 ============
def write_report(items, eval_results, all_details, llm_results=None, llm_details=None):
    group_counts = {}
    for item in items:
        group_counts[item["group"]] = group_counts.get(item["group"], 0) + 1

    lines = []
    lines.append("# AI 智能助手检索策略评估报告")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 测试集规模：{len(items)} 条")
    lines.append(f"> 报告目录：`{REPORT_DIR}`")
    lines.append("")
    lines.append("## 一、测试集构成")
    lines.append("")
    lines.append("| 分组 | 数量 | 说明 |")
    lines.append("|------|------|------|")
    for group, desc in [("query-1chunk", "答案在单个证据块"), ("query-2chunk", "答案跨 2 个证据块"), ("query-3chunk", "答案跨 3 个证据块")]:
        lines.append(f"| {group} | {group_counts.get(group, 0)} | {desc} |")
    lines.append("")
    lines.append("去重策略：按 content_hash 去重，重复率 0%（≤5% 要求满足）。")
    lines.append("")
    lines.append("## 二、检索指标（全量 200 条）")
    lines.append("")
    lines.append("| 检索策略 | Recall@5 | Context Precision@5 | 耗时(s) |")
    lines.append("|----------|----------|---------------------|---------|")
    for name, r in eval_results.items():
        lines.append(f"| {name} | {r['recall@5']:.2%} | {r['context_precision@5']:.2%} | {r['elapsed_s']} |")
    lines.append("")
    lines.append("- **Recall@5**：Top-5 检索结果中是否命中目标证据块（业务使用 top_k=5）")
    lines.append("- **Context Precision@5**：Top-5 中命中目标块的比例（越高越精确）")
    lines.append("")

    # 逐策略分组命中率
    lines.append("## 三、逐策略分组命中率")
    lines.append("")
    for name in eval_results:
        s_details = [d for d in all_details if d["strategy"] == name]
        for group in ["query-1chunk", "query-2chunk", "query-3chunk"]:
            g_details = [d for d in s_details if d["group"] == group]
            if not g_details:
                continue
            r5 = sum(1 for d in g_details if d["recall@5"]) / len(g_details)
            cp = sum(d["context_precision@5"] for d in g_details) / len(g_details)
            lines.append(f"- **{name}** / {group}：R@5={r5:.0%}  CP@5={cp:.0%}  （{len(g_details)} 条）")
        lines.append("")

    # LLM 评估指标
    if llm_results:
        sample_n = next(iter(llm_results.values()), {}).get("sample_size", "?")
        lines.append("## 四、LLM 生成质量评估（忠实度 + 响应相关性）")
        lines.append("")
        lines.append(f"> 评估方式：每策略抽样 {sample_n} 条，用 LLM 基于检索证据生成答案并自评")
        lines.append("")
        lines.append("| 检索策略 | 忠实度 | 响应相关性 | 样本数 |")
        lines.append("|----------|--------|------------|--------|")
        for name in eval_results:
            if name in llm_results:
                r = llm_results[name]
                lines.append(f"| {name} | {r['faithfulness']:.3f} | {r['answer_relevance']:.3f} | {r['sample_size']} |")
        lines.append("")
        lines.append("- **忠实度（Faithfulness）**：答案中的陈述是否都能在检索证据中找到支持（0-1，越高越好）")
        lines.append("- **响应相关性（Answer Relevance）**：答案是否直接回答了问题（0-1，越高越好）")
        lines.append("")

    # 结论
    lines.append("## 五、结论与建议")
    lines.append("")
    best_recall = max(eval_results.items(), key=lambda x: x[1]["recall@5"])
    lines.append(f"1. 检索召回最优策略为 **{best_recall[0]}**（Recall@5={best_recall[1]['recall@5']:.2%}）。")
    if llm_results:
        best_faith = max(llm_results.items(), key=lambda x: x[1]["faithfulness"])
        best_rel = max(llm_results.items(), key=lambda x: x[1]["answer_relevance"])
        lines.append(f"2. 忠实度最优：**{best_faith[0]}**（{best_faith[1]['faithfulness']:.3f}）。")
        lines.append(f"3. 响应相关性最优：**{best_rel[0]}**（{best_rel[1]['answer_relevance']:.3f}）。")
    lines.append("")
    lines.append(f"> 逐条测试明细见：`test_detail_log.json`")
    if llm_details:
        lines.append(f"> LLM 评估明细见：`llm_eval_details.json`")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


# ============ 主流程 ============
def main():
    print("=" * 70)
    print("  AI 智能助手测试集构建与检索策略评估")
    print(f"  报告输出目录: {REPORT_DIR}")
    print("=" * 70)

    print("\n步骤 1/6：读取知识库证据块...")
    evidence = load_evidence()
    print(f"  共读取 {len(evidence)} 条证据块")

    print("\n步骤 2/6：去重并抽样 200 条...")
    sampled = dedupe_and_sample(evidence, 330)
    print(f"  抽样 {len(sampled)} 个去重块（重复率 0%）")

    print("\n步骤 3/6：生成查询与黄金答案...")
    items = build_test_items(sampled)
    print(f"  生成 {len(items)} 条测试项")

    print("\n步骤 4/6：评估检索策略（逐条输出）...")
    eval_results, all_details = eval_retrieval_strategies(items, sampled)

    print(f"\n步骤 5/6：LLM 生成质量评估（忠实度 + 响应相关性）...")
    llm_results, llm_details = eval_llm_metrics(all_details, sample_size=50)

    print(f"\n步骤 6/6：生成报告...")
    report = write_report(items, eval_results, all_details, llm_results, llm_details)
    print(f"  Markdown 报告: {report}")

    # 保存逐条明细 JSON
    DETAILED_LOG_PATH.write_text(
        json.dumps(all_details, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  逐条明细 JSON: {DETAILED_LOG_PATH}")

    # 保存 LLM 评估明细 JSON
    LLM_DETAILS_PATH = REPORT_DIR / "llm_eval_details.json"
    LLM_DETAILS_PATH.write_text(
        json.dumps(llm_details, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  LLM 评估明细 JSON: {LLM_DETAILS_PATH}")

    # 保存测试集 JSON 备份
    TESTSET_JSON_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  测试集 JSON: {TESTSET_JSON_PATH}")

    print("\n" + "=" * 70)
    print("  全部完成！")
    print(f"  报告目录: {REPORT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
