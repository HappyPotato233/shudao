"""认证刷新与用户管理接口测试。"""
import datetime

from sqlalchemy import text

from app.core.config import settings

API = settings.API_V1_PREFIX


def _now_iso() -> str:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).isoformat(timespec="seconds")


def _token(client, username="admin", password="Abc@123456"):
    resp = client.post(f"{API}/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def test_refresh_token_returns_new_access_token(client):
    login = client.post(
        f"{API}/auth/login",
        json={"username": "zhangsan", "password": "Abc@123456"},
    )
    refresh = login.json()["data"]["refresh_token"]
    resp = client.post(f"{API}/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["access_token"]
    assert body["data"]["user"]["username"] == "zhangsan"


def test_refresh_token_invalid_returns_40103(client):
    resp = client.post(f"{API}/auth/refresh", json={"refresh_token": "bad.token.value"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 40103


def test_refresh_rotates_and_revokes_old_refresh_token(client):
    login = client.post(
        f"{API}/auth/login",
        json={"username": "zhangsan", "password": "Abc@123456"},
    ).json()["data"]

    first_refresh = login["refresh_token"]
    refreshed = client.post(
        f"{API}/auth/refresh", json={"refresh_token": first_refresh}
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["data"]["access_token"]

    me = client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {new_access}"}
    )
    assert me.status_code == 200
    assert me.json()["code"] == 0

    reused = client.post(
        f"{API}/auth/refresh", json={"refresh_token": first_refresh}
    )
    assert reused.status_code == 401
    assert reused.json()["code"] == 40103


def test_cleanup_expired_sessions_removes_expired_and_revoked(client, db):
    import asyncio

    from app.models.base import AsyncSessionLocal
    from app.services.auth_service import cleanup_expired_sessions

    db.execute(
        text(
            "INSERT INTO auth_sessions "
            "(session_id, user_id, access_jti, refresh_jti, last_active_at, "
            "access_expires_at, refresh_expires_at, revoked_at, created_at, updated_at) "
            "VALUES "
            "('auth_expired', 'U002', 'aj_expired', 'rj_expired', :now, "
            ":now, :expired, NULL, :now, :now), "
            "('auth_revoked', 'U002', 'aj_revoked', 'rj_revoked', :now, "
            ":now, :future, :now, :now, :now)"
        ),
        {
            "now": _now_iso(),
            "expired": (
                datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
                - datetime.timedelta(days=1)
            ).isoformat(timespec="seconds"),
            "future": (
                datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
                + datetime.timedelta(days=1)
            ).isoformat(timespec="seconds"),
        },
    )
    db.commit()

    # cleanup_expired_sessions 已 async 化：用临时 event loop + AsyncSession 调用
    # （async 引擎为 NullPool，跨 loop 安全；与 sync 引擎指向同一 SQLite 文件）
    async def _run_cleanup():
        async with AsyncSessionLocal() as adb:
            return await cleanup_expired_sessions(adb)

    removed = asyncio.run(_run_cleanup())

    assert removed == 2
    remaining = db.scalar(
        text(
            "SELECT COUNT(*) FROM auth_sessions "
            "WHERE session_id IN ('auth_expired', 'auth_revoked')"
        )
    )
    assert remaining == 0


def test_admin_can_create_user(client, auth_headers):
    admin = auth_headers("admin")
    resp = client.post(
        f"{API}/users",
        json={
            "username": "zhaoqi",
            "name": "赵七",
            "password": "Abc@123456",
            "role": "User",
            "department": "工程部",
            "project": "绵九高速项目",
            "phone": "13800138001",
        },
        headers=admin,
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["id"].startswith("U")
    assert resp.json()["data"]["username"] == "zhaoqi"


def test_create_user_duplicate_username_fails(client, auth_headers):
    admin = auth_headers("admin")
    resp = client.post(
        f"{API}/users",
        json={
            "username": "zhangsan",
            "name": "重复用户",
            "password": "Abc@123456",
            "role": "User",
            "department": "工程部",
            "project": "绵九高速项目",
        },
        headers=admin,
    )
    assert resp.json()["code"] == 40013


def test_create_user_weak_password_fails(client, auth_headers):
    admin = auth_headers("admin")
    resp = client.post(
        f"{API}/users",
        json={
            "username": "weakuser",
            "name": "弱密码",
            "password": "weak",
            "role": "User",
            "department": "工程部",
            "project": "绵九高速项目",
        },
        headers=admin,
    )
    assert resp.json()["code"] == 40001


def test_non_admin_cannot_create_user(client, auth_headers):
    zh = auth_headers("zhangsan")
    resp = client.post(
        f"{API}/users",
        json={
            "username": "notadmin",
            "name": "非管理员",
            "password": "Abc@123456",
            "role": "User",
            "department": "工程部",
            "project": "绵九高速项目",
        },
        headers=zh,
    )
    assert resp.json()["code"] == 40303


def test_admin_can_update_and_delete_user(client, auth_headers):
    admin = auth_headers("admin")
    created = client.post(
        f"{API}/users",
        json={
            "username": "zhaoba",
            "name": "赵八",
            "password": "Abc@123456",
            "role": "User",
            "department": "工程部",
            "project": "绵九高速项目",
        },
        headers=admin,
    )
    user_id = created.json()["data"]["id"]

    updated = client.put(
        f"{API}/users/{user_id}",
        json={"name": "赵八改", "department": "安全部", "project": "成绵高速扩容项目"},
        headers=admin,
    )
    assert updated.json()["code"] == 0
    assert updated.json()["data"]["name"] == "赵八改"
    assert updated.json()["data"]["department"] == "安全部"

    deleted = client.delete(f"{API}/users/{user_id}", headers=admin)
    assert deleted.json()["code"] == 0

    login = client.post(
        f"{API}/auth/login",
        json={"username": "zhaoba", "password": "Abc@123456"},
    )
    assert login.json()["code"] == 40102


def test_safety_officer_cannot_delete_user(client, auth_headers):
    zh = auth_headers("zhangsan")
    resp = client.delete(f"{API}/users/U003", headers=zh)
    assert resp.json()["code"] == 40303
