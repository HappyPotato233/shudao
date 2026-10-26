"""上传文件存储与校验工具"""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.response import BizError, ErrorCode


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
ATTACHMENT_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".md", ".zip"}


def validate_upload(file: UploadFile, kind: str = "image") -> tuple[bytes, str]:
    """校验文件类型与大小，返回 (文件内容, 扩展名)。"""
    ext = Path(file.filename or "").suffix.lower()
    allowed = IMAGE_EXTS if kind == "image" else ATTACHMENT_EXTS
    if ext not in allowed:
        raise BizError(*ErrorCode.FILE_TYPE_NOT_ALLOWED)

    limit_mb = settings.MAX_IMAGE_SIZE_MB if kind == "image" else settings.MAX_ATTACHMENT_SIZE_MB
    data = file.file.read()
    if len(data) > limit_mb * 1024 * 1024:
        raise BizError(*ErrorCode.FILE_TOO_LARGE)
    return data, ext


def save_upload(file: UploadFile, subdir: str, kind: str = "image") -> tuple[str, int]:
    """保存上传文件到 UPLOAD_DIR/subdir，返回 (相对路径, 字节数)。"""
    data, ext = validate_upload(file, kind)
    dest_dir = Path(settings.UPLOAD_DIR) / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (dest_dir / name).write_bytes(data)
    return (Path(subdir) / name).as_posix(), len(data)


def public_url(rel_path: str | None) -> str | None:
    """把相对上传路径转为对外 URL。"""
    if not rel_path:
        return None
    return "/uploads/" + rel_path.replace("\\", "/")
