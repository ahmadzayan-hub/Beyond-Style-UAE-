"""P1: the generator rejects every image-bearing input, structurally."""

from __future__ import annotations

import base64

import pytest

from bsos.adapters.imagegen import LocalDevProvider, PromptRejected, validate_prompt
from bsos.kernel.contracts import PolicyDenied


def _png_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 10, 10)).save(buf, format="PNG")
    return buf.getvalue()


IMAGE_BEARING_PAYLOADS = [
    {"prompt": "pendant", "model": "local-dev", "brief_id": 1, "image": b"\x89PNG..."},
    {"prompt": "pendant", "model": "local-dev", "brief_id": 1,
     "reference": "/tmp/reference.png"},
    {"prompt": "pendant like https://instagram.com/p/abc/media.jpg",
     "model": "local-dev", "brief_id": 1},
    {"prompt": "data:image/png;base64,iVBORw0KGgoAAAANS", "model": "local-dev", "brief_id": 1},
    {"prompt": "pendant", "model": "local-dev", "brief_id": 1,
     "init_image": base64.b64encode(_png_bytes() * 40).decode()},
    {"prompt": "pendant", "model": "local-dev", "brief_id": 1,
     "attachments": [{"data": b"raw-bytes"}]},
]


@pytest.mark.parametrize("payload", IMAGE_BEARING_PAYLOADS)
def test_every_image_bearing_call_is_rejected(kernel, payload):
    with pytest.raises((PolicyDenied, TypeError)):
        kernel.invoke("designer", "generate.image", payload)


def test_adapter_signature_is_typed_text_only():
    provider = LocalDevProvider()
    with pytest.raises(TypeError):
        provider.generate_image("prompt", "local-dev", image=b"bytes")  # noqa
    with pytest.raises(TypeError):
        validate_prompt(b"not a string", "local-dev")


@pytest.mark.parametrize("prompt", [
    "use https://example.com/ref.jpg as the base",
    "data:image/jpeg;base64,/9j/4AAQSkZJRg",
    "iVBORw0KGgoAAAANSUhEUgAA" + "A" * 100,
])
def test_adapter_revalidates_prompt_content(prompt):
    with pytest.raises(PromptRejected):
        LocalDevProvider().generate_image(prompt, "local-dev")


def test_clean_text_prompt_generates(kernel):
    from sqlmodel import select

    from bsos.memory.domain import Brief, Concept

    with kernel.db_factory() as db:
        db.add(Brief(title="t", attributes={}, status="approved"))
        db.commit()
        brief_id = db.exec(select(Brief)).first().id
    result = kernel.invoke("designer", "generate.image", {
        "prompt": "an original pendant, teardrop silhouette, brushed silver tone",
        "model": "local-dev", "brief_id": brief_id,
    })
    assert result["origin"] == "ai_generated"
    assert "internal_concepts" in result["image_path"]
    assert "CONCEPT_ONLY" in result["image_path"]
    with kernel.db_factory() as db:
        concept = db.get(Concept, result["concept_id"])
        assert concept.origin == "ai_generated"
