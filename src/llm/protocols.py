"""Protocol definitions for LLM providers."""

from enum import Enum
from typing import Protocol, runtime_checkable
from pydantic import BaseModel


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A message in a conversation."""

    role: MessageRole
    content: str


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers.

    Implement this protocol to add support for new LLM APIs.
    """

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a completion for a simple prompt.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text
        """
        ...

    async def complete_messages(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a completion for a conversation.

        Args:
            messages: List of messages in the conversation
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text
        """
        ...
