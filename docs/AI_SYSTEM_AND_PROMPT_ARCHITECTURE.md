# AI System and Prompt Architecture — BSOS

## Governing principle

**The kernel enforces; the prompt does not.** Model output is never
trusted for anything with a compliance or manufacturing consequence.
Policies P1–P8 are middleware on the tool-call path (`bsos/kernel/`), and
agents hold capability grants — see `ARCHITECTURE.md` and `COMPLIANCE.md`.

## Where AI is (and is not) used

| Concern | Mechanism | AI involved? |
|---|---|---|
| Arabic letterforms | HarfBuzz shaping + Amiri glyph outlines (`bsos/design_studio/typography.py`) | **No — deterministic.** Image models never draw or "fix" Arabic script |
| Geometry / manufacturability | shapely erosion–dilation, edge clearance, stroke width (`validation.py`) | No — deterministic |
| Pricing | Rules-as-data engine (`pricing.py`) | No — deterministic |
| Transliteration | Dictionary + digraph rules (`transliteration.py`) | No — deterministic |
| Concept imagery | `generate.image` (Nano Banana family), text-only in | Yes — output is `CONCEPT_ONLY`, never a production asset |
| Photo/video recognition | `vision.extract` → attribute JSON only | Yes — structured extraction only |
| Trend synthesis / chat | `bsos/adapters/llm.py` (Ollama local or Anthropic API) | Yes — behind kernel grants |

## Agent roster and grants

Six agents (`bsos/agents/`): custodian, analyst, designer, producer,
publisher, **calligrapher**. The CALLIGRAPHER agent is granted only
`design.*` + `brain.search`; a grant violation is ledgered and rejected
(covered by tests). Prompts live beside each agent; they describe intent,
never authority — authority is the GrantSet.

## Trust ladder (fail-closed)

```
ai_concept → typography_verified → manufacturing_checked → workshop_approved
```

- Every promotion requires its check to pass; any failure → `human_review`
  with bilingual issues (`issues` / `issues_ar`).
- Glyph verification is fail-closed: a glyph name that cannot be matched
  to an expected Arabic stem (case-insensitive; Amiri uses camelCase like
  `tehMarbuta-ar`) blocks promotion rather than passing silently.
- Empty/whitespace inscriptions are rejected before shaping (422 on the
  API; `human_review` in the engine).
- `workshop_approved` requires a human decision through `design.approve`,
  minting `BS-DS-{id}-{code}` into the hash-chained provenance ledger
  (`design-<id>` chains).

## Font policy

Approved registry only (`bsos/design_studio/fonts/registry.json`), SIL OFL
licences, vendored in-repo — **no runtime font downloads**. Adding a font
is a code change with licence review, not a config toggle.

## Hosted preview boundary

The Vercel serverless function (`deploy/vercel/studio.py`) runs the same
deterministic pipeline statelessly. It cannot approve: every export is
watermarked `PREVIEW - PENDING WORKSHOP APPROVAL` (DXF NOTES layer,
technical PDF, filenames). Approval, custody, and the ledger exist only in
the local kernel deployment.

## Prompt-injection posture

Because letterforms, validation, pricing, and exports are deterministic,
prompt injection cannot alter what the workshop receives. LLM-touching
skills are read/annotate-only or concept-only, and every call passes the
kernel policy gate regardless of what the prompt says.
