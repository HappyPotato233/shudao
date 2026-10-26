# RAG 检索评估报告（滑动窗口分块）

> 生成时间：2026-08-19 19:09:41
> 测试集规模：200 条
> 分块策略：滑动窗口 500字 / 250字重叠（50%重叠率）
> 命中判断：bigram 重合率 ≥ 0.3

## 检索指标对比（滑动窗口 vs 原始分块）

| 检索策略 | Recall@5(滑动窗口) | Recall@5(原始) | CP@5(滑动窗口) | CP@5(原始) |
|----------|-------------------|---------------|---------------|-----------|
| BM25-only | 36.50% | 82.00% | 12.40% | 18.20% |
| Vector-only | 23.50% | 67.00% | 7.80% | 14.80% |
| Hybrid(BM25+Vector) | 33.50% | 78.50% | 11.40% | 17.70% |
| Hybrid+Rerank | 34.00% | 84.50% | 11.90% | 19.20% |

## 逐策略分组命中率

- **BM25-only** / query-1chunk：R@5=38%  CP@5=14%  （120 条）
- **BM25-only** / query-2chunk：R@5=30%  CP@5=9%  （50 条）
- **BM25-only** / query-3chunk：R@5=40%  CP@5=12%  （30 条）

- **Vector-only** / query-1chunk：R@5=24%  CP@5=8%  （120 条）
- **Vector-only** / query-2chunk：R@5=22%  CP@5=8%  （50 条）
- **Vector-only** / query-3chunk：R@5=23%  CP@5=5%  （30 条）

- **Hybrid(BM25+Vector)** / query-1chunk：R@5=36%  CP@5=13%  （120 条）
- **Hybrid(BM25+Vector)** / query-2chunk：R@5=24%  CP@5=8%  （50 条）
- **Hybrid(BM25+Vector)** / query-3chunk：R@5=40%  CP@5=11%  （30 条）

- **Hybrid+Rerank** / query-1chunk：R@5=37%  CP@5=13%  （120 条）
- **Hybrid+Rerank** / query-2chunk：R@5=28%  CP@5=10%  （50 条）
- **Hybrid+Rerank** / query-3chunk：R@5=33%  CP@5=9%  （30 条）

## 结论

1. 滑动窗口分块 + BM25-only 的 Recall@5=36.50%
2. 对比原始最优策略(Hybrid+Rerank R@5=84.50%)，降低 48.0%
