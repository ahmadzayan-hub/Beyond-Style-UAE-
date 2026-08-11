# AI Evaluation Plan — BSOS / Design Studio

Because the manufacturing-critical path is deterministic, evaluation is
mostly *golden testing* rather than statistical model evaluation. All
evals below run in `pytest tests/` (104 passing) unless marked otherwise.

## 1. Typography correctness (deterministic goldens)

- **Reference test — زهران:** shaping must produce the exact expected
  glyph sequence with correct joining; regression-locked.
- **29-name battery:** common Arabic names (نورة، فاطمة، أحمد، ليلى…)
  must reach `typography_verified` — guards the fail-closed matcher
  against false rejections (the camelCase glyph-name incident).
- **Diacritics:** زَهْرَان must normalize to the زهران skeleton (tashkeel
  stripped) and verify.
- **Empty/whitespace input:** must return `human_review` with Arabic
  issue text, never crash.
- **Mixed script:** must force an explicit choice (`arabic_part` /
  `latin_part`), never silently pick.

## 2. Geometry and manufacturability

- Descender-centering battery (نور، ريم on coin/brooch): real ink-bounds
  fitting must keep edge clearance on every item frame.
- Erosion–dilation stroke survival at each item's minimum stroke width.
- Frame presets: every item type composes within its usable diameter.

## 3. Trust ladder and governance

- Ladder ordering: no export before `workshop_approved` locally; grant
  isolation (CALLIGRAPHER cannot call non-design skills — violation is
  ledgered); provenance chain verification for `design-<id>`.

## 4. Pricing and transliteration

- Pricing goldens across items/materials/quantity tiers; 265 AED floor;
  rounding to 5; 18k gold returns quote-on-request, never a number.
- Transliteration: dictionary names map exactly; rule-based fallback
  produces valid Arabic for unseen names.

## 5. Generative components (concept imagery, LLM skills)

These are *not* golden-testable. Controls instead:
- Output is labeled `CONCEPT_ONLY` and cannot enter the manufacturing
  path (kernel-enforced, tested at the grant/policy layer).
- Human review is the promotion gate; no auto-acceptance metric exists by
  design.
- When a model/version changes, rerun the full pytest suite plus a manual
  spot-check of concept outputs; record findings in the changelog.

## 6. End-to-end and UX evals (scripted, not yet in CI)

- Playwright journey: type name → variants render → hero → ZIP link live,
  on mobile viewport, EN and AR/RTL; console-error and a11y sweep across
  9 routes (0 errors / 0 unlabeled at last run).
- Lighthouse on `/design` (see `docs/PERFORMANCE_REPORT.md`).

## Cadence and gates

- Every commit: `pytest tests/ -q` + `npm run build` must pass.
- Before any release: E2E journey + Lighthouse + `npm audit` re-run;
  numbers recorded in `docs/RELEASE_READINESS_REPORT.md`.
- **Open gap (recorded):** the Playwright/Lighthouse evals are scripted
  but not wired into CI — see finding #9 in the baseline audit.
