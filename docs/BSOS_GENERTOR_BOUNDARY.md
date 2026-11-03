# BSOS vs. Genertor — product boundary

Both repos contain a jewellery design-generation pipeline, which has caused
confusion about which one owns customer-facing design generation. This
document fixes the boundary so the two stop being read as competing
implementations of the same feature.

## The two repos

| | `Beyond-Style-UAE-` (BSOS) | `Beyond-Style-UAE-design-Genertor` |
|---|---|---|
| Role | Internal-operations / compliance kernel | Customer-facing product |
| What it is | A kernel-enforced agentic OS: orchestrator, agents (custodian, analyst, designer, producer, publisher, calligrapher), skills registry, policy kernel (P1–P10), Second Brain, metrics/ledger | A production design generator: recipe-driven CAD intent, workshop rule gates, bilingual UI, deployed to customers |
| Who uses it | Beyond Style's own team, running the business loop (market signal → concept → spec → prototype → catalogue) | End customers placing a custom piece |
| Contains a design engine? | Yes — `bsos/design_studio/` (deterministic Arabic typography, geometry validation, exports) | Yes — its own recipe-driven CAD intent pipeline |

## Why both have a "design studio"

BSOS's `bsos/design_studio/` module predates the decision to spin out a
dedicated customer product. It was built as one of BSOS's internal skills
(`design.*`, kernel-guarded, used by the **designer** agent as part of the
market-signal-to-catalogue loop) — not as the customer-facing ordering
surface. Genertor was then built separately as that customer-facing surface,
with its own CAD-intent pipeline and workshop gates, and is the one that
gets deployed to customers and iterated on for conversion, pricing, and
checkout.

They independently implement overlapping jewellery-design logic (Arabic
typography verification, geometry/workshop-tolerance validation) because
they were not originally planned as one system. That duplication is a real
engineering-debt item, not a design decision — see "Open duplication" below.

## The boundary, stated as a rule

- **BSOS owns**: compliance enforcement (the P1–P10 kernel gates — child
  safety, exact Arabic calligraphy, licensing, provenance), the agent
  orchestration loop, internal tooling (Second Brain, progress/session
  logs, metrics), and anything run by or for the Beyond Style team rather
  than shown to a customer.
- **Genertor owns**: the customer-facing ordering/design flow — the UI a
  customer actually uses to request and approve a piece, its CAD-intent
  recipe pipeline, and its own workshop rule gates for that flow.
- **masaar owns**: the canonical order console (quotes → orders → payments
  → invoices) once a design is approved — neither BSOS nor Genertor owns
  order/payment lifecycle.

## Open duplication (not resolved by this document)

`bsos/design_studio/` and Genertor's CAD-intent pipeline both independently
verify Arabic calligraphy and validate workshop geometry. Per the standing
compliance mandate, the *rules* (child-safety, exact-Arabic-calligraphy)
were ported from BSOS's sibling repo
(`Beyond-Style-UAE-Agentic-Product-Design-Operating-System`, now archived)
into BSOS itself via PR #5 (merged 2026-11-02) — but that port did not touch
Genertor, so Genertor's own gates are a second, separately-maintained
implementation of adjacent rules. Recommendation for a follow-up (not done
here, as it is a cross-repo code change, not a documentation reconciliation):
decide whether Genertor should call into BSOS's `design.*` skills over an
API rather than re-implementing calligraphy/geometry verification, or
whether the duplication is intentionally kept for deployment independence
(Genertor ships to customers on its own schedule; BSOS does not deploy
automatically — see `docs/DEPLOYMENT_AND_ROLLBACK.md`). This is a build
decision for Ahmed, not an engineering default.
