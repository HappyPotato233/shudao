"""应用配置 - 基于 pydantic-settings 管理环境变量与默认配置"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# project-root 根目录（基于本文件位置推算）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# 数据库文件绝对路径
_DB_PATH = _PROJECT_ROOT / "database" / "app.db"


class Settings(BaseSettings):
    """全局配置，支持 .env 覆盖"""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "蜀道安全助手"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # API 前缀
    API_V1_PREFIX: str = "/api/v1"

    # JWT 配置（生产环境务必通过 .env 注入随机密钥）
    JWT_SECRET_KEY: str = "shudao-safety-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120   # 2 小时，符合 PRD 5.2.1
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 密码复杂度（PRD 5.2.1：≥8 位，含大小写字母+数字+特殊字符）
    PASSWORD_MIN_LENGTH: int = 8

    # 会话超时（30 分钟无操作自动登出，PRD 5.2.1）
    SESSION_IDLE_TIMEOUT_MINUTES: int = 30

    # 数据库配置（SQLite，使用绝对路径避免工作目录差异）
    DATABASE_URL: str = f"sqlite:///{_DB_PATH}"

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        """异步引擎连接串：sqlite → aiosqlite，postgresql → asyncpg 驱动

        供 SQLAlchemy create_async_engine 使用，与 DATABASE_URL 指向同一数据库。
        """
        url = self.DATABASE_URL
        if url.startswith("sqlite:///"):
            return "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://"):]
        return url

    # 视觉大模型（OpenAI 兼容接口；专用于隐患图像识别，后续可再扩展其它模型）
    VISULIZATION_API_KEY: str = ""
    VISULIZATION_BASE_URL: str = ""
    VISULIZATION_MODEL_NAME: str = ""

    # AI 智能助手大模型（OpenAI 兼容接口；与视觉模型分离）
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL_NAME: str = ""

    # 本地向量化与重排模型（已复制到 project-root/models）
    EMBEDDING_MODEL_DIR: str = str(_PROJECT_ROOT / "models" / "bge-large")
    RERANK_MODEL_DIR: str = str(_PROJECT_ROOT / "models" / "bge-base-rerank")

    # Chroma 向量索引持久化目录
    CHROMA_PERSIST_DIR: str = str(_PROJECT_ROOT / "chroma_data")

    # AI 问答限流：单用户每分钟最大次数
    AI_RATE_LIMIT_PER_MIN: int = 10

    # RAG 检索：重排分数阈值与 RRF 融合参数
    RAG_RERANK_THRESHOLD: float = 0.3
    RAG_RRF_K: float = 60.0

    # 启动时后台预热 BGE 模型（测试环境关闭：加载中的后台线程在进程退出时
    # 会引发 access violation，且测试无需真实模型）
    PRELOAD_MODELS: bool = True

    # 上传与图片限制（PRD H01/H09：最多 9 张，单张 20MB）
    UPLOAD_DIR: str = str(_PROJECT_ROOT / "uploads")

    # 标注图片库根目录（YOLO 格式：运营高速公路/隧道施工/简支梁/加油站 四个子集）
    ANNOTATED_IMAGE_DIR: str = str(_PROJECT_ROOT.parent / "data" / "test-image")
    MAX_HAZARD_IMAGES: int = 9
    MAX_IMAGE_SIZE_MB: int = 20
    MAX_ATTACHMENT_COUNT: int = 5
    MAX_ATTACHMENT_SIZE_MB: int = 20


settings = Settings()
