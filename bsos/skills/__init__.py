"""Skill package. Importing it registers every skill into the registry."""

from bsos.skills import (  # noqa: F401
    asset_custody,
    concept_studio,
    corpus_synth,
    export_publish,
    spec_workshop,
)
from bsos.skills.registry import registry

__all__ = ["registry"]
