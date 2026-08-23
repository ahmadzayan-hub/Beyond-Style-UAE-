"""Vector memory for the originality gate and semantic corpus search.

Embeddings are stored as float32 blobs in SQLite; cosine similarity runs in
numpy. The embedder is pluggable: production uses CLIP (see
adapters/vision.py); tests inject deterministic embedders. No cloud vector
service is involved.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import numpy as np


class VectorStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS embeddings (
                       key TEXT PRIMARY KEY,
                       namespace TEXT NOT NULL,
                       dim INTEGER NOT NULL,
                       vector BLOB NOT NULL
                   )"""
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def upsert(self, key: str, vector: np.ndarray, namespace: str = "corpus") -> None:
        vec = np.asarray(vector, dtype=np.float32).ravel()
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (key, namespace, dim, vector) VALUES (?,?,?,?)",
                (key, namespace, vec.shape[0], vec.tobytes()),
            )

    def get(self, key: str) -> np.ndarray | None:
        with self._conn() as conn:
            row = conn.execute("SELECT vector, dim FROM embeddings WHERE key=?", (key,)).fetchone()
        if row is None:
            return None
        return np.frombuffer(row[0], dtype=np.float32)

    def count(self, namespace: str = "corpus") -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE namespace=?", (namespace,)
            ).fetchone()[0]

    def search(self, query: np.ndarray, namespace: str = "corpus", top_k: int = 3) -> list[tuple[str, float]]:
        """Return (key, cosine_similarity) sorted desc across the namespace."""
        q = np.asarray(query, dtype=np.float32).ravel()
        qn = np.linalg.norm(q)
        if qn == 0:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT key, vector FROM embeddings WHERE namespace=?", (namespace,)
            ).fetchall()
        scored: list[tuple[str, float]] = []
        for key, blob in rows:
            v = np.frombuffer(blob, dtype=np.float32)
            vn = np.linalg.norm(v)
            if vn == 0:
                continue
            scored.append((key, float(np.dot(q, v) / (qn * vn))))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:top_k]
