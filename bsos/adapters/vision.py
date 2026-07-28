"""Vision adapter: attribute extraction, OCR-ish mark detection, embeddings.

Attribute extraction runs a vision-capable LLM and returns structured JSON
only — the image never travels further than this adapter. Embeddings power
the originality gate: production uses CLIP (optional extra `bsos[clip]`);
without it, a deterministic pixel-projection embedder keeps the machinery
running for development and is clearly reported as such in `describe()`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ATTRIBUTE_SCHEMA_KEYS = {
    "form": ["silhouette", "dominant_geometry", "symmetry", "proportion_ratio", "layering", "scale"],
    "motif": ["primary", "cultural_register", "abstraction_level"],
    "typography": ["present", "script", "style", "integration"],
    "material_finish": ["apparent_metal", "finish", "stone_presence", "colour_palette"],
    "construction": ["apparent_technique", "join_method", "closure"],
    "commercial": ["occasion", "gifting_signal", "perceived_tier", "target_segment"],
}

_BRAND_TOKENS = ("cartier", "tiffany", "bulgari", "bvlgari", "van cleef", "chopard", "pandora", "swarovski", "damas", "lazurde")


class VisionError(Exception):
    pass


def validate_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """Enforce the extraction contract: schema shape, <=12 words, no brand names."""
    cleaned: dict[str, Any] = {}
    for section, keys in ATTRIBUTE_SCHEMA_KEYS.items():
        src = data.get(section, {}) or {}
        out: dict[str, Any] = {}
        for key in keys:
            value = src.get(key, "" if key != "present" else False)
            if isinstance(value, str):
                if len(value.split()) > 12:
                    raise VisionError(f"{section}.{key}: field longer than 12 words rejected")
                if any(tok in value.lower() for tok in _BRAND_TOKENS):
                    raise VisionError(f"{section}.{key}: brand/designer naming rejected")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and any(t in item.lower() for t in _BRAND_TOKENS):
                        raise VisionError(f"{section}.{key}: brand/designer naming rejected")
            out[key] = value
        cleaned[section] = out
    return cleaned


EXTRACTION_PROMPT = (
    "You are an abstraction engine for a jewellery market corpus. Describe the "
    "piece in this image as structured JSON matching the given schema exactly. "
    "Each string field must be at most 12 words. Never name a brand, designer, "
    "product or collection. Return JSON only.\n\nSchema: "
    + json.dumps({k: {f: "" for f in v} for k, v in ATTRIBUTE_SCHEMA_KEYS.items()})
)


class LLMVisionExtractor:
    """Attribute extraction via a vision-capable LLM adapter (see llm.py)."""

    def __init__(self, llm):
        self.llm = llm

    def extract_attributes(self, image_path: Path) -> dict[str, Any]:
        raw = self.llm.complete_vision(EXTRACTION_PROMPT, Path(image_path))
        try:
            data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        except (ValueError, json.JSONDecodeError) as exc:
            raise VisionError(f"vision model returned non-JSON output: {exc}") from exc
        return validate_attributes(data)


# ---------------------------------------------------------------------------
# Embedders
# ---------------------------------------------------------------------------


class ClipEmbedder:
    """CLIP embeddings (production path). Requires `pip install bsos[clip]`."""

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        try:
            import open_clip
            import torch
        except ImportError as exc:
            raise VisionError(
                "open-clip-torch not installed; install extras `bsos[clip]` or use "
                "the dev embedder (development only)"
            ) from exc
        self._torch = torch
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        self.model.eval()

    def embed_image(self, image_path: Path) -> np.ndarray:
        from PIL import Image

        img = self.preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
        with self._torch.no_grad():
            feats = self.model.encode_image(img)
        vec = feats[0].cpu().numpy().astype(np.float32)
        return vec / (np.linalg.norm(vec) or 1.0)

    def describe(self) -> str:
        return "clip"


class DevPixelEmbedder:
    """Deterministic fallback embedder — DEVELOPMENT ONLY.

    Projects a downscaled grayscale image through a fixed random matrix
    (seeded), giving stable cosine geometry good enough to exercise the gate
    machinery and tests. It is not a perceptual model; SETUP.md requires CLIP
    before originality decisions are trusted.
    """

    DIM = 256

    def __init__(self) -> None:
        rng = np.random.default_rng(20260728)
        self._proj = rng.standard_normal((32 * 32, self.DIM)).astype(np.float32)

    def embed_image(self, image_path: Path) -> np.ndarray:
        from PIL import Image

        img = Image.open(image_path).convert("L").resize((32, 32))
        flat = np.asarray(img, dtype=np.float32).ravel()
        flat = (flat - flat.mean()) / (flat.std() or 1.0)
        vec = flat @ self._proj
        return vec / (np.linalg.norm(vec) or 1.0)

    def describe(self) -> str:
        return "dev-pixel-projection (NOT for production originality decisions)"


def perceptual_hash(image_path: Path) -> str:
    import imagehash
    from PIL import Image

    return str(imagehash.phash(Image.open(image_path)))


def phash_distance(h1: str, h2: str) -> int:
    import imagehash

    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
