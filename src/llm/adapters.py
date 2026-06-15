"""Adapter implementations for LLM providers."""

import logging
import json
from types import SimpleNamespace

from openai import AsyncOpenAI

from ..settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_DEFAULT_MODEL,
)
from .protocols import LLMProvider, Message, MessageRole

logger = logging.getLogger(__name__)


class OpenRouterAdapter(LLMProvider):
    """
    Adapter for OpenRouter API.

    OpenRouter provides access to many LLMs through an OpenAI-compatible API.

    Usage:
        async with OpenRouterAdapter() as llm:
            response = await llm.complete("What is machine learning?")
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize the OpenRouter adapter.

        Args:
            api_key: Optional API key. If not provided, uses OPENROUTER_API_KEY env var.
            model: Model to use. Defaults to OPENROUTER_DEFAULT_MODEL.
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or OPENROUTER_DEFAULT_MODEL
        self.base_url = base_url or OPENROUTER_BASE_URL
        self._client: AsyncOpenAI | None = None

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY in .env"
            )
        if not self.base_url:
            raise ValueError(
                "OpenRouter base URL required. Set OPENROUTER_BASE_URL in .env"
            )

        logger.info(f"OpenRouter adapter initialized with model: {self.model}")

    async def __aenter__(self) -> "OpenRouterAdapter":
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            max_retries=10,  # More retries for free tier rate limits
            timeout=120.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with' context manager."
            )
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a completion for a simple prompt."""
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        logger.info(f"Completing prompt ({len(prompt)} chars) with {self.model}")
        logger.debug(f"Temperature: {temperature}, max_tokens: {max_tokens}")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = response.choices[0].message.content or ""
        logger.info(f"Completion received ({len(result)} chars)")
        logger.debug(f"Usage: {response.usage}")

        return result

    async def complete_messages(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a completion for a conversation."""
        formatted_messages = [
            {"role": msg.role.value, "content": msg.content} for msg in messages
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""

    async def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict:
        """Generate a completion with tool use support.

        Args:
            prompt: User prompt
            tools: List of tool definitions
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Dict containing:
                - content: Text content from the response
                - tool_use: List of tool use blocks if any
                - stop_reason: Why generation stopped
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.complete_with_tools_messages(
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def complete_with_tools_messages(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict:
        """Generate a completion with tool use support for multi-turn conversations.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: List of tool definitions
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Dict containing:
                - content: Text content from the response
                - tool_use: List of tool use blocks if any
                - stop_reason: Why generation stopped
                - raw_content: Raw content blocks for continuing conversation
        """
        logger.info(f"Completing with tools ({len(tools)} tools) using {self.model}")

        formatted_messages = self._format_tool_messages(messages, system_prompt)
        formatted_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", tool.get("parameters", {})),
                },
            }
            for tool in tools
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            tools=formatted_tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        content = message.content or ""

        result = {
            "content": content,
            "tool_use": [],
            "stop_reason": "tool_use" if finish_reason == "tool_calls" else "end_turn",
            "raw_content": [],
        }

        if content:
            result["raw_content"].append(SimpleNamespace(type="text", text=content))

        for tool_call in message.tool_calls or []:
            arguments = tool_call.function.arguments or "{}"
            try:
                tool_input = json.loads(arguments)
            except json.JSONDecodeError:
                logger.warning("Failed to parse tool arguments as JSON: %s", arguments)
                tool_input = {}

            result["tool_use"].append({
                "id": tool_call.id,
                "name": tool_call.function.name,
                "input": tool_input,
            })
            result["raw_content"].append(
                SimpleNamespace(
                    type="tool_use",
                    id=tool_call.id,
                    name=tool_call.function.name,
                    input=tool_input,
                )
            )

        logger.info(
            f"Tool completion received: {len(result['tool_use'])} tool calls, "
            f"stop_reason={result['stop_reason']}"
        )

        return result

    def _format_tool_messages(
        self,
        messages: list[dict],
        system_prompt: str | None,
    ) -> list[dict]:
        """Convert the local tool loop into OpenAI-compatible messages."""
        formatted_messages: list[dict] = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for message in messages:
            role = message["role"]
            content = message["content"]

            if isinstance(content, str):
                formatted_messages.append({"role": role, "content": content})
                continue

            if role == "assistant":
                text_parts: list[str] = []
                tool_calls = []
                for block in content:
                    if block["type"] == "text":
                        text_parts.append(block["text"])
                    elif block["type"] == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        })

                formatted: dict = {
                    "role": "assistant",
                    "content": "\n".join(text_parts) or None,
                }
                if tool_calls:
                    formatted["tool_calls"] = tool_calls
                formatted_messages.append(formatted)
                continue

            if role == "user":
                for block in content:
                    if block["type"] == "tool_result":
                        formatted_messages.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"],
                        })
                    elif block["type"] == "text":
                        formatted_messages.append({
                            "role": "user",
                            "content": block["text"],
                        })
                continue

            formatted_messages.append({"role": role, "content": str(content)})
        return formatted_messages
