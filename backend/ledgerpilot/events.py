"""In-process fan-out of server-sent events. Safe to publish from worker threads."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

PING_SECONDS = 20


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event: str, data: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        message = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
        for queue in list(self._subscribers):
            self._loop.call_soon_threadsafe(queue.put_nowait, message)

    async def stream(self) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=PING_SECONDS)
                except TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            self._subscribers.discard(queue)
