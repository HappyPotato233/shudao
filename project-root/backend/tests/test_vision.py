"""H09 视觉识别与标注测试"""
import cv2
import numpy as np

from app.core.config import settings

API = settings.API_V1_PREFIX


def test_ai_detect_not_configured(client, auth_headers):
    files = [("images", ("a.jpg", b"fake", "image/jpeg"))]
    resp = client.post(f"{API}/hazards/ai-detect", files=files, headers=auth_headers("lisi"))
    assert resp.json()["code"] == 40203


def test_annotate_draws_box(tmp_path):
    from app.services.annotator import annotate, imwrite_unicode

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    src = tmp_path / "a.jpg"
    imwrite_unicode(src, img)
    out = tmp_path / "out.jpg"
    items = [
        {
            "id": 1,
            "label": "临边防护缺失",
            "risk": "high",
            "bbox_norm": [0.1, 0.1, 0.5, 0.5],
            "color_bgr": [0, 0, 255],
            "conf": 0.9,
            "fix": "",
            "note": "",
        }
    ]
    drawn = annotate(src, items, out)
    assert out.exists()
    assert drawn[0]["bbox_px"] == [10, 10, 50, 50]
