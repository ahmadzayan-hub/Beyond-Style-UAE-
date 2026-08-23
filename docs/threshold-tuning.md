# Originality gate — threshold tuning

The gate rejects a concept when its highest CLIP cosine similarity against
any corpus reference reaches `originality_max_similarity` (shipped default
**0.86**) or its perceptual-hash distance to any library asset falls below
`phash_min_distance` (default **8**). Passes within
`originality_escalation_margin` (**0.03**) of the threshold escalate to a
human decision card instead of auto-approving.

## Procedure

1. **Pair sets.** Build two labelled sets:
   - *known-similar*: pairs a human judges derivative — the same piece
     re-photographed, close re-colours, minor crops, obvious copies;
   - *known-different*: pairs a human judges clearly distinct designs.
   Aim for ≥30 pairs per set drawn from the live corpus.
2. **Sweep.** For each candidate threshold in 0.80–0.95 (step 0.01), compute
   pass/reject for every pair with the production embedder.
3. **Pick.** Choose the lowest threshold with **zero false-passes** on the
   known-similar set; report the false-reject rate it costs on the
   known-different set. Set the escalation margin to cover the score band
   where human judges disagreed.
4. **Record.** Apply via `POST /api/policies/threshold` (or edit
   `kernel/policies.yaml` before start). Every runtime change writes a
   ledger entry with old value, new value, actor and reason.

## Build-time tuning run (dev embedder) — honest status

CLIP could not be installed in the build environment, so the shipped 0.86
was validated against the **deterministic dev embedder** with synthetic
pairs (see `tests/test_originality_gate.py`):

| Pair type | Max similarity observed | At 0.86 |
|---|---|---|
| byte-identical copy (known-similar) | 1.000 | rejected ✔ (plus phash distance 0) |
| distinct generated pattern (known-different) | ≈ 0.11–0.4 | passed ✔ |

This confirms the gate machinery, **not** the perceptual quality of 0.86.
The dev embedder is labelled "NOT for production originality decisions" in
every gate result. Before trusting the gate commercially: install
`bsos[clip]`, rebuild corpus embeddings (re-run extraction), and run the
full procedure above with real jewellery pairs. Do not ship an untuned
threshold to production use.

## Perceptual-hash secondary check

`phash_min_distance` guards against near-pixel copies that embedding spaces
can under-score (crops, watermark overlays). Distance is Hamming distance
on 64-bit pHash; 0–5 is effectively the same image, 6–10 close variants.
The default 8 was chosen so byte-identical and lightly-edited copies always
fail even if the embedder is fooled.
