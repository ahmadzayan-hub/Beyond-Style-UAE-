"""Session memory: working state for an active run, discarded on completion."""

from __future__ import annotations

import threading
import uuid
from typing import Any


class SessionMemory:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def open(self) -> str:
        sid = uuid.uuid4().hex[:12]
        with self._lock:
            self._store[sid] = {}
        return sid

    def get(self, sid: str, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._store.get(sid, {}).get(key, default)

    def set(self, sid: str, key: str, value: Any) -> None:
        with self._lock:
            self._store.setdefault(sid, {})[key] = value

    def close(self, sid: str) -> None:
        with self._lock:
            self._store.pop(sid, None)
