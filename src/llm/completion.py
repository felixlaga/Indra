"""Convenience functions for LLM completions."""

from .adapters import OpenRouterAdapter
from .protocols import LLMProvider, Message


async def complete(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    provider: LLMProvider | None = None,
) -> str:
    """
    Generate a completion for a simple prompt.

    Args:
        prompt: The user prompt
        system_prompt: Optional system prompt
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate
        provider: Optional LLM provider. Defaults to OpenRouterAdapter.

    Returns:
        The generated text

    Example:
        response = await complete("Summarize this paper: ...")
    """
    if provider:
        return await provider.complete(prompt, system_prompt, temperature, max_tokens)
    else:
        async with OpenRouterAdapter() as llm:
            return await llm.complete(prompt, system_prompt, temperature, max_tokens)


async def complete_with_messages(
    messages: list[Message],
    temperature: float = 0.7,
    max_tokens: int | None = None,
    provider: LLMProvider | None = None,
) -> str:
    """
    Generate a completion for a conversation.

    Args:
        messages: List of messages in the conversation
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate
        provider: Optional LLM provider. Defaults to OpenRouterAdapter.

    Returns:
        The generated text
    """
    if provider:
        return await provider.complete_messages(messages, temperature, max_tokens)
    else:
        async with OpenRouterAdapter() as llm:
            return await llm.complete_messages(messages, temperature, max_tokens)
