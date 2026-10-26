"""敏感词过滤：基于 DFA（trie）的输入拦截与输出脱敏。"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_orm import SensitiveWord


@dataclass
class FilterResult:
    passed: bool
    text: str
    matched: list[str] = field(default_factory=list)


class SensitiveWordFilter:
    """从 sensitive_words 表加载词库，用 DFA 匹配。

    - filter_input：命中敏感词 -> passed=False（用于请求前置拦截）。
    - filter_output：把命中的敏感词替换为 ``***``（用于回答后置脱敏）。
    """

    def __init__(self, words: list[str] | None = None):
        self._words: list[str] = []
        self._root: dict = {}
        if words is not None:
            self._words = [w for w in words if w]
            self._build(self._words)

    @classmethod
    async def load_async(cls, db: AsyncSession) -> "SensitiveWordFilter":
        """异步加载词库（AsyncSession 场景使用）。"""
        rows = (
            await db.scalars(
                select(SensitiveWord.word)
                .where(SensitiveWord.is_active == 1)
                .order_by(SensitiveWord.word_id)
            )
        ).all()
        return cls(words=list(rows))

    def _build(self, words: list[str]) -> None:
        root: dict = {}
        for word in words:
            node = root
            for ch in word:
                node = node.setdefault(ch, {})
            node["#"] = True
        self._root = root

    def _match_ranges(self, text: str) -> list[tuple[int, int, str]]:
        """返回 (start, end_exclusive, word) 的命中区间列表。"""
        matches: list[tuple[int, int, str]] = []
        n = len(text)
        for i in range(n):
            node = self._root
            j = i
            while j < n and text[j] in node:
                node = node[text[j]]
                j += 1
                if "#" in node:
                    matches.append((i, j, text[i:j]))
        return matches

    def filter_input(self, text: str) -> FilterResult:
        matches = self._match_ranges(text or "")
        if not matches:
            return FilterResult(passed=True, text=text)
        return FilterResult(passed=False, text=text, matched=[m[2] for m in matches])

    def filter_output(self, text: str) -> FilterResult:
        matches = self._match_ranges(text or "")
        if not matches:
            return FilterResult(passed=True, text=text)

        # 按区间替换，重叠区间简单去重（DFA 扫描顺序天然靠前）。
        chars = list(text)
        for start, end, word in matches:
            if all(chars[k] != "" for k in range(start, end)):
                chars[start] = "***"
                for k in range(start + 1, end):
                    chars[k] = ""
        return FilterResult(
            passed=True,
            text="".join(chars),
            matched=[m[2] for m in matches],
        )
