"""Server-sent event formatting helpers for the product API."""

from __future__ import annotations

from .models import Event


EVENT_STREAM_MEDIA_TYPE = "text/event-stream"


def format_sse_event(event: Event) -> str:
    """Format an API event as a server-sent event frame."""

    return (
        f"id: {event.id}\n"
        f"event: {event.event_type}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


def format_sse_comment(comment: str) -> str:
    """Format a server-sent event comment frame."""

    return f": {comment}\n\n"
