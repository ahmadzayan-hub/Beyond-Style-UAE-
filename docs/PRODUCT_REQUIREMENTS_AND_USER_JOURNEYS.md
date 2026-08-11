# Product Requirements and User Journeys — BSOS / AI Custom Design Studio

Beyond Style UAE (Dubai) sells personalised jewellery and gifts with an
in-house workshop. Instagram: `beyond.style.uae` · WhatsApp business:
`+971 55 561 5509`.

## Personas

| Persona | Needs |
|---|---|
| **Customer** (in showroom or on phone) | See their name as a finished piece, understand price, decide, order via WhatsApp |
| **Sales associate** | Generate variants live in front of the customer, present pricing, capture the order |
| **Workshop craftsman** | Manufacturable files (DXF/technical PDF) with verified geometry, mirrored engraving masters |
| **Owner/operator** | Fail-closed compliance: nothing reaches the workshop without typography verification + human approval |

## Functional requirements (implemented)

- **FR-1 Deterministic Arabic typography.** Inscriptions are shaped with
  HarfBuzz + real font outlines (Amiri, SIL OFL). No image model ever
  generates or "fixes" Arabic letterforms. Diacritics are stripped
  (skeleton is engraved); mixed-script input forces an explicit choice.
- **FR-2 Trust ladder (fail-closed).** `ai_concept → typography_verified →
  manufacturing_checked → workshop_approved`. Any validation failure lands
  in `human_review` with bilingual issue text. Approval mints
  `BS-DS-{id}-{code}` and is provenance-chained.
- **FR-3 Variants.** Diwani-inspired presets (classic, flowing,
  minimal_modern, manufacturing_optimized) composed onto item-specific
  frames (cufflink 20 mm, pendant 24, ring 14, brooch 30, coin 32,
  bracelet 22, corporate gift 40).
- **FR-4 Exports.** ZIP package: preview PNG, mirrored engraving master,
  SVG/mirrored SVG, vector PDF, technical PDF, DXF (R2000) with dimensions.
  Hosted-preview files carry `PREVIEW - PENDING WORKSHOP APPROVAL` on the
  DXF NOTES layer, technical PDF, and filenames.
- **FR-5 Pricing.** Rules-as-data AED engine (item base, material
  multiplier, variant factor, finish adder, per-letter, quantity tiers,
  265 AED floor, rounding to 5). 18k gold is quote-on-request. Client
  mirror gives instant totals; server `design.quote` is the provenanced
  source of truth.
- **FR-6 Transliteration.** Latin → Arabic name suggestion (dictionary of
  ~70 common names + rule-based digraphs) so non-Arabic speakers can order.
- **FR-7 Bilingual, RTL, mobile-first.** Full EN/AR UI, RTL layout, top-bar
  navigation on phones, showroom Reveal screen with no operator chrome.

## Non-functional requirements

- Fail-closed everywhere; no silent downgrade of a failed check.
- Hosted preview is stateless (recompute from inscription); kernel
  workflows (custody, approvals, ledger) run locally via `make dev`.
- Accessibility: labeled controls, WCAG AA contrast, zero console errors.
- Performance: route-level code splitting; Lighthouse targets in
  `docs/PERFORMANCE_REPORT.md`.

## User journeys (verified end-to-end)

### J1 — Customer live design (hosted, mobile)
1. Open `/design` → type a name (Arabic, or Latin → transliteration
   suggestions appear) → choose item type.
2. Real pipeline shapes/validates → verified variants render as product
   previews (metal + finish selectable).
3. FINAL DESIGN hero shows the chosen variant as a jewel render; price
   panel updates instantly (AED).
4. Download all (ZIP) or individual formats — every file extractable,
   PREVIEW-marked.
5. CTA → WhatsApp `wa.me/971555615509` with a prefilled summary.

### J2 — Showroom reveal (`/reveal/live?text=…&item=…`)
Full-bleed black screen: the piece, material toggles, quantity, price, and
WhatsApp CTA — what the customer sees on the studio screen.

### J3 — Workshop approval (local kernel)
`design.project_create → design.compose → design.validate →
design.approve (human) → design.export_package`. Grants restrict the
CALLIGRAPHER agent to `design.*` + `brain.search`; every step is ledgered.

### J4 — Operator monitoring
Command workspace: policy feed, escalations, live metrics; escalation
approve/reject resolves through the kernel.

## Out of scope (recorded)
- Payments/checkout (WhatsApp order flow instead — deliberate for this market).
- Saved customer accounts on the hosted preview (stateless by design).
- Native `.ai` files (never claimed; vector PDF/SVG/DXF provided).
