"""Append-only audit ledger.

JSONL on disk, hash-chained: each entry embeds the SHA-256 of the previous
entry, so any tampering with history breaks verification. There is no update
or delete API on purpose. Every policy evaluation — including passes — every
grant check, every threshold change, and every export lands here.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

GENESIS = "0" * 64


def _canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._seq, self._prev_hash = self._recover()

    def _recover(self) -> tuple[int, str]:
        seq, prev = 0, GENESIS
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    seq = entry["seq"]
                    prev = entry["hash"]
        return seq, prev

    def append(
        self,
        event_type: str,
        actor: str,
        data: dict[str, Any] | None = None,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            entry: dict[str, Any] = {
                "seq": self._seq + 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "actor": actor,
                "outcome": outcome,
                "data": data or {},
                "prev_hash": self._prev_hash,
            }
            entry["hash"] = hashlib.sha256(
                (self._prev_hash + _canonical({k: v for k, v in entry.items() if k != "hash"})).encode()
            ).hexdigest()
            with self.path.open("a", encoding="utf-8") as f:
                f.write(_canonical(entry) + "\n")
            self._seq = entry["seq"]
            self._prev_hash = entry["hash"]
            return entry

    def entries(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def tail(self, n: int = 100, event_type: str | None = None) -> list[dict[str, Any]]:
        rows = [e for e in self.entries() if event_type is None or e["event_type"] == event_type]
        return rows[-n:]

    def verify(self) -> bool:
        """Recompute the hash chain; False if any entry was altered."""
        prev = GENESIS
        for entry in self.entries():
            expected = hashlib.sha256(
                (prev + _canonical({k: v for k, v in entry.items() if k != "hash"})).encode()
            ).hexdigest()
            if entry["hash"] != expected or entry["prev_hash"] != prev:
                return False
            prev = entry["hash"]
        return True
