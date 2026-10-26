"""AI 智能助手大模型服务：OpenAI 兼容异步流式调用。

配置来源按优先级：
1. 模型管理里 model_type='chat' 且 is_active=1 的模型（与管理端测试同源，改完即时生效）
2. .env 的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME（兜底）
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.response import BizError, ErrorCode

# 模型调用超时上界（秒）与重试次数：防止挂起拖死前端 loading
API_TIMEOUT_S = 120
API_MAX_RETRIES = 1


class LlmService:
    def __init__(self):
        self._client: AsyncOpenAI | None = None
        self._client_key: tuple[str, str] | None = None

    @staticmethod
    async def resolve_config(db: AsyncSession) -> dict | None:
        """解析当前生效的 chat 模型配置，两处都不可用时返回 None。

        先查模型管理中启用的 chat 模型（同类型只有一条 is_active=1），
        缺失再回退 .env。返回 dict 含 api_key / base_url / model_name 等。
        """
        row = (await db.execute(text(
            "SELECT api_base, api_key, model_name, temperature, max_tokens "
            "FROM ai_model_config WHERE model_type = 'chat' AND is_active = 1 "
            "ORDER BY id LIMIT 1"
        ))).fetchone()
        if row and row.api_base and row.api_key and row.model_name:
            return {
                "api_key": row.api_key,
                "base_url": row.api_base,
                "model_name": row.model_name,
                "temperature": row.temperature if row.temperature is not None else 0.3,
                "max_tokens": row.max_tokens or 2048,
                "source": "db",
            }
        if settings.LLM_API_KEY and settings.LLM_BASE_URL and settings.LLM_MODEL_NAME:
            return {
                "api_key": settings.LLM_API_KEY,
                "base_url": settings.LLM_BASE_URL,
                "model_name": settings.LLM_MODEL_NAME,
                "temperature": 0.3,
                "max_tokens": 2048,
                "source": ".env",
            }
        return None

    def _get_client(self, cfg: dict) -> AsyncOpenAI:
        if not cfg:
            raise BizError(*ErrorCode.AI_UNAVAILABLE)
        # 配置切换后重建客户端，避免沿用旧 base_url / key
        key = (cfg["base_url"], cfg["api_key"])
        if self._client is None or self._client_key != key:
            self._client = AsyncOpenAI(
                api_key=cfg["api_key"],
                base_url=cfg["base_url"],
                timeout=API_TIMEOUT_S,
                max_retries=API_MAX_RETRIES,
            )
            self._client_key = key
        return self._client

    async def stream_chat(self, messages: list[dict], cfg: dict | None) -> AsyncIterator[str]:
        """按 token 异步流式 yield 回答文本。"""
        client = self._get_client(cfg)
        try:
            stream = await client.chat.completions.create(
                model=cfg["model_name"],
                messages=messages,
                stream=True,
                temperature=cfg.get("temperature", 0.3),
                # glm-5.2 为思考模型：默认思考链使首字延迟数十秒，关闭后秒级响应
                extra_body={"enable_thinking": False},
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except BizError:
            raise
        except Exception:
            raise BizError(*ErrorCode.AI_UNAVAILABLE)


llm_service = LlmService()
