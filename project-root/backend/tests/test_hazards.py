"""隐患管理模块接口测试（新权限模型：仅 User 可管理隐患）"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

API = settings.API_V1_PREFIX
LONG_MEASURES = "已设置临时防护并安装正式护栏，经复查验收合格完成整改"

# 动态未来截止日期（+30 天），避免硬编码日期过期导致"整改截止日期不合法"
_FUTURE_DEADLINE = (
    datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=30)
).isoformat(timespec="seconds")


def _report(client, headers, **overrides):
    data = {
        "title": "临边防护缺失",
        "description": "桥墩施工区域临边护栏缺失约5米",
        "level": "major",
        "category": "edge_protection",
        "location": "K12+350",
        "occurred_at": "2026-08-12T09:30:00+08:00",
        "project": "成绵高速扩容项目",
    }
    data.update(overrides)
    files = [("images", ("a.jpg", b"fake-image", "image/jpeg"))]
    resp = client.post(f"{API}/hazards", data=data, files=files, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["hazard_id"]


def _assign(client, headers, hazard_id, assignee_id="U005", deadline=_FUTURE_DEADLINE):
    return client.post(
        f"{API}/hazards/{hazard_id}/assign",
        data={
            "assignee_id": assignee_id,
            "requirements": "立即设置临时防护并安装正式护栏",
            "deadline": deadline,
            "priority": "high",
        },
        headers=headers,
    )


def _rectify(client, headers, hazard_id, measures=LONG_MEASURES):
    files = [("images_after", ("after.jpg", b"fake-image", "image/jpeg"))]
    return client.post(
        f"{API}/hazards/{hazard_id}/rectify",
        data={"measures": measures},
        files=files,
        headers=headers,
    )


def test_report_creates_pending(client, auth_headers):
    hid = _report(client, auth_headers("lisi"))
    assert hid.startswith("HD-")
    detail = client.get(f"{API}/hazards/{hid}", headers=auth_headers("lisi")).json()["data"]
    assert detail["status"] == "pending"
    assert detail["reporter"]["name"] == "李四"


def test_employee_sees_only_own(client, auth_headers):
    li = auth_headers("lisi")
    zhao = auth_headers("zhaoliu")
    hid_li = _report(client, li, title="li", project="成绵高速扩容项目")
    hid_zhao = _report(client, zhao, title="zhao", project="成绵高速扩容项目")
    ids = [i["hazard_id"] for i in client.get(f"{API}/hazards", headers=li).json()["data"]["items"]]
    assert hid_li in ids
    assert hid_zhao not in ids


def test_admin_can_list_all_hazards(client, auth_headers):
    """管理员放权后可访问隐患列表，且能查看全部用户上报的隐患。"""
    li = auth_headers("lisi")
    zhao = auth_headers("zhaoliu")
    hid_li = _report(client, li)
    hid_zhao = _report(client, zhao)

    admin = auth_headers("admin")
    resp = client.get(f"{API}/hazards", headers=admin)
    assert resp.json()["code"] == 0
    ids = [i["hazard_id"] for i in resp.json()["data"]["items"]]
    assert hid_li in ids
    assert hid_zhao in ids


def test_employee_cannot_assign_others_hazard(client, auth_headers):
    li = auth_headers("lisi")
    zhao = auth_headers("zhaoliu")
    hid = _report(client, li)
    resp = _assign(client, zhao, hid)
    assert resp.json()["code"] == 40301


def test_assign_transitions_and_notifies(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    resp = _assign(client, li, hid)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "processing"
    items = client.get(f"{API}/notifications", headers=auth_headers("zhaoliu")).json()["data"]["items"]
    assert any(n["type"] == "hazard_assigned" and n["target_id"] == hid for n in items)


def test_assign_again_fails(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    assert _assign(client, li, hid).status_code == 200
    resp = _assign(client, li, hid)
    assert resp.json()["code"] == 40004


def test_critical_deadline_exceeds_seven_days(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li, level="critical")
    # 重大隐患期限必须 <=7 天：用 +10 天的动态日期，保证永远超限（硬编码日期会随时间失效）
    exceed = (
        datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=10)
    ).isoformat(timespec="seconds")
    resp = _assign(client, li, hid, deadline=exceed)
    assert resp.json()["code"] == 40006


def test_rectify_validation(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    _assign(client, li, hid)
    zhao = auth_headers("zhaoliu")
    short = _rectify(client, zhao, hid, measures="太短")
    assert short.json()["code"] == 40008
    no_img = client.post(
        f"{API}/hazards/{hid}/rectify",
        data={"measures": LONG_MEASURES},
        headers=zhao,
    )
    assert no_img.json()["code"] == 40009


def test_rectify_transitions(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    _assign(client, li, hid)
    resp = _rectify(client, auth_headers("zhaoliu"), hid)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending_review"


def test_review_reject_requires_reason(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    _assign(client, li, hid)
    _rectify(client, auth_headers("zhaoliu"), hid)
    resp = client.post(f"{API}/hazards/{hid}/review", json={"result": "rejected"}, headers=li)
    assert resp.json()["code"] == 40011


def test_review_approve_closes(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    _assign(client, li, hid)
    _rectify(client, auth_headers("zhaoliu"), hid)
    resp = client.post(f"{API}/hazards/{hid}/review", json={"result": "approved"}, headers=li)
    assert resp.json()["data"]["status"] == "closed"


def test_review_wrong_state(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    resp = client.post(f"{API}/hazards/{hid}/review", json={"result": "approved"}, headers=li)
    assert resp.json()["code"] == 40010


def test_report_with_ai_detections(client, auth_headers, tmp_path):
    """上报时携带 AI 检测结果：应写入 hazard_detections 并生成标注图，H03 可查看。"""
    import json

    import cv2
    import numpy as np
    from app.services.annotator import imwrite_unicode

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[20:60, 20:60] = (0, 0, 255)
    photo = tmp_path / "a.jpg"
    imwrite_unicode(photo, img)

    detections_json = json.dumps(
        [
            {
                "image_index": 0,
                "detections": [
                    {
                        "id": 1,
                        "label": "临边防护缺失",
                        "risk": "high",
                        "bbox_norm": [0.2, 0.2, 0.6, 0.6],
                        "color_bgr": [0, 0, 255],
                        "conf": 0.9,
                        "fix": "立即设置临时防护",
                        "note": "测试点位",
                    }
                ],
            }
        ],
        ensure_ascii=False,
    )

    resp = client.post(
        f"{API}/hazards",
        data={
            "title": "临边防护缺失",
            "description": "桥墩施工区域临边护栏缺失约5米",
            "level": "major",
            "category": "edge_protection",
            "location": "K12+350",
            "occurred_at": "2026-08-12T09:30:00+08:00",
            "project": "成绵高速扩容项目",
            "detections_json": detections_json,
        },
        files=[("images", ("a.jpg", photo.read_bytes(), "image/jpeg"))],
        headers=auth_headers("lisi"),
    )
    assert resp.status_code == 200, resp.text
    hid = resp.json()["data"]["hazard_id"]

    detail = client.get(f"{API}/hazards/{hid}", headers=auth_headers("lisi")).json()["data"]
    assert len(detail["media"]["detections"]) == 1
    assert detail["media"]["detections"][0]["label"] == "临边防护缺失"
    assert len(detail["media"]["annotated_images"]) == 1


def test_report_rejects_bad_file_type(client, auth_headers):
    resp = client.post(
        f"{API}/hazards",
        data={
            "title": "x",
            "description": "x",
            "level": "major",
            "category": "edge_protection",
            "location": "x",
            "occurred_at": "2026-08-14T09:00:00+08:00",
            "project": "成绵高速扩容项目",
        },
        files=[("images", ("evil.exe", b"x", "application/octet-stream"))],
        headers=auth_headers("lisi"),
    )
    assert resp.json()["code"] == 40020


def test_report_rejects_too_many_images(client, auth_headers):
    files = [("images", (f"{i}.jpg", b"x", "image/jpeg")) for i in range(10)]
    resp = client.post(
        f"{API}/hazards",
        data={
            "title": "x",
            "description": "x",
            "level": "major",
            "category": "edge_protection",
            "location": "x",
            "occurred_at": "2026-08-14T09:00:00+08:00",
            "project": "成绵高速扩容项目",
        },
        files=files,
        headers=auth_headers("lisi"),
    )
    assert resp.json()["code"] == 40002


def test_report_rejects_oversize(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "MAX_IMAGE_SIZE_MB", 0)
    resp = client.post(
        f"{API}/hazards",
        data={
            "title": "x",
            "description": "x",
            "level": "major",
            "category": "edge_protection",
            "location": "x",
            "occurred_at": "2026-08-14T09:00:00+08:00",
            "project": "成绵高速扩容项目",
        },
        files=[("images", ("a.jpg", b"x", "image/jpeg"))],
        headers=auth_headers("lisi"),
    )
    assert resp.json()["code"] == 41300


def test_assign_and_rectify_with_attachments(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)
    assign = client.post(
        f"{API}/hazards/{hid}/assign",
        data={
            "assignee_id": "U005",
            "requirements": "立即设置临时防护并安装正式护栏",
            "deadline": _FUTURE_DEADLINE,
            "priority": "high",
        },
        files=[("attachments", ("guide.txt", b"guidance", "text/plain"))],
        headers=li,
    )
    assert assign.status_code == 200
    detail = client.get(f"{API}/hazards/{hid}", headers=li).json()["data"]
    assert detail["assignment"]["attachments"]

    zhao = auth_headers("zhaoliu")
    rect = client.post(
        f"{API}/hazards/{hid}/rectify",
        data={"measures": LONG_MEASURES},
        files=[
            ("images_after", ("after.jpg", b"x", "image/jpeg")),
            ("attachments", ("proof.txt", b"proof", "text/plain")),
        ],
        headers=zhao,
    )
    assert rect.status_code == 200
    detail = client.get(f"{API}/hazards/{hid}", headers=li).json()["data"]
    assert detail["rectification"]["attachments"]


def test_export_hazard_pdf_returns_pdf_file(client, auth_headers):
    li = auth_headers("lisi")
    hid = _report(client, li)

    resp = client.get(f"{API}/hazards/{hid}/export?format=pdf", headers=li)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert f"attachment; filename={hid}.pdf" in resp.headers["content-disposition"]


def test_export_hazard_pdf_enforces_data_scope(client, auth_headers):
    li = auth_headers("lisi")
    zhao = auth_headers("zhaoliu")
    hid = _report(client, li)

    resp = client.get(f"{API}/hazards/{hid}/export?format=pdf", headers=zhao)

    assert resp.status_code == 403
    assert resp.json()["code"] == 40301
