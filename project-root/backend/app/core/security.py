"""安全工具 - JWT 签发/校验 + BCrypt 密码加盐哈希"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# passlib 上下文，自动加盐
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -------------------- 密码哈希 --------------------

def hash_password(password: str) -> str:
    """对明文密码进行 BCrypt 加盐哈希"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_complexity(password: str) -> bool:
    """密码复杂度：≥8 位，含大小写字母、数字、特殊字符。"""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True


# -------------------- JWT --------------------

def create_access_token(subject: str, extra: dict | None = None) -> tuple[str, str]:
    """
    签发 access_token
    :return: (token, jti)  jti 用于登出黑名单
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def create_refresh_token(subject: str) -> tuple[str, str]:
    """
    签发 refresh_token
    :return: (token, jti)  jti 用于持久化会话和 refresh rotation
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    jti = uuid4().hex
    payload = {
        "sub": subject,
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict:
    """
    解析并校验 token
    :raises JWTError: token 无效或已过期
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def is_expired(exc: JWTError) -> bool:
    """判断 JWTError 是否由过期引起"""
    return "expired" in str(exc).lower()
