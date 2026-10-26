"""视觉测试集构建服务

从标注图片库（YOLO 格式：images/ + labels/ + classes.txt）中按比例抽样图片，
复制到 uploads/test_sets/{test_set_id}/images/ 下，并把标注解析为 JSON 真值
写入 ai_test_items 表，用于一键生成带标注的 vision 测试集。
"""
import json
import random
import re
import shutil
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.response import BizError

# 标注图片库子集 → 文件名前缀（避免中文路径出现在 URL 中）
SUBSET_PREFIXES = {
    "运营高速公路子集": "highway",
    "隧道施工子集": "tunnel",
    "简支梁子集": "beam",
    "加油站子集": "station",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _load_class_map(subset_dir: Path) -> dict[int, dict]:
    """读取子集的 classes.txt 与 类别说明.txt，构建 class_id → {name, name_zh} 映射。"""
    # 英文名列表（行序即 class_id）
    class_map: dict[int, dict] = {}
    classes_file = subset_dir / "classes.txt"
    if not classes_file.is_file():
        return class_map
    names = [line.strip() for line in classes_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    for idx, name in enumerate(names):
        class_map[idx] = {"name": name, "name_zh": name}

    # 中文说明（格式：`0: toll_booth  # 收费亭`），存在则覆盖 name_zh
    desc_file = subset_dir / "类别说明.txt"
    if desc_file.is_file():
        for line in desc_file.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(\d+):\s*(\S+)\s*#\s*(.+)$", line.strip())
            if m:
                cid = int(m.group(1))
                if cid in class_map:
                    class_map[cid]["name_zh"] = m.group(3).strip()
    return class_map


def _parse_label_file(label_path: Path, class_map: dict[int, dict]) -> list[dict]:
    """解析单个 YOLO 标注文件为检测框列表（保留归一化坐标 cx/cy/w/h）。"""
    detections = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            cid = int(parts[0])
            cx, cy, w, h = (float(x) for x in parts[1:5])
        except ValueError:
            continue
        info = class_map.get(cid, {"name": str(cid), "name_zh": str(cid)})
        detections.append({
            "class_id": cid,
            "name": info["name"],
            "name_zh": info["name_zh"],
            "cx": cx, "cy": cy, "w": w, "h": h,
        })
    return detections


def _collect_candidates(source_dir: Path) -> dict[str, list[dict]]:
    """收集每个子集中"图片 + 对应标注"均存在的候选条目。

    返回 {子集名: [{image_path, label_path, class_map}, ...]}，跳过无标注的图片。
    """
    result: dict[str, list[dict]] = {}
    for subset_name in SUBSET_PREFIXES:
        subset_dir = source_dir / subset_name
        images_dir = subset_dir / "images"
        labels_dir = subset_dir / "labels"
        if not (images_dir.is_dir() and labels_dir.is_dir()):
            continue
        class_map = _load_class_map(subset_dir)
        items = []
        for img in sorted(images_dir.iterdir()):
            if img.suffix.lower() not in IMAGE_EXTS:
                continue
            label = labels_dir / (img.stem + ".txt")
            if label.is_file():
                items.append({"image_path": img, "label_path": label, "class_map": class_map})
        if items:
            result[subset_name] = items
    return result


def _allocate_quota(candidates: dict[str, list[dict]], total: int) -> dict[str, int]:
    """按各子集可用图片数比例分配抽样配额（最大余数法，总量不超过可用总数）。"""
    available_total = sum(len(v) for v in candidates.values())
    if available_total <= total:
        return {name: len(v) for name, v in candidates.items()}

    # 先按比例向下取整，再把剩余名额分给余数最大的子集
    quotas = {name: len(v) * total // available_total for name, v in candidates.items()}
    remain = total - sum(quotas.values())
    remainders = sorted(
        candidates.keys(),
        key=lambda n: (len(candidates[n]) * total / available_total - quotas[n], len(candidates[n])),
        reverse=True,
    )
    for name in remainders[:remain]:
        quotas[name] += 1
    return quotas


async def build_vision_testset(db: AsyncSession, test_set_id: str, count: int = 200) -> dict:
    """主入口：从标注图片库抽样 count 张，复制图片并写入 ai_test_items。

    返回 {"total": 实际条数, "by_subset": {子集: 条数}, "target_dir": 图片目录}。
    """
    source_dir = Path(settings.ANNOTATED_IMAGE_DIR)
    if not source_dir.is_dir():
        raise BizError(40004, f"标注图片库不存在: {source_dir}")

    candidates = _collect_candidates(source_dir)
    if not candidates:
        raise BizError(40004, "标注图片库中没有可用的带标注图片")

    quotas = _allocate_quota(candidates, count)
    rng = random.Random(42)  # 固定种子保证可复现

    target_dir = Path(settings.UPLOAD_DIR) / "test_sets" / test_set_id / "images"
    target_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    by_subset: dict[str, int] = {}
    for subset_name, items in candidates.items():
        quota = quotas.get(subset_name, 0)
        if quota <= 0:
            continue
        prefix = SUBSET_PREFIXES[subset_name]
        for item in rng.sample(items, quota):
            detections = _parse_label_file(item["label_path"], item["class_map"])
            if not detections:
                continue  # 标注文件为空则跳过，保证每条真值至少有一个检测框
            # 复制图片到测试集目录（前缀+序号避免不同子集同名冲突）
            seq = by_subset.get(subset_name, 0) + 1
            by_subset[subset_name] = seq
            new_name = f"{prefix}_{seq:03d}{item['image_path'].suffix.lower()}"
            shutil.copy2(item["image_path"], target_dir / new_name)
            rows.append({
                "test_set_id": test_set_id,
                "image_path": f"test_sets/{test_set_id}/images/{new_name}",
                "ground_truth": json.dumps({
                    "source": subset_name,
                    "original_name": item["image_path"].name,
                    "detections": detections,
                }, ensure_ascii=False),
                "metadata_json": json.dumps({"subset": subset_name, "prefix": prefix}, ensure_ascii=False),
            })

    if rows:
        await db.execute(
            text("INSERT INTO ai_test_items (test_set_id, item_type, image_path, ground_truth, metadata_json) "
                 "VALUES (:test_set_id, 'image', :image_path, :ground_truth, :metadata_json)"),
            rows,
        )
    await db.execute(
        text("UPDATE ai_test_sets SET image_count = :cnt WHERE test_set_id = :id"),
        {"cnt": len(rows), "id": test_set_id},
    )
    return {"total": len(rows), "by_subset": by_subset, "target_dir": str(target_dir)}


def purge_testset_files(test_set_id: str) -> None:
    """删除测试集对应的上传图片目录（删除测试集时调用）。"""
    target_dir = Path(settings.UPLOAD_DIR) / "test_sets" / test_set_id
    if target_dir.is_dir():
        shutil.rmtree(target_dir, ignore_errors=True)

