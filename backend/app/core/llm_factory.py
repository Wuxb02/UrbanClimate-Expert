from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logger import logger


LLMCallable = Callable[[str, list[dict[str, str]] | None], Awaitable[str]]


class LLMFactory:
    """
    Factory for producing LLM callables based on environment configuration.
    The returned callable can be passed to LightRAG's `llm_model_func`.
    """

    @staticmethod
    def build_chat_model() -> LLMCallable:
        llm_type = settings.llm_type.lower()
        logger.info(f"构建 LLM 模型 | 类型: {llm_type}")

        try:
            if llm_type == "openai":
                return LLMFactory._build_openai()
            if llm_type in {"ollama", "vllm"}:
                return LLMFactory._build_ollama_like()
            raise ValueError(f"Unsupported LLM_TYPE: {settings.llm_type}")
        except Exception as e:
            logger.error(f"LLM 模型构建失败 | 类型: {llm_type} | 错误: {e}")
            raise

    @staticmethod
    def _build_openai() -> LLMCallable:
        logger.debug(
            f"配置 OpenAI 客户端 | "
            f"模型: {settings.openai_model} | "
            f"Base URL: {settings.openai_base_url or 'default'}"
        )

        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )

        async def _chat(prompt: str, history: list[dict[str, str]] | None = None) -> str:
            logger.debug(f"OpenAI 请求开始 | Prompt 长度: {len(prompt)}")

            try:
                messages = history or []
                messages.append({"role": "user", "content": prompt})
                response = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    temperature=0.2,
                )
                content = response.choices[0].message.content or ""
                logger.debug(f"OpenAI 请求成功 | 响应长度: {len(content)}")
                return content
            except Exception as e:
                logger.error(f"OpenAI 请求失败 | 错误: {e}")
                raise

        logger.info(f"OpenAI 客户端配置完成 | 模型: {settings.openai_model}")
        return _chat

    @staticmethod
    def _build_ollama_like() -> LLMCallable:
        """
        Uses OpenAI-compatible endpoints exposed by Ollama or vLLM.
        """
        logger.debug(
            f"配置 Ollama/vLLM 客户端 | "
            f"模型: {settings.ollama_model} | "
            f"Base URL: {settings.ollama_base_url}"
        )

        client = AsyncOpenAI(
            api_key=settings.openai_api_key or "ollama",
            base_url=settings.ollama_base_url,
        )

        async def _chat(prompt: str, history: list[dict[str, str]] | None = None) -> str:
            logger.debug(f"Ollama 请求开始 | Prompt 长度: {len(prompt)}")

            try:
                messages = history or []
                messages.append({"role": "user", "content": prompt})
                response = await client.chat.completions.create(
                    model=settings.ollama_model,
                    messages=messages,
                    temperature=0.2,
                )
                content = response.choices[0].message.content or ""
                logger.debug(f"Ollama 请求成功 | 响应长度: {len(content)}")
                return content
            except Exception as e:
                logger.error(f"Ollama 请求失败 | 错误: {e}")
                raise

        logger.info(f"Ollama/vLLM 客户端配置完成 | 模型: {settings.ollama_model}")
        return _chat
