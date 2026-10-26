"""用户列表接口测试（派单选人）"""
from app.core.config import settings

API = settings.API_V1_PREFIX


def test_admin_lists_all_users(client, auth_headers):
    data = client.get(f"{API}/users", headers=auth_headers("admin")).json()["data"]
    assert data["total"] >= 3


def test_employee_can_list_users(client, auth_headers):
    data = client.get(f"{API}/users", headers=auth_headers("lisi")).json()["data"]
    assert data["total"] >= 3
