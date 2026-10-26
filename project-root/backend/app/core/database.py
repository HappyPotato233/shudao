"""数据库初始化管理

提供 init_db() 函数（async）：用 Base.metadata.create_all 建表（跨库通用，
SQLite/PostgreSQL 一致），再幂等预置种子数据（角色/敏感词/用户/考试分类）。

2026-08-21 async 改造：弃用 schema.sql + executescript（SQLite 专属 DDL），
表结构以 ORM 为唯一事实来源；种子数据改为"先查后插"幂等写法。
schema.sql 与 ORM 的差异（CHECK 约束、二级索引）已确认可接受：
- CHECK 约束：业务校验在 service 层实现
- 索引：当前数据量小，性能无影响，后续可按需在 ORM 中加 index=True
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Base,
    async_engine,
    AsyncSessionLocal,
    Role,
    User,
    QuestionCategory,
    Question,
    SensitiveWord,
    RagConfig,
)
from app.core.security import hash_password


_SEED_USERS = [
    ("U001", "admin", "系统管理员", 1, "信息中心", "蜀道集团总部", 1),
    ("U002", "zhangsan", "张三", 2, "安全生产部", "成绵高速扩容项目", 1),
    ("U003", "lisi", "李四", 2, "工程部", "绵九高速项目", 1),
    ("U004", "wangwu", "王五", 2, "工程部", "绵九高速项目", 0),
    ("U005", "zhaoliu", "赵六", 2, "工程部", "成绵高速扩容项目", 1),
]

_SEED_SENSITIVE_WORDS = [
    ("赌博", "illegal", 1),
    ("毒品", "illegal", 1),
    ("色情", "pornography", 1),
    ("暴力袭击", "violence", 1),
]

# 默认 RAG 配置（对齐 schema.sql 的 INSERT OR IGNORE 种子）
_SEED_RAG_CONFIG = [
    ("chunk_size", "500", "文档分块大小（字符数）"),
    ("chunk_overlap", "50", "分块重叠字符数"),
    ("retrieval_top_k", "5", "检索返回 Top-K 条"),
    ("similarity_threshold", "0.7", "相似度阈值"),
    ("rerank_enabled", "1", "是否启用重排序"),
    ("hybrid_search_enabled", "0", "是否启用混合检索"),
    ("hybrid_keyword_weight", "0.3", "混合检索中关键词权重"),
]


async def _seed_roles(db: AsyncSession):
    """预置角色（幂等）：Admin / User 两角色模型。"""
    for role_id, name, description in [
        (1, "Admin", "系统管理员，拥有最高权限"),
        (2, "User", "普通用户，可操作本人数据"),
    ]:
        exists = await db.get(Role, role_id)
        if exists is None:
            db.add(Role(role_id=role_id, name=name, description=description))


async def _seed_sensitive_words(db: AsyncSession):
    """预置示例敏感词（幂等）。"""
    for word, category, is_active in _SEED_SENSITIVE_WORDS:
        exists = (
            await db.execute(
                select(SensitiveWord).where(SensitiveWord.word == word)
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(SensitiveWord(word=word, category=category, is_active=is_active))


async def _seed_users(db: AsyncSession):
    """预置用户（幂等），密码统一为 Abc@123456。"""
    pwd_hash = hash_password("Abc@123456")
    for user_id, username, name, role_id, department, project, is_active in _SEED_USERS:
        exists = await db.get(User, user_id)
        if exists is None:
            db.add(
                User(
                    user_id=user_id,
                    username=username,
                    password_hash=pwd_hash,
                    name=name,
                    role_id=role_id,
                    department=department,
                    project=project,
                    is_active=is_active,
                )
            )


async def _seed_exam(db: AsyncSession):
    """预置考试分类和少量已发布题目（幂等），保证首次使用即可组卷。"""
    category_count = (
        await db.execute(select(QuestionCategory).limit(1))
    ).scalar_one_or_none()
    if category_count is None:
        db.add(QuestionCategory(name="法律法规", level=1, sort_order=1))
        db.add(QuestionCategory(name="高处作业", level=1, sort_order=2))
        db.add(QuestionCategory(name="消防安全", level=1, sort_order=3))
        await db.flush()  # 生成自增 category_id 供题目引用

    question_count = (
        await db.execute(select(Question).limit(1))
    ).scalar_one_or_none()
    if question_count is not None:
        return

    # 重新查询分类，按 sort_order 取 id
    categories = (
        await db.execute(
            select(QuestionCategory).order_by(QuestionCategory.sort_order)
        )
    ).scalars().all()
    cat_ids = [c.category_id for c in categories]  # [法律法规, 高处作业, 消防安全]

    seed_questions = [
        (
            "single_choice",
            "根据《安全生产法》，从业人员有权对本单位安全生产工作中存在的问题提出批评、(  )、控告。",
            '{"A":"检举","B":"举报","C":"投诉","D":"建议"}',
            "B",
            "根据《安全生产法》第五十七条，从业人员有权提出批评、检举、控告。",
            2,
            "easy",
            '["安全生产法","从业人员权利"]',
        ),
        (
            "true_false",
            "高处作业人员应按规定正确佩戴和使用安全防护用品。",
            None,
            "正确",
            "《建筑施工高处作业安全技术规范》要求高处作业人员正确使用安全防护用品。",
            2,
            "easy",
            '["高处作业","安全带"]',
        ),
        (
            "single_choice",
            "使用干粉灭火器灭火时，应对准火焰的哪个部位喷射？",
            '{"A":"顶部","B":"中部","C":"根部","D":"任意部位"}',
            "C",
            "灭火器应对准火焰根部喷射，由近及远推进。",
            2,
            "easy",
            '["消防安全","灭火器"]',
        ),
        (
            "multi_choice",
            "下列属于高处作业安全防护用品的有哪些？",
            '{"A":"安全带","B":"安全帽","C":"安全网","D":"普通布鞋"}',
            "ABC",
            "安全带、安全帽、安全网是高处作业常见防护用品。",
            3,
            "medium",
            '["高处作业","防护用品"]',
        ),
        (
            "true_false",
            "重大事故隐患必须立即整改。",
            None,
            "正确",
            "重大隐患可能导致重大事故，应按规定立即整改。",
            2,
            "easy",
            '["隐患管理"]',
        ),
        (
            "single_choice",
            "施工现场临时用电应优先采用什么系统？",
            '{"A":"TT系统","B":"TN-S系统","C":"IT系统","D":"随意选择"}',
            "B",
            "施工现场临时用电通常采用 TN-S 三相五线制系统。",
            2,
            "medium",
            '["临时用电"]',
        ),
    ]
    # category_id 依序映射：法律法规=cat_ids[0]，高处作业=cat_ids[1]，消防安全=cat_ids[2]
    cat_map = [
        cat_ids[0],  # 安全生产法
        cat_ids[1],  # 高处作业防护
        cat_ids[2],  # 灭火器
        cat_ids[1],  # 防护用品
        cat_ids[0],  # 隐患管理 → 法律法规
        cat_ids[0],  # 临时用电 → 法律法规
    ]
    for row, category_id in zip(seed_questions, cat_map):
        db.add(
            Question(
                type=row[0],
                content=row[1],
                options_json=row[2],
                answer=row[3],
                explanation=row[4],
                score=row[5],
                difficulty=row[6],
                category_id=category_id,
                tags_json=row[7],
                status="published",
                source="manual",
                created_by="U002",
            )
        )


async def _migrate_roles(db: AsyncSession):
    """角色模型归一迁移：旧三角色（SafetyOfficer/Employee）→ 两角色（Admin/User）。

    2026-08-17 权限重构后 roles 仅保留 Admin/User，但早期建库数据仍是三角色，
    需在此归一：role_id=2 改名 User，role_id=3 的用户并入 role_id=2 后删除该角色。
    幂等，新库不触发。
    """
    renamed = (
        await db.execute(
            Role.__table__.update()
            .where(Role.role_id == 2)
            .where(Role.name != "User")
            .values(name="User", description="普通用户，可操作本人数据")
        )
    ).rowcount
    moved = (
        await db.execute(
            User.__table__.update().where(User.role_id == 3).values(role_id=2)
        )
    ).rowcount
    removed = (
        await db.execute(
            Role.__table__.delete().where(Role.role_id == 3)
        )
    ).rowcount
    if renamed or moved or removed:
        print(f"[init_db] 角色模型已迁移为 Admin/User"
              f"（改角色名 {renamed}，迁移用户 {moved}，删除旧角色 {removed}）")


async def _seed_rag_config(db: AsyncSession):
    """预置默认 RAG 配置（幂等），已有键不覆盖。"""
    for key, value, description in _SEED_RAG_CONFIG:
        exists = (
            await db.execute(select(RagConfig).where(RagConfig.config_key == key))
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                RagConfig(config_key=key, config_value=value, description=description)
            )


async def init_db():
    """建表 + 幂等预置种子数据（async，跨库通用）

    1. Base.metadata.create_all：表已存在则跳过（幂等）
    2. 种子数据：先查后插，重复执行无副作用
    """
    # 1. 建表（表存在则跳过）
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 种子数据（独立事务，失败不影响建表）
    async with AsyncSessionLocal() as db:
        await _migrate_roles(db)
        await _seed_roles(db)
        await _seed_sensitive_words(db)
        await _seed_rag_config(db)
        await _seed_users(db)
        await _seed_exam(db)
        await db.commit()

    print("[init_db] 数据库初始化完成")


if __name__ == "__main__":
    asyncio.run(init_db())
