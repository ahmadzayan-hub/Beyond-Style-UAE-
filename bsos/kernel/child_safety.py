"""Conservative deterministic hazard rules ported from SafetyAgent.

These rules act on declared design/material facts; they are not a physical
product certification or a substitute for a workshop safety inspection.
"""

import json
import re

CHILD_AUTO_REJECT = (
    "choking hazard", "small detachable component", "unsafe chain length",
    "strangulation hazard", "sharp edge", "weak clasp", "unsafe stone",
    "magnet", "unverified coating", "toxic material", "fragile attachment",
)


def review_child_safety(facts: dict) -> tuple[list[str], bool]:
    """Return absolute failures and whether safe wearable review is required.

    Accept the sibling's camelCase and BSOS's snake_case fact names. Match
    the sibling's conservative first-word hazard triggers, plus small parts.
    """
    text = json.dumps(facts, ensure_ascii=False).lower()
    nodes = []

    def visit(value):
        if isinstance(value, dict):
            nodes.append(value)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(facts)
    # Brief attributes use {path: {value, source_ids}} rather than raw values.
    nodes.extend({key.rsplit(".", 1)[-1]: value["value"]}
                 for node in list(nodes) for key, value in node.items()
                 if isinstance(value, dict) and "value" in value)
    child = any(n.get("is_child_product") is True or n.get("isChildProduct") is True
                or n.get("family") == "BABIES_CHILDREN" for n in nodes)
    wearable = any(n.get("is_wearable_child_product") is True
                   or n.get("isWearableChildProduct") is True for n in nodes)
    child = child or wearable
    hazards = []
    # General wearable checks from the source apply to adult designs too.
    minimums = [n.get("minimum_thickness_mm", n.get("minimumThicknessMm")) for n in nodes]
    minimums = [float(v) for v in minimums if v is not None]
    for node in nodes:
        dimensions = node.get("dimensions", {})
        thickness = dimensions.get("thickness_mm", dimensions.get("thicknessMm"))
        minimum = max(minimums) if minimums else None
        if thickness is not None and minimum is not None and float(thickness) < float(minimum):
            hazards.append("structural weakness: below material minimum thickness")
        if any("sharp" in str(r).lower() for r in node.get("risks", [])):
            hazards.append("sharp edge risk flagged by design")
    if child:
        hazards.extend(h for h in CHILD_AUTO_REJECT
                       if re.search(r"\b" + re.escape(h.split()[0]), text))
        if re.search(r"bead|charm|slider", text):
            hazards.append("small detachable component (bead/charm/slider)")
        if "babies-children" in text:
            hazards.append("restricted material for children")
    return sorted(set(hazards)), child and wearable and not hazards
