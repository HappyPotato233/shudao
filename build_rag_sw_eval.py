"""用滑动窗口分块重新构建知识库语料，然后跑 RAG 检索评估。

流程：
1. 从 transport_safety_kb 的 documents 表读取原始文档全文
2. 用系统内置的 _split_text_sliding_window 滑动窗口分块
3. 对新语料跑 4 种检索策略（BM25 / Vector / Hybrid / Hybrid+Rerank）
4. 生成对比报告
"""
import json
import re
import time
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
KB_PATH = PROJECT_ROOT / "project-root" / "database" / "transport_safety_kb.sqlite3"
TESTSET_PATH = PROJECT_ROOT / "test_report" / "ai_testset_200.json"
REPORT_DIR = PROJECT_ROOT / "test_report"
SW_REPORT_PATH = REPORT_DIR / "rag_sliding_window_eval_report.md"

# 导入系统的滑动窗口分块函数
sys.path.insert(0, str(PROJECT_ROOT / "project-root" / "backend"))
from app.services.knowledge_service import _split_text_sliding_window


# ============ 1. 读取文档并用滑动窗口分块 ============
def load_and_chunk():
    """从知识库读取文档全文，用滑动窗口重新分块。"""
    con = sqlite3.connect(f"file:{KB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT document_id, title, text,
               (SELECT k2.topic FROM knowledge_entries k2
                WHERE k2.document_id = d.document_id AND k2.invalidated = 0
                ORDER BY k2.rowid LIMIT 1) AS topic,
               d.document_type,
               CASE
                   WHEN d.jurisdiction = '国家' THEN '国家规范'
                   WHEN d.jurisdiction LIKE '%公司%' OR d.jurisdiction LIKE '%集团%'
                        OR d.jurisdiction LIKE '%企业%' THEN '企业规范'
                   ELSE '地方规范'
               END AS standard_level
        FROM documents d
        WHERE d.text IS NOT NULL AND trim(d.text) != ''
        ORDER BY d.document_id
    """).fetchall()
    con.close()

    # 滑动窗口分块（500字 / 250字重叠 = 50% 重叠）
    all_chunks = []
    for row in rows:
        doc = dict(row)
        chunks = _split_text_sliding_window(doc["text"] or "", chunk_size=500, chunk_overlap=250)
        for i, c in enumerate(chunks):
            all_chunks.append({
                "evidence_id": f"sw_{doc['document_id']}_{i}",
                "document_id": doc["document_id"],
                "title": doc["title"],
                "text": c,
                "topic": doc.get("topic"),
                "document_type": doc.get("document_type"),
                "standard_level": doc.get("standard_level"),
                "locator": str(i),
            })

    print(f"  文档数: {len(rows)}, 滑动窗口分块数: {len(all_chunks)}")
    return all_chunks


# ============ 2. 检索评估 ============
def tokenize(text):
    try:
        import jieba
        return [t.strip() for t in jieba.lcut(text or "") if t.strip()]
    except Exception:
        return (text or "").split()


def bigram_set(text):
    s = (text or "").replace("\n", "").replace(" ", "")
    return {s[i:i + 2] for i in range(len(s) - 1)}


def bigram_overlap(a, b):
    sa, sb = bigram_set(a), bigram_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def eval_strategies(chunks, test_items):
    """对滑动窗口分块后的语料跑 4 种检索策略。"""
    from rank_bm25 import BM25Okapi
    import numpy as np

    # BM25 索引
    corpus = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus)

    # 向量索引
    from app.services.embedding import embedding_service
    embedder = embedding_service
    print("  预计算证据块向量...")
    evidence_vectors = []
    for c in chunks:
        vec = embedder.embed([c["text"]])[0]
        evidence_vectors.append(np.array(vec))
    evidence_matrix = np.array(evidence_vectors)

    # rerank 模型
    reranker = None
    try:
        from app.services.embedding import rerank_service
        reranker = rerank_service
        print("  rerank 模型加载完成")
    except Exception as e:
        print(f"  [警告] rerank 模型加载失败: {e}")

    eid_to_text = {c["evidence_id"]: c["text"] for c in chunks}

    strategies = [
        ("BM25-only", "bm25"),
        ("Vector-only", "vector"),
        ("Hybrid(BM25+Vector)", "hybrid"),
        ("Hybrid+Rerank", "hybrid_rerank"),
    ]

    results = {}
    all_details = []

    for name, method in strategies:
        print(f"\n{'='*60}")
        print(f"  策略: {name} (滑动窗口分块)")
        print(f"{'='*60}")

        recall5 = 0
        ctx_precision_sum = 0.0
        total = len(test_items)
        t0 = time.perf_counter()

        for idx, item in enumerate(test_items):
            query = item["query"]
            golden = item["golden_answer"]

            # BM25 检索
            bm25_scores = bm25.get_scores(tokenize(query))
            bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
            bm25_hits = [chunks[i]["evidence_id"] for i in bm25_ranked if bm25_scores[i] > 0][:50]

            # 向量检索
            vector_hits = []
            if evidence_matrix.size > 0:
                qvec = np.array(embedder.embed([query])[0])
                qnorm = np.linalg.norm(qvec)
                enorms = np.linalg.norm(evidence_matrix, axis=1)
                sims = np.dot(evidence_matrix, qvec) / (enorms * qnorm + 1e-9)
                top_idx = np.argsort(sims)[::-1][:50]
                vector_hits = [chunks[i]["evidence_id"] for i in top_idx if sims[i] > 0]

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
            else:  # hybrid
                rrf = {}
                for rank, eid in enumerate(bm25_hits):
                    rrf[eid] = rrf.get(eid, 0.0) + 1.0 / (60 + rank + 1)
                for rank, eid in enumerate(vector_hits):
                    rrf[eid] = rrf.get(eid, 0.0) + 1.0 / (60 + rank + 1)
                final_hits = sorted(rrf, key=lambda x: rrf[x], reverse=True)

            # 命中判断：bigram 重合率 >= 0.3
            top5 = final_hits[:5]
            hit = False
            hit_count = 0
            for eid in top5:
                overlap = bigram_overlap(eid_to_text.get(eid, ""), golden)
                if overlap >= 0.3:
                    hit = True
                    hit_count += 1

            if hit:
                recall5 += 1
            ctx_precision_sum += hit_count / 5

            if (idx + 1) % 50 == 0 or idx == total - 1:
                print(f"    [{idx+1}/{total}] R@5={'Y' if hit else 'N'} CP@5={hit_count/5:.0%}")

            all_details.append({
                "strategy": name,
                "index": idx + 1,
                "group": item["group"],
                "query": query[:60],
                "recall@5": hit,
                "context_precision@5": round(hit_count / 5, 2),
            })

        elapsed = time.perf_counter() - t0
        results[name] = {
            "recall@5": recall5 / total,
            "context_precision@5": ctx_precision_sum / total,
            "elapsed_s": round(elapsed, 1),
        }
        print(f"\n  --- {name} 汇总 ---")
        print(f"  Recall@5={recall5/total:.2%}  CP@5={ctx_precision_sum/total:.2%}  耗时={elapsed:.1f}s")

    return results, all_details


# ============ 3. 报告 ============
def write_report(results, all_details, prev_results=None):
    lines = []
    lines.append("# RAG 检索评估报告（滑动窗口分块）")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 测试集规模：200 条")
    lines.append(f"> 分块策略：滑动窗口 500字 / 250字重叠（50%重叠率）")
    lines.append(f"> 命中判断：bigram 重合率 ≥ 0.3")
    lines.append("")

    if prev_results:
        lines.append("## 检索指标对比（滑动窗口 vs 原始分块）")
        lines.append("")
        lines.append("| 检索策略 | Recall@5(滑动窗口) | Recall@5(原始) | CP@5(滑动窗口) | CP@5(原始) |")
        lines.append("|----------|-------------------|---------------|---------------|-----------|")
        for name in results:
            r = results[name]
            p = prev_results.get(name, {})
            lines.append(f"| {name} | {r['recall@5']:.2%} | {p.get('recall@5', 0):.2%} | {r['context_precision@5']:.2%} | {p.get('context_precision@5', 0):.2%} |")
        lines.append("")
    else:
        lines.append("## 检索指标")
        lines.append("")
        lines.append("| 检索策略 | Recall@5 | Context Precision@5 | 耗时(s) |")
        lines.append("|----------|----------|---------------------|---------|")
        for name, r in results.items():
            lines.append(f"| {name} | {r['recall@5']:.2%} | {r['context_precision@5']:.2%} | {r['elapsed_s']} |")
        lines.append("")

    # 分组
    lines.append("## 逐策略分组命中率")
    lines.append("")
    for name in results:
        s_details = [d for d in all_details if d["strategy"] == name]
        for group in ["query-1chunk", "query-2chunk", "query-3chunk"]:
            g_details = [d for d in s_details if d["group"] == group]
            if not g_details:
                continue
            r5 = sum(1 for d in g_details if d["recall@5"]) / len(g_details)
            cp = sum(d["context_precision@5"] for d in g_details) / len(g_details)
            lines.append(f"- **{name}** / {group}：R@5={r5:.0%}  CP@5={cp:.0%}  （{len(g_details)} 条）")
        lines.append("")

    lines.append("## 结论")
    lines.append("")
    best = max(results.items(), key=lambda x: x[1]["recall@5"])
    lines.append(f"1. 滑动窗口分块 + {best[0]} 的 Recall@5={best[1]['recall@5']:.2%}")
    if prev_results:
        prev_best = max(prev_results.items(), key=lambda x: x[1]["recall@5"])
        delta = best[1]["recall@5"] - prev_best[1]["recall@5"]
        lines.append(f"2. 对比原始最优策略({prev_best[0]} R@5={prev_best[1]['recall@5']:.2%})，{'提升' if delta > 0 else '降低'} {abs(delta):.1%}")
    lines.append("")

    SW_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return SW_REPORT_PATH


# ============ 主流程 ============
def main():
    print("=" * 70)
    print("  RAG 检索评估（滑动窗口分块）")
    print("=" * 70)

    # 1. 加载测试集
    print("\n步骤 1/4：加载测试集...")
    test_items = json.loads(TESTSET_PATH.read_text(encoding="utf-8"))
    print(f"  测试集: {len(test_items)} 条")

    # 2. 滑动窗口分块
    print("\n步骤 2/4：读取知识库文档并用滑动窗口分块...")
    chunks = load_and_chunk()

    # 3. 检索评估
    print(f"\n步骤 3/4：检索策略评估（4 种策略）...")
    results, all_details = eval_strategies(chunks, test_items)

    # 4. 加载之前的评估结果做对比
    prev_report = REPORT_DIR / "rag_retrieval_eval_report.md"
    prev_results = None
    if prev_report.exists():
        # 从之前的 JSON 明细中提取 Recall@5 和 CP@5
        prev_detail_path = REPORT_DIR / "test_detail_log.json"
        if prev_detail_path.exists():
            prev_details = json.loads(prev_detail_path.read_text(encoding="utf-8"))
            prev_results = {}
            for d in prev_details:
                s = d["strategy"]
                if s not in prev_results:
                    prev_results[s] = {"recall5_sum": 0, "cp_sum": 0.0, "count": 0}
                prev_results[s]["recall5_sum"] += 1 if d.get("recall@5") else 0
                prev_results[s]["cp_sum"] += d.get("context_precision@5", 0)
                prev_results[s]["count"] += 1
            for s in prev_results:
                n = prev_results[s]["count"]
                prev_results[s] = {
                    "recall@5": prev_results[s]["recall5_sum"] / n,
                    "context_precision@5": prev_results[s]["cp_sum"] / n,
                }

    # 5. 生成报告
    print(f"\n步骤 4/4：生成报告...")
    report = write_report(results, all_details, prev_results)
    print(f"  报告: {report}")

    detail_path = REPORT_DIR / "rag_sw_eval_details.json"
    detail_path.write_text(json.dumps(all_details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  明细: {detail_path}")

    print("\n" + "=" * 70)
    print("  完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
