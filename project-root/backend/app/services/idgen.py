"""隐患编号生成：HD-YYYYMMDD-XXXX，当日递增。"""
import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_hazard_id(db: AsyncSession) -> str:
    prefix = f"HD-{datetime.date.today():%Y%m%d}-"
    row = (
        await db.execute(
            text("SELECT MAX(hazard_id) FROM hazards WHERE hazard_id LIKE :p"),
            {"p": prefix + "%"},
        )
    ).scalar()
    seq = int(str(row).rsplit("-", 1)[-1]) + 1 if row else 1
    return f"{prefix}{seq:04d}"
