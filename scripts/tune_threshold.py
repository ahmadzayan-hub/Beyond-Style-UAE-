#!/usr/bin/env python3
"""Originality-gate threshold tuning harness.

Runs the procedure in docs/threshold-tuning.md against real labelled pairs:

    python scripts/tune_threshold.py pairs.csv

pairs.csv columns: image_a,image_b,label   (label: similar | different)

Sweeps thresholds 0.80-0.95, reports false-pass/false-reject rates per
candidate, and recommends the lowest threshold with zero false-passes on the
known-similar set. Uses CLIP when installed; refuses to recommend a
production threshold on the dev embedder.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    pairs_file = Path(sys.argv[1])

    try:
        from bsos.adapters.vision import ClipEmbedder

        embedder = ClipEmbedder()
        production = True
    except Exception as exc:  # noqa: BLE001
        from bsos.adapters.vision import DevPixelEmbedder

        embedder = DevPixelEmbedder()
        production = False
        print(f"WARNING: CLIP unavailable ({exc}); running on the dev embedder — "
              "results exercise the harness but must NOT set a production threshold.\n")

    rows = list(csv.DictReader(pairs_file.open(encoding="utf-8")))
    sims: list[tuple[float, str]] = []
    for row in rows:
        va = embedder.embed_image(Path(row["image_a"]))
        vb = embedder.embed_image(Path(row["image_b"]))
        sims.append((float(np.dot(va, vb)), row["label"].strip().lower()))

    similar = [s for s, label in sims if label == "similar"]
    different = [s for s, label in sims if label == "different"]
    print(f"{len(similar)} known-similar pairs, {len(different)} known-different pairs\n")
    print(f"{'threshold':>9} | {'false-pass (similar)':>20} | {'false-reject (different)':>24}")

    best = None
    for t in [round(0.80 + i * 0.01, 2) for i in range(16)]:
        false_pass = sum(1 for s in similar if s < t)
        false_reject = sum(1 for s in different if s >= t)
        print(f"{t:>9.2f} | {false_pass:>20} | {false_reject:>24}")
        if false_pass == 0 and best is None:
            best = (t, false_reject)

    print()
    if best is None:
        print("no candidate threshold achieved zero false-passes; collect harder "
              "known-similar pairs or inspect the outliers")
        return 1
    print(f"recommended threshold: {best[0]:.2f} "
          f"(zero false-passes; costs {best[1]} false-reject(s) on known-different)")
    if not production:
        print("DEV EMBEDDER RUN — do not apply this value. Install bsos[clip] and re-run.")
        return 1
    print("apply via POST /api/policies/threshold "
          "{key: originality_max_similarity, value, reason} — the change is ledgered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
