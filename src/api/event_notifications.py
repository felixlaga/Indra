"""One LISTEN connection per API process; durable rows remain authoritative."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

logger = logging.getLogger(__name__)


class EventNotifications:
    def __init__(self, dsn: str | None):
        self.dsn = dsn
        self.subscribers: dict[str, set[asyncio.Event]] = {}
        self.task: asyncio.Task | None = None
        self.connected = asyncio.Event()

    async def start(self) -> None:
        if self.dsn:
            self.task = asyncio.create_task(self._listen())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    @asynccontextmanager
    async def subscribe(self, session_id: str):
        wake = asyncio.Event()
        self.subscribers.setdefault(session_id, set()).add(wake)
        try:
            yield wake
        finally:
            self.subscribers[session_id].discard(wake)
            if not self.subscribers[session_id]:
                del self.subscribers[session_id]

    async def _listen(self) -> None:
        import psycopg

        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self.dsn,
                    autocommit=True,
                    connect_timeout=5,
                    application_name="indra-events",
                ) as conn:
                    await conn.execute("LISTEN indra_events")
                    self.connected.set()
                    # Catch up immediately after reconnecting, including changes
                    # committed during the outage or before LISTEN took effect.
                    for subscribers in self.subscribers.values():
                        for wake in subscribers:
                            wake.set()
                    async for notification in conn.notifies():
                        for wake in self.subscribers.get(notification.payload, ()):
                            wake.set()
            except asyncio.CancelledError:
                raise
            except (psycopg.Error, OSError):
                self.connected.clear()
                logger.warning(
                    "Event listener disconnected; durable polling remains active",
                    exc_info=True,
                )
                await asyncio.sleep(2)
            finally:
                self.connected.clear()
