"""统一响应与异常处理 - 对齐 API.md 1.2 统一响应结构"""
from typing import Any, Generic, TypeVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应结构：{code, message, data, timestamp}"""

    code: int = 0
    message: str = "success"
    data: T | None = None
    timestamp: int = Field(default_factory=lambda: int(__import__("time").time()))


def success(data: Any = None, message: str = "success") -> dict:
    """构造成功响应 dict（便于直接 return）"""
    return {"code": 0, "message": message, "data": data, "timestamp": int(__import__("time").time())}


# -------------------- 业务异常 --------------------

class BizError(Exception):
    """业务异常，携带业务错误码与 HTTP 状态码"""

    def __init__(self, code: int, message: str, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


# 业务错误码常量（对齐 API.md 附录）
class ErrorCode:
    # 认证 401xx
    BAD_CREDENTIALS = (40101, "用户名或密码错误", 401)
    ACCOUNT_DISABLED = (40102, "账户已被禁用", 401)
    REFRESH_TOKEN_INVALID = (40103, "refresh_token 无效或已过期", 401)
    OLD_PASSWORD_ERROR = (40104, "旧密码错误", 400)  # 保留给修改密码接口
    UNAUTHORIZED = (40100, "未认证或 Token 过期", 401)  # 统一未认证错误码
    TOKEN_INVALID = (40100, "Token 无效", 401)  # 合并到 40100
    # 通用 400xx
    VALIDATION_FAILED = (40001, "参数校验失败", 400)
    IMAGE_COUNT_EXCEEDED = (40002, "图片数量超限（最多 9 张）", 400)
    FILE_TYPE_NOT_ALLOWED = (40020, "不支持的文件类型", 400)

    # 隐患业务 400xx（对齐 API.md 附录）
    STATUS_NOT_ASSIGNABLE = (40004, "隐患状态不允许派单", 400)
    INVALID_DEADLINE = (40005, "整改截止日期不合法", 400)
    CRITICAL_DEADLINE = (40006, "重大隐患整改期限不得超过 7 天", 400)
    STATUS_NOT_RECTIFIABLE = (40007, "隐患状态不允许提交整改", 400)
    MEASURES_TOO_SHORT = (40008, "整改描述不足 20 字", 400)
    NO_RECTIFY_IMAGES = (40009, "未上传整改后照片", 400)
    STATUS_NOT_REVIEWABLE = (40010, "隐患状态不允许验收", 400)
    REJECT_NEEDS_REASON = (40011, "驳回时必须填写原因（≥10 字）", 400)
    DUPLICATE_FEEDBACK = (40012, "重复评价", 400)
    USERNAME_EXISTS = (40013, "用户名已存在", 400)

    # AI / 权限 / 资源
    SENSITIVE_CONTENT = (40201, "问题包含敏感内容", 400)
    NON_SAFETY_QUESTION = (40202, "非安全相关问题", 400)
    AI_UNAVAILABLE = (40203, "AI 服务暂不可用", 503)
    SESSION_LIMIT_EXCEEDED = (40204, "会话数量已达上限（100 个）", 400)
    HAZARD_FORBIDDEN = (40301, "无权查看该隐患", 403)
    NOT_ASSIGNEE = (40302, "非被指派人无权操作", 403)
    FORBIDDEN = (40303, "角色无此功能权限", 403)
    HAZARD_NOT_FOUND = (40401, "隐患不存在", 404)
    SESSION_NOT_FOUND = (40402, "会话不存在", 404)
    USER_NOT_FOUND = (40405, "用户不存在", 404)
    FILE_TOO_LARGE = (41300, "上传文件过大", 413)
    AI_RATE_LIMITED = (42901, "AI 问答频率超限（≤ 10 次/分钟）", 429)


def _error_body(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None, "timestamp": int(__import__("time").time())}


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，统一错误响应格式"""

    @app.exception_handler(BizError)
    async def _handle_biz_error(_: Request, exc: BizError):
        return JSONResponse(status_code=exc.http_status, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError):
        # 参数校验失败统一映射为 40001
        return JSONResponse(status_code=400, content=_error_body(40001, "参数校验失败"))

    @app.exception_handler(Exception)
    async def _handle_unhandled(_: Request, exc: Exception):
        # 兜底：未捕获异常返回 500，避免泄露堆栈
        return JSONResponse(status_code=500, content=_error_body(50000, "服务器内部错误"))
