"""SQLite → PostgreSQL 全量数据迁移脚本（P5.1）。

用法（在 backend 目录下执行）：
    python scripts/migrate_sqlite_to_pg.py ^
        --pg postgresql+asyncpg://postgres:<密码>@localhost:5432/shudao ^
        [--sqlite ../database/app.db] [--create-db]

流程：
    1. --create-db：先连 postgres 维护库，目标库不存在则创建（UTF8）
    2. 在 PG 上 Base.metadata.create_all 建全量表结构（幂等）
    3. 按 sorted_tables 逆序清空、正序回填 app.db 全部业务数据（先删后插，可重跑）
    4. 对自增主键 setval 校正序列，避免后续 ORM 插入主键冲突
    5. 打印 源库/目标库 各表行数核对清单

说明：
    - 主键 / ID / 时间戳字符串原样保留（Chroma 向量按 chunk_id 关联，不受影响）
    - sqlite_sequence 等 SQLite 内部表不在 ORM 元数据内，自动跳过
    - 测试环境不受影响：conftest 用环境变量把 DATABASE_URL 指回临时 SQLite
"""
import argparse
import asyncio
import pathlib
import sqlite3
import sys

# 保证能 import app 包（脚本在 backend/scripts/ 下）
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import Float, make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  触发全部模型注册到 Base.metadata
from app.models.base import Base


async def create_database_if_missing(pg_url: str) -> None:
    """连 postgres 维护库创建目标库（已存在则跳过）。"""
    import asyncpg

    url = make_url(pg_url)
    dbname = url.database
    conn = await asyncpg.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username or "postgres",
        password=url.password,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", dbname
        )
        if exists:
            print(f"[skip] 数据库 {dbname} 已存在")
        else:
            await conn.execute(f'CREATE DATABASE "{dbname}" ENCODING \'UTF8\'')
            print(f"[ok] 已创建数据库 {dbname}")
    finally:
        await conn.close()


async def migrate(pg_url: str, sqlite_path: pathlib.Path) -> None:
    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row
    engine = create_async_engine(pg_url)

    try:
        async with engine.begin() as conn:
            # 1. 建表（幂等）
            await conn.run_sync(Base.metadata.create_all)

            tables = Base.metadata.sorted_tables
            sqlite_tables = {
                r[0]
                for r in src.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

            # 2. 逆序清空（先删子表后删父表，保证可重跑）
            for t in reversed(tables):
                await conn.execute(t.delete())

            # 3. 正序回填（先插父表后插子表）
            for t in tables:
                if t.name not in sqlite_tables:
                    print(f"[warn] 源库缺少表 {t.name}，按空表处理")
                    continue
                cols = [c.name for c in t.columns]
                col_sql = ", ".join(f'"{c}"' for c in cols)
                raw = [dict(r) for r in src.execute(f'SELECT {col_sql} FROM "{t.name}"')]
                # Float 列的 int 值统一转 float（asyncpg 对浮点参数类型严格）
                float_cols = {c.name for c in t.columns if isinstance(c.type, Float)}
                rows = [
                    {k: (float(v) if k in float_cols and isinstance(v, int) else v)
                     for k, v in r.items()}
                    for r in raw
                ]
                if rows:
                    await conn.execute(t.insert(), rows)

                # 4. 自增主键序列校正（显式插入 id 不会推进 PG 序列）
                pk = next((c for c in t.primary_key.columns if c.autoincrement), None)
                if pk is not None and rows:
                    res = await conn.execute(
                        text("SELECT pg_get_serial_sequence(:t, :c)"),
                        {"t": t.name, "c": pk.name},
                    )
                    seq = res.scalar()
                    if seq:
                        max_id = max(r[pk.name] for r in rows)
                        await conn.execute(
                            text(f"SELECT setval('{seq}', {max_id})")
                        )
        print("[ok] 数据回填完成（单事务提交）")

        # 5. 行数核对清单
        print(f"\n{'表名':32s}{'SQLite':>10s}{'PG':>10s}")
        print("-" * 52)
        async with engine.connect() as conn:
            for t in tables:
                n_src = (
                    src.execute(f'SELECT COUNT(*) FROM "{t.name}"').fetchone()[0]
                    if t.name in sqlite_tables
                    else 0
                )
                res = await conn.execute(text(f'SELECT COUNT(*) FROM "{t.name}"'))
                n_pg = res.scalar()
                mark = " " if n_src == n_pg else "  <-- 不一致"
                print(f"{t.name:32s}{n_src:>10d}{n_pg:>10d}{mark}")

        extra = sqlite_tables - {t.name for t in tables}
        if extra:
            print(f"\n[skip] 源库中不在 ORM 元数据内的表：{sorted(extra)}")
    finally:
        await engine.dispose()
        src.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL 数据迁移")
    parser.add_argument(
        "--pg", required=True,
        help="目标库连接串，如 postgresql+asyncpg://postgres:pwd@localhost:5432/shudao",
    )
    parser.add_argument(
        "--sqlite", default="../database/app.db", help="源 SQLite 文件路径",
    )
    parser.add_argument(
        "--create-db", action="store_true", help="目标库不存在时先创建",
    )
    args = parser.parse_args()

    if args.create_db:
        asyncio.run(create_database_if_missing(args.pg))
    asyncio.run(migrate(args.pg, pathlib.Path(args.sqlite)))
    print("\nALL DONE")


if __name__ == "__main__":
    main()
