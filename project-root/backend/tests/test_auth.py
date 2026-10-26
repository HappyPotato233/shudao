"""认证模块接口测试 - 对齐 API.md 2.1~2.4

覆盖：
- 登录成功 / 密码错误 / 账户禁用 / 用户不存在 / 参数校验
- /auth/me 鉴权（无 token / 无效 token / 有效 token）
- /auth/logout（无 token / 成功登出 / 登出后 token 失效）
"""
from __future__ import annotations

import datetime

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings

API = settings.API_V1_PREFIX


def _now_iso() -> str:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).isoformat(timespec="seconds")


def _shift_iso(value: str, minutes: int) -> str:
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    return (dt + datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds")


# -------------------- 登录 --------------------

class TestLogin:
    def test_login_success(self, client: TestClient):
        """登录成功：返回 access_token/refresh_token/expires_in/user"""
        resp = client.post(f"{API}/auth/login", json={"username": "zhangsan", "password": "Abc@123456"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        user = data["user"]
        assert user["id"] == "U002"
        assert user["username"] == "zhangsan"
        assert user["name"] == "张三"
        assert user["role"] == "User"
        assert user["department"] == "安全生产部"
        assert user["project"] == "成绵高速扩容项目"

    def test_login_wrong_password(self, client: TestClient):
        """密码错误 → 40101"""
        resp = client.post(f"{API}/auth/login", json={"username": "zhangsan", "password": "Wrong@123"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 40101

    def test_login_user_not_found(self, client: TestClient):
        """用户不存在 → 40101（避免暴露用户是否存在）"""
        resp = client.post(f"{API}/auth/login", json={"username": "nobody", "password": "Abc@123456"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 40101

    def test_login_disabled_account(self, client: TestClient):
        """账户已被禁用 → 40102"""
        resp = client.post(f"{API}/auth/login", json={"username": "wangwu", "password": "Abc@123456"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 40102

    def test_login_missing_password(self, client: TestClient):
        """缺少必填字段 → 40001"""
        resp = client.post(f"{API}/auth/login", json={"username": "zhangsan"})
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001

    def test_login_empty_body(self, client: TestClient):
        """空请求体 → 40001"""
        resp = client.post(f"{API}/auth/login", json={})
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001


# -------------------- 当前用户 --------------------

class TestMe:
    def _token(self, client: TestClient, username="zhangsan") -> str:
        resp = client.post(f"{API}/auth/login", json={"username": username, "password": "Abc@123456"})
        return resp.json()["data"]["access_token"]

    def test_me_without_token(self, client: TestClient):
        """未携带 Token → 40100"""
        resp = client.get(f"{API}/auth/me")
        assert resp.status_code == 401
        assert resp.json()["code"] == 40100

    def test_me_invalid_token(self, client: TestClient):
        """Token 无效 → 40100"""
        resp = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not.a.valid.token"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 40100

    def test_me_success(self, client: TestClient):
        """携带有效 Token → 返回当前用户信息"""
        token = self._token(client)
        resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["username"] == "zhangsan"
        assert body["data"]["role"] == "User"


# -------------------- 登出 --------------------

class TestLogout:
    def _token(self, client: TestClient, username="zhangsan") -> str:
        resp = client.post(f"{API}/auth/login", json={"username": username, "password": "Abc@123456"})
        return resp.json()["data"]["access_token"]

    def test_logout_without_token(self, client: TestClient):
        """未携带 Token → 40100"""
        resp = client.post(f"{API}/auth/logout")
        assert resp.status_code == 401
        assert resp.json()["code"] == 40100

    def test_logout_success(self, client: TestClient):
        """登出成功 → code 0"""
        token = self._token(client)
        resp = client.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "已退出登录" in body["message"]

    def test_token_invalid_after_logout(self, client: TestClient):
        """登出后原 Token 失效 → /auth/me 返回 401"""
        token = self._token(client)
        # 先登出
        client.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
        # 再用同一 Token 访问 /me
        resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 40100


class TestPassword:
    def test_change_password_success(self, client: TestClient):
        resp = client.post(f"{API}/auth/login", json={"username": "zhangsan", "password": "Abc@123456"})
        token = resp.json()["data"]["access_token"]
        r = client.put(
            f"{API}/auth/password",
            json={"old_password": "Abc@123456", "new_password": "Xyz@654321"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == 0
        login = client.post(f"{API}/auth/login", json={"username": "zhangsan", "password": "Xyz@654321"})
        assert login.json()["code"] == 0

    def test_change_password_wrong_old(self, client: TestClient):
        resp = client.post(f"{API}/auth/login", json={"username": "zhangsan", "password": "Abc@123456"})
        token = resp.json()["data"]["access_token"]
        r = client.put(
            f"{API}/auth/password",
            json={"old_password": "Wrong@123", "new_password": "Xyz@654321"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == 40104

    def test_change_password_weak(self, client: TestClient):
        resp = client.post(f"{API}/auth/login", json={"username": "zhangsan", "password": "Abc@123456"})
        token = resp.json()["data"]["access_token"]
        r = client.put(
            f"{API}/auth/password",
            json={"old_password": "Abc@123456", "new_password": "weakpass"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["code"] == 40001


def test_login_creates_persistent_auth_session(client, db):
    client.post(
        f"{API}/auth/login",
        json={"username": "zhangsan", "password": "Abc@123456"},
    )

    row = db.execute(
        text(
            "SELECT session_id, user_id, access_jti, refresh_jti, revoked_at "
            "FROM auth_sessions WHERE user_id = 'U002' ORDER BY created_at DESC LIMIT 1"
        )
    ).fetchone()
    assert row is not None
    assert row.user_id == "U002"
    assert row.access_jti
    assert row.refresh_jti
    assert row.revoked_at is None

    last_login = db.scalar(text("SELECT last_login_at FROM users WHERE user_id = 'U002'"))
    assert last_login is not None


def test_logout_persists_revoked_session(client, auth_headers, db):
    token = auth_headers("zhangsan")["Authorization"].split(" ", 1)[1]
    client.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})

    revoked = db.scalar(
        text("SELECT revoked_at FROM auth_sessions WHERE user_id = 'U002'")
    )
    assert revoked is not None

    resp = client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 40100


def test_multiple_logins_are_independent(client):
    first = client.post(
        f"{API}/auth/login",
        json={"username": "zhangsan", "password": "Abc@123456"},
    ).json()["data"]
    second = client.post(
        f"{API}/auth/login",
        json={"username": "zhangsan", "password": "Abc@123456"},
    ).json()["data"]

    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    assert client.get(f"{API}/auth/me", headers=first_headers).status_code == 200
    assert client.get(f"{API}/auth/me", headers=second_headers).status_code == 200

    client.post(f"{API}/auth/logout", headers=first_headers)

    assert client.get(f"{API}/auth/me", headers=first_headers).json()["code"] == 40100
    assert client.get(f"{API}/auth/me", headers=second_headers).json()["code"] == 0


def test_idle_timeout_returns_40100(client, auth_headers, db):
    token = auth_headers("zhangsan")["Authorization"].split(" ", 1)[1]
    old = _shift_iso(_now_iso(), -31)
    db.execute(
        text("UPDATE auth_sessions SET last_active_at = :last_active_at WHERE user_id = 'U002'"),
        {"last_active_at": old},
    )
    db.commit()

    resp = client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 40100


def test_activity_updates_last_active_at(client, auth_headers, db):
    token = auth_headers("zhangsan")["Authorization"].split(" ", 1)[1]
    old = _shift_iso(_now_iso(), -2)
    db.execute(
        text("UPDATE auth_sessions SET last_active_at = :last_active_at WHERE user_id = 'U002'"),
        {"last_active_at": old},
    )
    db.commit()

    resp = client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200

    updated = db.scalar(
        text("SELECT last_active_at FROM auth_sessions WHERE user_id = 'U002'")
    )
    assert updated > old
