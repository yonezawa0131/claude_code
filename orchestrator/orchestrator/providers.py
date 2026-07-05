"""モデル呼び出しの抽象化。

Provider プロトコルに合わせれば他社モデルも差し込める。
標準実装は公式 Anthropic SDK (AsyncAnthropic) を使う。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ModelRefusedError(Exception):
    """安全分類器または モデル自身がリクエストを拒否した。"""

    def __init__(self, model: str, category: str | None = None):
        self.model = model
        self.category = category
        super().__init__(f"{model} refused (category={category})")


@dataclass
class Completion:
    text: str
    model: str  # 実際に応答したモデル(フォールバック時は要求と異なりうる)
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None


class Provider(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 16_000,
        effort: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> Completion: ...


class AnthropicProvider:
    """公式 Anthropic SDK 実装。

    - claude-fable-5 にはサーバーサイド refusal フォールバック
      (beta: server-side-fallback-2026-06-01 → claude-opus-4-8) を既定で付ける。
      安全分類器の誤検知でリクエストが止まらないようにするための公式推奨設定。
    - effort はサポートするモデルにだけ渡す(Haiku 4.5 では 400 になるため)。
    - output_schema を渡すと structured outputs (output_config.format) で
      有効な JSON を保証する。
    """

    FABLE_FALLBACK_BETA = "server-side-fallback-2026-06-01"

    def __init__(self, client=None):
        if client is None:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic()
        self._client = client

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 16_000,
        effort: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> Completion:
        from .models import CATALOG

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system

        output_config: dict[str, Any] = {}
        info = CATALOG.get(model)
        if effort and info and info.supports_effort:
            output_config["effort"] = effort
        if output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}
        if output_config:
            kwargs["output_config"] = output_config

        if model == "claude-fable-5":
            kwargs["betas"] = [self.FABLE_FALLBACK_BETA]
            kwargs["fallbacks"] = [{"model": "claude-opus-4-8"}]
            response = await self._client.beta.messages.create(**kwargs)
        else:
            response = await self._client.messages.create(**kwargs)

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise ModelRefusedError(model, category)

        text = "".join(b.text for b in response.content if b.type == "text")
        return Completion(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )
