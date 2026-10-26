"""pytest 公共夹具：使用临时 SQLite 与临时上传目录，避免污染真实数据。"""
import asyncio
import os
import pathlib
import tempfile

_TEST_TMP = pathlib.Path(tempfile.mkdtemp(prefix="shudao_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_TMP / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_TEST_TMP / "uploads")
# 关闭 BGE 模型后台预热：加载中的线程在进程退出时会引发段错误
os.environ["PRELOAD_MODELS"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.core.database import init_db

API = settings.API_V1_PREFIX

# 测试专用同步引擎：app 运行时已全量 async 化（P4 删除了 sync 引擎），
# 同步测试函数的造数/断言走此私有引擎，与 async 引擎指向同一测试库文件
_test_engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)


# 测试造数同样启用 SQLite 外键约束，与 app 行为一致
@event.listens_for(_test_engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture()
def client():
    """同步测试客户端，启动时初始化数据库。

    drop_all / init_db 均经 async 引擎（同文件）在临时 event loop 中执行
    （async 引擎为 NullPool，无跨 loop 问题）。
    TestClient 启动时 lifespan 会再次幂等执行 init_db。
    """
    from app.models.base import Base, async_engine

    async def _reset():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(_reset())
    asyncio.run(init_db())
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    """返回指定用户的 Bearer Token 请求头。"""
    def _make(username: str = "zhangsan", password: str = "Abc@123456") -> dict:
        resp = client.post(
            f"{API}/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def db(client):
    """直接操作测试库的同步 Session（测试造数/断言专用，走私有测试引擎）。"""
    s = _TestSessionLocal()
    yield s
    s.close()
