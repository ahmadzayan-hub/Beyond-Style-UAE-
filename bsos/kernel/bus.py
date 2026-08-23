"""In-process event bus.

Synchronous subscribers for internal wiring plus asyncio queues for SSE
fan-out to the UI's live policy feed. Publishing never raises: a failing
subscriber is isolated and reported on the bus itself.
"""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from typing import Any, Callable

Handler = Callable[[str, dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._queues: list[asyncio.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self, topic: str, handler: Handler) -> None:
        with self._lock:
            self._handlers[topic].append(handler)

    def attach_queue(self, maxsize: int = 500) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        with self._lock:
            self._queues.append(q)
        return q

    def detach_queue(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    def publish(self, topic: str, event: dict[str, Any]) -> None:
        with self._lock:
            handlers = list(self._handlers.get(topic, [])) + list(self._handlers.get("*", []))
            queues = list(self._queues)
        for h in handlers:
            try:
                h(topic, event)
            except Exception:  # noqa: BLE001 — subscriber faults must not break publishers
                pass
        payload = {"topic": topic, **event}
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
