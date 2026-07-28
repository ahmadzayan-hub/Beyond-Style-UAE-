# BSOS Compliance

The compliance rules are **kernel middleware**, not agent instructions. Every
tool call crosses the guard, every policy evaluation (passes included) is
written to an append-only, hash-chained ledger, and capability grants make
whole classes of violation structurally impossible before any rule runs.

## The eight policies

**P1 — NO_IMAGE_TO_GENERATOR.** The image generator accepts
`generate_image(prompt: str, model: str)` and nothing else. The kernel
rejects any generation payload carrying bytes, file paths, base64, data URIs
or URLs; the adapter re-validates the prompt text. The Designer additionally
holds no grant that can return image bytes, so there is no code path from an
image to the generator.

**P2 — LICENCE_REQUIRED.** No third-party asset is ingested, copied or
exported without an active licence row: signed document present on disk,
`valid_to` in the future, scope covering the requested use. Denials name the
missing or failing licence.

**P3 — PROVENANCE_MINIMUM.** A brief cannot be promoted to generation while
any attribute has fewer than three independent source records. Offending
attributes are dropped, logged as `insufficient_provenance`, and the brief
returns to review.

**P4 — CORPUS_FLOOR.** Synthesis and briefing are blocked until the corpus
holds at least 40 references across at least 12 distinct sources. The denial
reports current counts and the shortfall.

**P5 — NO_AI_PUBLICATION.** Nothing with `origin = ai_generated` reaches
`exports/catalogue/`, social exports, product listings, or any
customer-facing document. AI renders write only to
`exports/internal_concepts/`, carry `CONCEPT_ONLY` in filename and image
metadata, and no skill exposes a way to change an asset's origin. The
workshop state machine independently requires an uploaded workshop
photograph before `catalogue_ready`.

**P6 — NO_UNVERIFIED_MATERIAL_CLAIMS.** Metal, purity, plating, stone,
carat and weight fields are writable only with a `verified_source`
reference; otherwise they are set to `pending_workshop_verification`.

**P7 — NO_SCRAPING.** Outbound calls to Instagram/Meta domains must target
the official Graph API with a valid OAuth token. A denylist of scraper
libraries fails the build if one enters the dependency tree
(`tests/test_import_graph.py`).

**P8 — CONTEXT_SEPARATION.** Beyond Style / BCGT commercial data never
shares a record, file path or export bundle with RTA or public-sector
context. This policy evaluates on **every** tool call.

Rule enablement is not configurable: attempting to disable P1–P8 in
`kernel/policies.yaml` fails the load. Thresholds are tunable; every change
writes a ledger entry with old value, new value, actor, timestamp and reason.

## Escalations (pause + decision card, never silent)

- a licence expiring within 30 days, listing affected assets
- a concept passing the originality gate within 0.03 of the threshold
- a source database contradicting an established Beyond Style policy
  (e.g. the AED 265 starting-price floor)
- a supplier asset carrying another party's brand mark or an unverified
  material claim

## What the manifest and ledger record

Every catalogue export writes `MANIFEST.csv`: filename, origin, source,
licence id, licence scope, permalink, export timestamp. The ledger records
every tool call (agent, tool, grant check, each policy evaluation with
outcome, duration, result) in a hash chain verifiable with
`make verify-ledger`. Per concept, an append-only provenance chain records
the corpus snapshot, contributing sources per attribute, the exact prompt,
model id and version, all similarity scores, the gate result, approver and
timestamps — exportable as a PDF (`bsos audit`, Studio → provenance PDF).

## What BSOS does not do

- It does not scrape Instagram or any Meta property, in any mode.
- It does not feed images — licensed or otherwise — into an image generator.
- It does not publish AI-generated imagery to customers, ever, under any
  configuration.
- It does not state materials, purity or weight it has not verified.
- It does not resolve pricing contradictions silently, remove detected brand
  marks, or delete/rewrite audit history.
- It does not mix Beyond Style commercial work with RTA/public-sector data.
