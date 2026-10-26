"""KB 数据迁移：transport_safety_kb.sqlite3 → 业务库 ORM 表（P3.1）。

把独立 KB 库的 documents / evidence_units / knowledge_entries / quarantine
四张核心表全量同步到业务库 kb_* 表，供 rag.py / exam_service.py 以 ORM 访问。

幂等策略：按表先删后插，可重复执行。
row_id 语义：kb_documents 按源库 rowid 顺序写入，row_id 即源库 rowid，
exam_service 文档出题模式的 document_id 寻址行为保持不变。

2026-08-23 P4：改用 async 引擎 + AsyncSession（app 已删除 sync 引擎）。

Usage:
    python backend/scripts/migrate_kb_data.py
"""
import asyncio
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import delete

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import (
    Base,
    AsyncSessionLocal,
    KbDocument,
    KbEvidenceUnit,
    KbKnowledgeEntry,
    KbQuarantine,
    async_engine,
)

KB_PATH = BACKEND_DIR.parent / "database" / "transport_safety_kb.sqlite3"

# 表级迁移配置：源表名 -> (ORM 类, 自增承接列名或 None)
_TABLES = [
    ("documents", KbDocument, "row_id"),
    ("evidence_units", KbEvidenceUnit, None),
    ("knowledge_entries", KbKnowledgeEntry, "entry_id"),
    ("quarantine", KbQuarantine, None),
]


def _read_rows(con: sqlite3.Connection, table: str) -> list[dict]:
    """按源库 rowid 顺序读取全表，保留 rowid 供自增主键承接。"""
    con.row_factory = sqlite3.Row
    return [dict(row) for row in con.execute(f"SELECT rowid AS __rowid__, * FROM {table} ORDER BY rowid")]


async def migrate() -> dict[str, int]:
    if not KB_PATH.is_file():
        raise SystemExit(f"KB 源库不存在: {KB_PATH}")

    # 确保目标表存在（已有库追加 kb_* 表，幂等）
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    con = sqlite3.connect(f"file:{KB_PATH}?mode=ro", uri=True)
    try:
        counts: dict[str, int] = {}
        async with AsyncSessionLocal() as db:
            for table, model, seq_col in _TABLES:
                rows = _read_rows(con, table)
                await db.execute(delete(model))
                for row in rows:
                    data = {k: v for k, v in row.items() if k != "__rowid__"}
                    if seq_col:
                        # 显式指定自增主键值，保持与源库 rowid 一致
                        data[seq_col] = row["__rowid__"]
                    db.add(model(**data))
                await db.commit()
                counts[table] = len(rows)
        return counts
    finally:
        con.close()


def main() -> None:
    counts = asyncio.run(migrate())
    for table, count in counts.items():
        print(f"{table}: {count} rows migrated")
    print("KB data migration done.")


if __name__ == "__main__":
    main()
