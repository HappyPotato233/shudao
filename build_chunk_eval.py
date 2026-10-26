"""高级分块策略对比评估脚本

对比 5 种分块策略的 BM25 检索效果：

1. 固定500字/100重叠（系统当前默认，基线）
2. 父子分块（Small-to-Big）：小块200字检索，命中后映射到父块800字
3. 语义分块（Semantic Chunking）：用 embedding 计算句子相似度，语义断点切分
4. 递归结构化分块：按"第X章/节/条"标题层级切分
5. 滑动窗口分块：500字块 + 50% 重叠率（250字重叠）

命中判断：top-5 检索结果与 golden_answer 的 bigram 重合率 ≥ 0.3
"""
import json
import re
import time
import sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
KB_PATH = PROJECT_ROOT / "project-root" / "database" / "transport_safety_kb.sqlite3"
TESTSET_PATH = PROJECT_ROOT / "test_report" / "ai_testset_200.json"
REPORT_DIR = PROJECT_ROOT / "test_report"
CHUNK_REPORT_PATH = REPORT_DIR / "chunk_strategy_eval_report.md"

# ============ 1. 读取原始文档 ============
def load_documents():
    con = sqlite3.connect(f"file:{KB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT document_id, title, text
        FROM documents
        WHERE text IS NOT NULL AND trim(text) != ''
        ORDER BY document_id
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ============ 2. 分块策略实现 ============

# --- 策略 0：固定500字/100重叠（系统默认，基线） ---
def chunk_fixed_500(text):
    """递归分隔符切分，500字/100重叠（与系统 knowledge_service 一致）。"""
    seps = ["\n\n", "\n", "。", "；"]
    size, overlap = 500, 100
    if len(text) <= size:
        return [text.strip()] if text.strip() else []

    def _split(segment, seps):
        if len(segment) <= size:
            return [segment]
        if not seps:
            return [segment[i:i + size] for i in range(0, len(segment), size)]
        sep = seps[0]
        parts = segment.split(sep)
        result = []
        for part in parts:
            if len(part) > size:
                result.extend(_split(part, seps[1:]))
            else:
                result.append(part)
        return result

    parts = _split(text, seps)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if chunks and len(chunks[-1]) < size:
            tail = chunks[-1][-overlap:] if overlap else ""
            chunks[-1] = (chunks[-1] + part)[:size]
        else:
            chunks.append(part)
    return [c for c in chunks if c.strip()]


# --- 策略 1：父子分块（Small-to-Big） ---
def chunk_parent_child(text):
    """父子分块：文档先切成父块(800字)，每个父块再切成子块(200字)。
    返回子块列表，每个子块携带 parent_index 映射到父块。
    """
    seps = ["\n\n", "\n", "。", "；"]
    parent_size = 800

    # 切父块
    if len(text) <= parent_size:
        parents = [text.strip()] if text.strip() else []
    else:
        def _split(segment, seps):
            if len(segment) <= parent_size:
                return [segment]
            if not seps:
                return [segment[i:i + parent_size] for i in range(0, len(segment), parent_size)]
            sep = seps[0]
            parts = segment.split(sep)
            result = []
            for part in parts:
                if len(part) > parent_size:
                    result.extend(_split(part, seps[1:]))
                else:
                    result.append(part)
            return result
        parents = [p.strip() for p in _split(text, seps) if p.strip()]

    # 每个父块切成子块(300字)
    child_size = 300
    children = []
    for pidx, parent in enumerate(parents):
        if len(parent) <= child_size:
            children.append({"text": parent, "parent_index": pidx, "parent_text": parent})
        else:
            # 按句子切子块
            sentences = re.split(r'(?<=[。；])', parent)
            sentences = [s.strip() for s in sentences if s.strip()]
            current = ""
            for sent in sentences:
                if len(current) + len(sent) <= child_size:
                    current += sent
                else:
                    if current:
                        children.append({"text": current, "parent_index": pidx, "parent_text": parent})
                    current = sent
            if current:
                children.append({"text": current, "parent_index": pidx, "parent_text": parent})
    return children


# --- 策略 2：语义分块（Semantic Chunking） ---
def chunk_semantic(text, embedder=None):
    """语义分块：用 embedding 计算相邻句子相似度，低于阈值时切分。
    无 embedder 时回退到按句子合并（每块≤500字）。
    """
    # 按句子拆分
    sentences = re.split(r'(?<=[。；！？\n])', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 2]
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    if embedder is None:
        # 无 embedder：回退到按句子合并至 500 字
        chunks = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= 500:
                current += sent
            else:
                if current:
                    chunks.append(current)
                current = sent
        if current:
            chunks.append(current)
        return chunks

    # 有 embedder：计算句子向量，用余弦相似度找语义断点
    import numpy as np
    vecs = np.array(embedder.embed(sentences))
    # 归一化
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs_norm = vecs / (norms + 1e-9)
    # 相邻句子的余弦相似度
    sims = np.array([np.dot(vecs_norm[i], vecs_norm[i + 1]) for i in range(len(vecs) - 1)])

    # 动态阈值：用均值 - 标准差作为切分点
    threshold = np.mean(sims) - np.std(sims)

    # 按语义断点切分
    chunks = []
    current_sents = [sentences[0]]
    for i in range(len(sims)):
        if sims[i] < threshold:
            # 语义断点，切分
            chunks.append("".join(current_sents))
            current_sents = [sentences[i + 1]]
        else:
            current_sents.append(sentences[i + 1])
            # 长度保护：超过 800 字强制切
            if sum(len(s) for s in current_sents) > 800:
                chunks.append("".join(current_sents))
                current_sents = []
    if current_sents:
        chunks.append("".join(current_sents))
    return [c for c in chunks if c.strip()]


# --- 策略 5：语义父子分块（Semantic + Parent-Child） ---
def chunk_semantic_parent_child(text, embedder=None):
    """语义父子分块：先用语义分块切语义父块，再在每个父块内按句子累积切子块(300字)。

    结合语义分块（父块语义完整）与父子分块（子块精确检索+父块上下文）的优势。
    返回子块列表，每个子块携带 parent_index / parent_text 映射到语义父块。
    """
    # 第一层：语义分块得到语义父块（语义完整单元，替代固定800字父块）
    parents = chunk_semantic(text, embedder=embedder)
    if not parents:
        return []

    # 第二层：每个语义父块按句子累积切子块（检索粒度，与父子分块子块逻辑一致）
    child_size = 300
    children = []
    for pidx, parent in enumerate(parents):
        parent = parent.strip()
        if not parent:
            continue
        if len(parent) <= child_size:
            # 短父块直接作为单子块（父子同块）
            children.append({"text": parent, "parent_index": pidx, "parent_text": parent})
            continue
        sentences = re.split(r'(?<=[。；])', parent)
        sentences = [s.strip() for s in sentences if s.strip()]
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= child_size:
                current += sent
            else:
                if current:
                    children.append({"text": current, "parent_index": pidx, "parent_text": parent})
                current = sent
        if current:
            children.append({"text": current, "parent_index": pidx, "parent_text": parent})
    return children


# --- 策略 3：递归结构化分块 ---
def chunk_structured(text):
    """按法规文档结构层级切分：第X章 -> 第X节 -> 第X条。
    每条作为一个块，相邻条合并至 ≤500 字。
    """
    # 按"第X条"切分
    articles = re.split(r'(第[一二三四五六七八九十百千零\d]+条)', text)
    if len(articles) <= 1:
        # 没有条款结构，回退到固定切分
        return chunk_fixed_500(text)

    # 重新组装：条款标题 + 内容
    blocks = []
    i = 1
    while i < len(articles):
        title = articles[i].strip()
        content = articles[i + 1].strip() if i + 1 < len(articles) else ""
        blocks.append(title + content)
        i += 2

    # 相邻条合并至 ≤500 字
    chunks = []
    current = ""
    for block in blocks:
        if len(current) + len(block) <= 500:
            current += block
        else:
            if current:
                chunks.append(current)
            if len(block) <= 500:
                current = block
            else:
                # 单条超过500字，硬切
                for j in range(0, len(block), 500):
                    chunks.append(block[j:j + 500])
                current = ""
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


# --- 策略 4：滑动窗口分块（50% 重叠） ---
def chunk_sliding_window(text):
    """滑动窗口：500字块，250字重叠（50%重叠率）。"""
    size = 500
    overlap = 250
    if len(text) <= size:
        return [text.strip()] if text.strip() else []

    # 先按段落切分，再在段落边界做滑动窗口
    seps = ["\n\n", "\n", "。", "；"]
    def _split(segment, seps):
        if len(segment) <= size:
            return [segment]
        if not seps:
            return [segment[i:i + size] for i in range(0, len(segment), size)]
        sep = seps[0]
        parts = segment.split(sep)
        result = []
        for part in parts:
            if len(part) > size:
                result.extend(_split(part, seps[1:]))
            else:
                result.append(part)
        return result

    parts = _split(text, seps)
    # 滑动窗口：步长 = size - overlap
    chunks = []
    buffer = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        buffer += part
        while len(buffer) >= size:
            chunks.append(buffer[:size])
            buffer = buffer[size - overlap:]  # 保留重叠部分
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks


# ============ 3. BM25 检索 + 命中判断 ============

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
    """覆盖率：a 的 bigram 有多少出现在 b 中。a=chunk, b=golden_answer"""
    sa, sb = bigram_set(a), bigram_set(b)
    if not sa:
        return 0.0
    return len(sa & sb) / len(sa)


def eval_strategy(strategy_name, documents, test_items, chunk_fn, embedder=None, is_parent_child=False):
    """对一种分块策略评估。

    is_parent_child=True 时，chunk_fn 返回 [{text, parent_text}] 结构：
    检索用子块 text 建索引，命中判断用父块 parent_text 匹配 golden_answer。
    """
    from rank_bm25 import BM25Okapi

    # 1. 分块
    all_chunks = []

    for doc in documents:
        if is_parent_child:
            chunks = chunk_fn(doc["text"] or "")
            for i, c in enumerate(chunks):
                all_chunks.append({
                    "doc_id": doc["document_id"],
                    "title": doc["title"],
                    "chunk_index": i,
                    "text": c["text"],
                    "parent_text": c.get("parent_text", c["text"]),
                })
        else:
            if strategy_name == "语义分块(Semantic)":
                chunks = chunk_fn(doc["text"] or "")
            else:
                chunks = chunk_fn(doc["text"] or "")
            for i, c in enumerate(chunks):
                all_chunks.append({
                    "doc_id": doc["document_id"],
                    "title": doc["title"],
                    "chunk_index": i,
                    "text": c,
                    "parent_text": c,
                })

    print(f"  分块数: {len(all_chunks)}", flush=True)

    # 2. BM25 索引（用检索文本：父子分块用子块文本，其他用块文本）
    search_texts = [c["text"] for c in all_chunks]
    corpus = [tokenize(t) for t in search_texts]
    bm25 = BM25Okapi(corpus)

    # 向量索引（Hybrid 检索用）
    import numpy as np
    evidence_matrix = None
    if embedder is not None:
        n = len(search_texts)
        print(f"  预计算向量 ({n} 块, batch=32)...", flush=True)
        evidence_vectors = []
        batch_size = 32
        for i in range(0, n, batch_size):
            batch = search_texts[i:i + batch_size]
            vecs = embedder.embed(batch)
            evidence_vectors.extend(vecs)
            done = min(i + batch_size, n)
            if done % 160 == 0 or done == n:
                print(f"    向量进度: {done}/{n}", flush=True)
        evidence_matrix = np.array(evidence_vectors)
        print(f"  向量索引完成: shape={evidence_matrix.shape}", flush=True)

    # 3. 逐条检索
    recall5 = 0
    ctx_precision_sum = 0.0
    total = len(test_items)
    detail_records = []

    for idx, item in enumerate(test_items):
        query = item["query"]
        golden = item["golden_answer"]

        # BM25 检索
        bm25_scores = bm25.get_scores(tokenize(query))
        bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
        bm25_hits = [i for i in bm25_ranked if bm25_scores[i] > 0][:50]

        # 向量检索
        vector_hits = []
        if evidence_matrix is not None and evidence_matrix.size > 0:
            qvec = np.array(embedder.embed([query])[0])
            qnorm = np.linalg.norm(qvec)
            enorms = np.linalg.norm(evidence_matrix, axis=1)
            sims = np.dot(evidence_matrix, qvec) / (enorms * qnorm + 1e-9)
            top_vec_idx = np.argsort(sims)[::-1][:50]
            vector_hits = [i for i in top_vec_idx if sims[i] > 0]

        # RRF 融合
        rrf = {}
        for rank, i in enumerate(bm25_hits):
            rrf[i] = rrf.get(i, 0.0) + 1.0 / (60 + rank + 1)
        for rank, i in enumerate(vector_hits):
            rrf[i] = rrf.get(i, 0.0) + 1.0 / (60 + rank + 1)
        final_ranked = sorted(rrf, key=lambda x: rrf[x], reverse=True)

        top5_idx = final_ranked[:5]
        top5_chunks = [all_chunks[i] for i in top5_idx]

        # 命中判断：父子分块用 parent_text 匹配，其他用 text
        hit = False
        hit_count = 0
        for chunk in top5_chunks:
            match_text = chunk["parent_text"] if is_parent_child else chunk["text"]
            overlap = bigram_overlap(match_text, golden)
            if overlap >= 0.2:
                hit = True
                hit_count += 1

        if hit:
            recall5 += 1
        ctx_precision_sum += hit_count / 5

        if (idx + 1) % 20 == 0 or idx == total - 1:
            print(f"    [{idx+1}/{total}] R@5={'Y' if hit else 'N'} CP@5={hit_count/5:.0%}", flush=True)

        detail_records.append({
            "index": idx + 1,
            "group": item["group"],
            "query": query[:60],
            "recall@5": hit,
            "context_precision@5": round(hit_count / 5, 2),
        })

    return {
        "recall@5": recall5 / total,
        "context_precision@5": ctx_precision_sum / total,
        "chunk_count": len(all_chunks),
        "avg_chunk_len": sum(len(c["text"]) for c in all_chunks) / len(all_chunks) if all_chunks else 0,
        "details": detail_records,
    }


# ============ 4. 报告 ============

def write_report(results):
    lines = []
    lines.append("# 高级分块策略对比评估报告")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 测试集规模：200 条（复用 RAG 评估测试集）")
    lines.append(f"> 检索方式：Hybrid (BM25+Vector+RRF)")
    lines.append(f"> 命中判断：bigram 覆盖率 ≥ 0.2（chunk 的 bigram 覆盖 golden_answer 的比例）")
    lines.append("")
    lines.append("## 一、分块策略说明")
    lines.append("")
    lines.append("| 策略 | 原理 | 优势 |")
    lines.append("|------|------|------|")
    lines.append("| 固定500字/100重叠（基线） | 递归分隔符切分，系统当前默认 | 实现简单，均衡 |")
    lines.append("| 父子分块(Small-to-Big) | 子块300字检索，命中后返回父块800字 | 精确匹配+完整上下文 |")
    lines.append("| 语义分块(Semantic) | 用 embedding 计算句子相似度，语义断点切分 | 语义完整性 |")
    lines.append("| 语义父子分块(Semantic+Parent-Child) | 语义父块(语义切分)+子块300字检索 | 语义完整上下文+精确检索 |")
    lines.append("| 递归结构化分块 | 按「第X章/节/条」标题层级切分 | 法规结构保持 |")
    lines.append("| 滑动窗口(50%重叠) | 500字块，250字重叠 | 高召回，防边界断裂 |")
    lines.append("")
    lines.append("## 二、对比结果")
    lines.append("")
    lines.append("| 分块策略 | 分块数 | 平均块长 | Recall@5 | Context Precision@5 |")
    lines.append("|----------|--------|----------|----------|---------------------|")
    for name, r in results.items():
        lines.append(f"| {name} | {r['chunk_count']} | {r['avg_chunk_len']:.0f} | {r['recall@5']:.2%} | {r['context_precision@5']:.2%} |")
    lines.append("")

    # 分组
    lines.append("## 三、逐策略分组命中率")
    lines.append("")
    for name, r in results.items():
        for group in ["query-1chunk", "query-2chunk", "query-3chunk"]:
            g_details = [d for d in r["details"] if d["group"] == group]
            if not g_details:
                continue
            r5 = sum(1 for d in g_details if d["recall@5"]) / len(g_details)
            cp = sum(d["context_precision@5"] for d in g_details) / len(g_details)
            lines.append(f"- **{name}** / {group}：R@5={r5:.0%}  CP@5={cp:.0%}  （{len(g_details)} 条）")
        lines.append("")

    # 结论
    lines.append("## 四、结论与建议")
    lines.append("")
    best = max(results.items(), key=lambda x: x[1]["recall@5"])
    best_cp = max(results.items(), key=lambda x: x[1]["context_precision@5"])
    lines.append(f"1. 检索召回最优分块策略为 **{best[0]}**（Recall@5={best[1]['recall@5']:.2%}）。")
    lines.append(f"2. 精确度最优为 **{best_cp[0]}**（Context Precision@5={best_cp[1]['context_precision@5']:.2%}）。")
    lines.append("3. 父子分块在精确匹配的同时保留完整上下文，适合跨块综合问答。")
    lines.append("4. 语义分块保证语义完整性，但需要 embedding 模型支持，增加计算开销。")
    lines.append("5. 语义父子分块结合两者：语义父块保证上下文完整，子块精确检索。")
    lines.append("6. 结构化分块保持法规层级，对条文类文本效果好。")
    lines.append("7. 滑动窗口通过高重叠率防止答案被切断，但分块数翻倍。")
    lines.append("")

    CHUNK_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return CHUNK_REPORT_PATH


# ============ 主流程 ============

def main():
    import sys
    print("=" * 70)
    print("  高级分块策略对比评估")
    print("=" * 70)

    # 读取测试集
    print("\n步骤 1/5：加载测试集...")
    test_items = json.loads(TESTSET_PATH.read_text(encoding="utf-8"))
    print(f"  测试集: {len(test_items)} 条")

    # 读取文档
    print("\n步骤 2/5：读取知识库文档...")
    documents = load_documents()
    print(f"  文档数: {len(documents)}")

    # 初始化 embedder（语义分块需要）
    print("\n步骤 3/5：初始化 embedding 模型...")
    embedder = None
    sys.path.insert(0, str(PROJECT_ROOT / "project-root" / "backend"))
    try:
        from app.services.embedding import embedding_service
        embedder = embedding_service
        print("  embedding 模型加载完成")
    except Exception as e:
        print(f"  [警告] embedding 模型加载失败: {e}，语义分块将回退到句子合并")

    # 策略列表
    strategies = [
        ("固定500字/100重叠(基线)", lambda t: chunk_fixed_500(t), False),
        ("父子分块(Small-to-Big)", lambda t: chunk_parent_child(t), True),
        ("语义分块(Semantic)", lambda t: chunk_semantic(t, embedder=embedder), False),
        ("语义父子分块(Semantic+Parent-Child)", lambda t: chunk_semantic_parent_child(t, embedder=embedder), True),
        ("递归结构化分块", lambda t: chunk_structured(t), False),
        ("滑动窗口(50%重叠)", lambda t: chunk_sliding_window(t), False),
    ]

    # 逐策略评估
    print(f"\n步骤 4/5：逐策略评估...")
    results = {}
    for name, chunk_fn, is_pc in strategies:
        print(f"\n{'='*50}", flush=True)
        print(f"  策略: {name}", flush=True)
        print(f"{'='*50}", flush=True)
        t0 = time.perf_counter()
        results[name] = eval_strategy(
            name, documents, test_items, chunk_fn,
            embedder=embedder, is_parent_child=is_pc,
        )
        elapsed = time.perf_counter() - t0
        r = results[name]
        print(f"  Recall@5={r['recall@5']:.2%}  CP@5={r['context_precision@5']:.2%}  分块数={r['chunk_count']}  耗时={elapsed:.1f}s", flush=True)

    # 生成报告
    print(f"\n步骤 5/5：生成报告...")
    report = write_report(results)
    print(f"  报告: {report}")

    detail_path = REPORT_DIR / "chunk_eval_details.json"
    detail_path.write_text(json.dumps(
        {k: v["details"] for k, v in results.items()},
        ensure_ascii=False, indent=2
    ), encoding="utf-8")
    print(f"  明细: {detail_path}")

    print("\n" + "=" * 70)
    print("  完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
