"""Pure, local image utilities for skills.

No network, no model calls — hashing and perceptual fingerprints only.
Anything that talks to a model or the outside world lives in adapters and is
reached exclusively through ``ctx.adapters``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def perceptual_hash(image_path: Path) -> str:
    import imagehash
    from PIL import Image

    return str(imagehash.phash(Image.open(image_path)))


def phash_distance(h1: str, h2: str) -> int:
    import imagehash

    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)
