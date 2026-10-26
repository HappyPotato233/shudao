# AI 智能助手检索策略评估报告

> 生成时间：2026-08-19 14:02:54
> 测试集规模：200 条
> 报告目录：`D:\实习\shudao\test\test_report`

## 一、测试集构成

| 分组 | 数量 | 说明 |
|------|------|------|
| query-1chunk | 120 | 答案在单个证据块 |
| query-2chunk | 50 | 答案跨 2 个证据块 |
| query-3chunk | 30 | 答案跨 3 个证据块 |

去重策略：按 content_hash 去重，重复率 0%（≤5% 要求满足）。

## 二、检索指标（全量 200 条）

| 检索策略 | Recall@5 | Context Precision@5 | 耗时(s) |
|----------|----------|---------------------|---------|
| BM25-only | 82.00% | 18.20% | 4.5 |
| Vector-only | 67.00% | 14.80% | 4.5 |
| Hybrid(BM25+Vector) | 78.50% | 17.70% | 6.0 |
| Hybrid+Rerank | 84.50% | 19.20% | 62.4 |

- **Recall@5**：Top-5 检索结果中是否命中目标证据块（业务使用 top_k=5）
- **Context Precision@5**：Top-5 中命中目标块的比例（越高越精确）

## 三、逐策略分组命中率

- **BM25-only** / query-1chunk：R@5=79%  CP@5=16%  （120 条）
- **BM25-only** / query-2chunk：R@5=80%  CP@5=20%  （50 条）
- **BM25-only** / query-3chunk：R@5=97%  CP@5=25%  （30 条）

- **Vector-only** / query-1chunk：R@5=61%  CP@5=12%  （120 条）
- **Vector-only** / query-2chunk：R@5=72%  CP@5=17%  （50 条）
- **Vector-only** / query-3chunk：R@5=83%  CP@5=21%  （30 条）

- **Hybrid(BM25+Vector)** / query-1chunk：R@5=74%  CP@5=15%  （120 条）
- **Hybrid(BM25+Vector)** / query-2chunk：R@5=80%  CP@5=20%  （50 条）
- **Hybrid(BM25+Vector)** / query-3chunk：R@5=93%  CP@5=26%  （30 条）

- **Hybrid+Rerank** / query-1chunk：R@5=82%  CP@5=16%  （120 条）
- **Hybrid+Rerank** / query-2chunk：R@5=86%  CP@5=21%  （50 条）
- **Hybrid+Rerank** / query-3chunk：R@5=93%  CP@5=27%  （30 条）

## 四、LLM 生成质量评估（忠实度 + 响应相关性）

> 评估方式：每策略抽样 50 条，用 LLM 基于检索证据生成答案并自评

| 检索策略 | 忠实度 | 响应相关性 | 样本数 |
|----------|--------|------------|--------|
| BM25-only | 1.000 | 0.852 | 50 |
| Vector-only | 1.000 | 0.844 | 50 |
| Hybrid(BM25+Vector) | 1.000 | 0.958 | 50 |
| Hybrid+Rerank | 0.998 | 0.906 | 50 |

- **忠实度（Faithfulness）**：答案中的陈述是否都能在检索证据中找到支持（0-1，越高越好）
- **响应相关性（Answer Relevance）**：答案是否直接回答了问题（0-1，越高越好）

## 五、结论与建议

1. 检索召回最优策略为 **Hybrid+Rerank**（Recall@5=84.50%）。
2. 忠实度最优：**BM25-only**（1.000）。
3. 响应相关性最优：**Hybrid(BM25+Vector)**（0.958）。

> 逐条测试明细见：`test_detail_log.json`
> LLM 评估明细见：`llm_eval_details.json`
