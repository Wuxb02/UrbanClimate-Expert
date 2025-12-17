from collections.abc import Awaitable, Callable
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings


LLMCallable = Callable[[str, list[dict[str, str]] | None], Awaitable[str]]


class LLMFactory:
    """
    Factory for producing LLM callables based on environment configuration.
    The returned callable can be passed to LightRAG's `llm_model_func`.
    """

    @staticmethod
    def build_chat_model() -> LLMCallable:
        llm_type = settings.llm_type.lower()
        if llm_type == "openai":
            return LLMFactory._build_openai()
        if llm_type in {"ollama", "vllm"}:
            return LLMFactory._build_ollama_like()
        raise ValueError(f"Unsupported LLM_TYPE: {settings.llm_type}")

    @staticmethod
    def _build_openai() -> LLMCallable:
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )

        async def _chat(prompt: str, history: list[dict[str, str]] | None = None) -> str:
            messages = history or []
            messages.append({"role": "user", "content": prompt})
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                temperature=0.2,
            )
            return response.choices[0].message.content or ""

        return _chat

    @staticmethod
    def _build_ollama_like() -> LLMCallable:
        """
        Uses OpenAI-compatible endpoints exposed by Ollama or vLLM.
        """
        client = AsyncOpenAI(
            api_key=settings.openai_api_key or "ollama",
            base_url=settings.ollama_base_url,
        )

        async def _chat(prompt: str, history: list[dict[str, str]] | None = None) -> str:
            messages = history or []
            messages.append({"role": "user", "content": prompt})
            response = await client.chat.completions.create(
                model=settings.ollama_model,
                messages=messages,
                temperature=0.2,
            )
            return response.choices[0].message.content or ""

        return _chat
