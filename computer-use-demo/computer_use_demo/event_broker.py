from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import AsyncIterator


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._subscribers[session_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[session_id].discard(queue)
                if not self._subscribers[session_id]:
                    self._subscribers.pop(session_id, None)

    async def publish(self, session_id: str, message: str) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(session_id, set()))
        for queue in queues:
            queue.put_nowait(message)
