"""Image generation adapter: text in, image out. Nothing else in.

The interface is typed so P1 is structural: ``generate_image(prompt, model)``
takes exactly a string prompt and a model id. The adapter re-validates the
prompt (no base64 signature, no URL, no data URI) as defence in depth behind
the kernel policy check.

Providers: Google Nano Banana family via the Gemini API. As of July 2026:
  - Nano Banana Pro   (gemini-3-pro-image)          — final renders, up to 4K
  - Nano Banana 2     (gemini-3.1-flash-image)      — general work
  - Nano Banana 2 Lite (gemini-3.1-flash-lite-image) — bulk ideation, ~4 s
The live model list is read at startup; a configured id that has vanished
fails loudly instead of being silently substituted. Every Nano Banana output
carries an invisible SynthID watermark (a further reason P5 exists).
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

_FORBIDDEN_PROMPT_PATTERNS = (
    re.compile(r"data:\s*image/", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"(?:iVBOR|/9j/|R0lGOD|UklGR)[A-Za-z0-9+/=]{64,}"),
)


class ImageGenError(Exception):
    pass


class PromptRejected(ImageGenError):
    """Prompt carried image data or a reference to it."""


@dataclass
class ImageResult:
    image_bytes: bytes
    model_id: str
    model_version: str
    generated_at: str


def validate_prompt(prompt: str, model: str) -> None:
    if not isinstance(prompt, str) or not isinstance(model, str):
        raise TypeError("generate_image(prompt: str, model: str) — no other input types exist")
    for pat in _FORBIDDEN_PROMPT_PATTERNS:
        if pat.search(prompt):
            raise PromptRejected(
                "prompt rejected: it contains a URL, data URI, or base64 image signature; "
                "the generator accepts descriptive text only (P1)"
            )


class NanoBananaProvider:
    """Google Gemini image models ('Nano Banana' family)."""

    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, allowed_models: list[str] | None = None, timeout: float = 120.0):
        if not api_key:
            raise ImageGenError("GOOGLE_API_KEY missing — imagegen adapter cannot start (see SETUP.md)")
        self.api_key = api_key
        self.timeout = timeout
        self.allowed_models = allowed_models or [
            "gemini-3-pro-image",
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-lite-image",
        ]
        self._verify_models_live()

    def _verify_models_live(self) -> None:
        """Read the live model list; fail loudly if a configured id is gone."""
        resp = httpx.get(
            f"{self.BASE}/models", params={"key": self.api_key, "pageSize": 200},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        live = {m["name"].split("/")[-1] for m in resp.json().get("models", [])}
        missing = [m for m in self.allowed_models if m not in live]
        if missing:
            raise ImageGenError(
                f"configured imagegen model(s) not present in the live model list: {missing}. "
                "Refusing to start with a stale configuration — update BSOS_IMAGEGEN_MODELS."
            )

    def generate_image(self, prompt: str, model: str) -> ImageResult:
        validate_prompt(prompt, model)
        if model not in self.allowed_models:
            raise ImageGenError(f"model '{model}' is not in the allowed set {self.allowed_models}")
        resp = httpx.post(
            f"{self.BASE}/models/{model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"]},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        for cand in body.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return ImageResult(
                        image_bytes=base64.b64decode(inline["data"]),
                        model_id=model,
                        model_version=body.get("modelVersion", model),
                        generated_at=datetime.now(timezone.utc).isoformat(),
                    )
        raise ImageGenError(f"model '{model}' returned no image data")


class LocalDevProvider:
    """Offline placeholder renderer for development and tests.

    Renders a flat composition card from the prompt text via Pillow. It is
    NOT a product visual and is labelled as such; SETUP.md documents that a
    real provider key is required for actual concept work.
    """

    def __init__(self) -> None:
        self.allowed_models = ["local-dev"]

    def generate_image(self, prompt: str, model: str = "local-dev") -> ImageResult:
        validate_prompt(prompt, model)
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (768, 768), (242, 240, 236))
        draw = ImageDraw.Draw(img)
        draw.rectangle([24, 24, 744, 744], outline=(180, 174, 166), width=2)
        draw.text((40, 40), "LOCAL DEV RENDER — NOT A PRODUCT VISUAL", fill=(120, 60, 40))
        y = 90
        for line in _wrap(prompt, 58)[:28]:
            draw.text((40, y), line, fill=(60, 58, 54))
            y += 22
        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return ImageResult(
            image_bytes=buf.getvalue(),
            model_id="local-dev",
            model_version="local-dev-0",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def write_concept_only(image: ImageResult, out_dir: Path, concept_id: int | str) -> Path:
    """Write an AI render into exports/internal_concepts with CONCEPT_ONLY marking.

    The filename carries CONCEPT_ONLY; EXIF UserComment carries the same tag
    plus model id. This function is the only writer of generated images and
    it cannot target any other directory.
    """
    out_dir = Path(out_dir)
    if out_dir.name != "internal_concepts":
        raise ImageGenError("AI renders may only be written to exports/internal_concepts (P5)")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"CONCEPT_ONLY_c{concept_id}_{stamp}.png"

    import io

    from PIL import Image, PngImagePlugin

    img = Image.open(io.BytesIO(image.image_bytes))
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Comment", f"CONCEPT_ONLY | ai_generated | model={image.model_id} "
                             f"({image.model_version}) | not for publication")
    img.save(path, "PNG", pnginfo=meta)
    return path
