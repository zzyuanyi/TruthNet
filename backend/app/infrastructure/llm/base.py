"""BaseOpenAICompatibleProvider — OpenAI 兼容 LLM 共享基类.

DeepSeek、Qwen 等 OpenAI 兼容 API 的公共实现：
- AsyncOpenAI 客户端管理
- 聊天、流式、结构化输出
- tenacity 重试 + 指数退避
- 连接检查

子类只需提供 api_key、base_url、model 和 provider_name。
"""

import json
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_transient_error(exception: BaseException) -> bool:
    """判断是否为可重试的瞬时错误."""
    try:
        from openai import APIStatusError, APITimeoutError, APIConnectionError

        return isinstance(
            exception, (APIStatusError, APITimeoutError, APIConnectionError)
        )
    except ImportError:
        return False


class BaseOpenAICompatibleProvider:
    """OpenAI 兼容 LLM Provider 共享基类.

    子类需覆盖 provider_name property，
    并在 __init__ 中调用 super().__init__(...) 传入凭据。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 30,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout = timeout
        self._available = bool(api_key)
        self._client: AsyncOpenAI | None = None

        if self._available:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=float(timeout),
            )
            logger.info(
                "%s: 客户端已初始化 (model=%s, base_url=%s)",
                self.provider_name,
                model,
                base_url,
            )
        else:
            logger.warning("%s: API key 未配置，Provider 不可用", self.provider_name)

    # ── 抽象属性 ──────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        """Provider 名称（子类必须覆盖）."""
        raise NotImplementedError

    # ── 连接检查 ──────────────────────────────────────────

    async def check_connection(self) -> bool:
        """发送最简请求验证 API 连通性."""
        if self._client is None:
            logger.warning("%s: 客户端未初始化，无法检查连接", self.provider_name)
            return False

        try:
            _ = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            self._available = True
            logger.info("%s: 连接检查成功 (model=%s)", self.provider_name, self._model)
            return True
        except Exception as e:
            self._available = False
            logger.warning("%s: 连接检查失败: %s", self.provider_name, e)
            return False

    # ── 聊天 ──────────────────────────────────────────────

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """发送对话请求，返回文本回答（带重试）."""
        if self._client is None:
            return self._unavailable_response()

        @retry(
            retry=retry_if_exception(_is_transient_error),
            stop=stop_after_attempt(settings.LLM_RETRY_MAX_ATTEMPTS),
            wait=wait_exponential_jitter(
                initial=settings.LLM_RETRY_MIN_WAIT,
                max=settings.LLM_RETRY_MAX_WAIT,
                jitter=2,
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _call():
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                **kwargs,
            )
            return response.choices[0].message.content or ""

        try:
            return await _call()
        except Exception as e:
            logger.error("%s: chat 调用失败（重试已用尽）: %s", self.provider_name, e)
            return f"[{self.provider_name}] 服务暂时不可用，请稍后重试。错误: {e}"

    # ── 流式聊天 ──────────────────────────────────────────

    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """流式对话请求，yield 文本片段."""
        if self._client is None:
            yield self._unavailable_response()
            return

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                **kwargs,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            logger.error("%s: chat_stream 调用失败: %s", self.provider_name, e)
            yield f"\n[{self.provider_name}] 流式输出中断。错误: {e}"

    # ── 结构化输出 ────────────────────────────────────────

    async def structured_chat(
        self,
        messages: list[dict],
        output_schema: type[BaseModel],
        **kwargs,
    ) -> BaseModel:
        """结构化对话请求，返回 Pydantic 模型实例.

        使用 JSON 模式确保输出符合指定的 Pydantic schema。
        验证失败时自动重试一次。
        """
        if self._client is None:
            return self._degraded_structured(output_schema, "Provider 不可用")

        schema_json = json.dumps(output_schema.model_json_schema(), ensure_ascii=False)

        system_msg = {
            "role": "system",
            "content": (
                "你必须以符合以下 JSON Schema 的 JSON 对象回复。"
                "不要包含额外的解释文字，只输出 JSON。\n"
                f"```json\n{schema_json}\n```"
            ),
        }

        augmented = [system_msg] + list(messages)

        for attempt in range(2):  # 最多 2 次尝试
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=augmented,
                    response_format={"type": "json_object"},
                    **kwargs,
                )
                content = response.choices[0].message.content or "{}"

                # DeepSeek 有时在 JSON 前后包裹 markdown 代码块标记
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(
                        lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                    )

                try:
                    return output_schema.model_validate_json(content)
                except ValidationError as ve:
                    if attempt == 0:
                        logger.warning(
                            "%s: structured_chat 解析失败，重试中: %s",
                            self.provider_name,
                            ve.errors(),
                        )
                        # 在重试时加强系统提示
                        augmented.append(
                            {
                                "role": "user",
                                "content": (
                                    f"上次输出解析失败：{json.dumps(ve.errors(), ensure_ascii=False)}。"
                                    "请确保你的回复严格符合 JSON Schema。"
                                ),
                            }
                        )
                        continue
                    else:
                        logger.error(
                            "%s: structured_chat 两次解析均失败: %s",
                            self.provider_name,
                            ve.errors(),
                        )
                        return self._degraded_structured(
                            output_schema, f"JSON 解析失败: {ve.errors()}"
                        )
            except Exception as e:
                if attempt == 0:
                    logger.warning(
                        "%s: structured_chat 第 %d 次调用失败: %s",
                        self.provider_name,
                        attempt + 1,
                        e,
                    )
                    continue
                else:
                    logger.error(
                        "%s: structured_chat 两次调用均失败: %s",
                        self.provider_name,
                        e,
                    )
                    return self._degraded_structured(output_schema, str(e))

        return self._degraded_structured(output_schema, "未知错误")

    # ── 内部辅助 ──────────────────────────────────────────

    def _unavailable_response(self) -> str:
        """Provider 不可用时的文本回答."""
        return (
            f"[{self.provider_name}] Provider 未激活，请配置 "
            f"{self.provider_name.upper()}_API_KEY。"
        )

    def _degraded_structured(
        self,
        output_schema: type[BaseModel],
        reason: str,
    ) -> BaseModel:
        """返回降级的结构化结果——使用模型默认值."""
        logger.warning(
            "%s: 返回降级结构化结果 (schema=%s, reason=%s)",
            self.provider_name,
            output_schema.__name__,
            reason,
        )
        try:
            return output_schema()
        except Exception:
            return output_schema.model_validate({})
