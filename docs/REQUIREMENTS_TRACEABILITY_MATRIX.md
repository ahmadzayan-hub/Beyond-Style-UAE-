# Requirements Traceability Matrix — BSOS / Design Studio

Requirement IDs from `docs/PRODUCT_REQUIREMENTS_AND_USER_JOURNEYS.md`.
Test references are in `tests/test_design_studio.py` unless noted.

| Req | Implementation | Tests / evidence | Status |
|---|---|---|---|
| FR-1 Deterministic Arabic typography | `bsos/design_studio/typography.py` (HarfBuzz shape, NFC + tashkeel strip, fail-closed glyph verify) | زهران golden; 29-name battery; diacritics skeleton; empty-input guard | ✅ |
| FR-1 Mixed-script handling | `deploy/vercel/studio.py` preview endpoint; DesignStudio picker | mixed-script API test; manual EN/AR journey | ✅ |
| FR-2 Trust ladder fail-closed | `bsos/skills/design_studio.py` status ladder; `validation.py` | ladder-order test; failed-validation → human_review test | ✅ |
| FR-2 Human approval + provenance | `design.approve` minting `BS-DS-{id}-{code}`; `design-<id>` hash chain | approval/export ladder test; provenance chain test | ✅ |
| FR-2 Grant isolation | CALLIGRAPHER GrantSet (`design.*`, `brain.search`) | grants isolation test (violation ledgered) | ✅ |
| FR-3 Variants + item frames | `composition.py` VARIANT_SPECS, FRAME_PRESETS, ink-bounds fitting | item-frames test; descender centering battery | ✅ |
| FR-4 Export package | `exports.py` (8 files + manifest); ZIP streaming in serverless | export-package test; live ZIP download verified on production URL | ✅ |
| FR-4 PREVIEW watermark | `export_dxf(note=…)`, technical PDF, filenames | code path + downloaded-file inspection | ✅ |
| FR-5 Pricing engine | `pricing.py` PRICING_RULES + `estimate`; `design.quote`; client mirror in `ui/src/demo.ts` | pricing goldens (floor, tiers, rounding, 18k quote-on-request) | ✅ |
| FR-6 Transliteration | `transliteration.py`; `/api/studio/transliterate` | transliteration tests (dictionary + rules) | ✅ |
| FR-7 Bilingual RTL mobile-first | `ui/src/i18n.tsx`; App.tsx top bar; Reveal showroom | Playwright sweep EN+AR mobile viewport; a11y sweep 0 issues | ✅ |
| NFR A11y (labels, contrast, h1) | aria-labels across pages; contrast tokens | Lighthouse A11y 100; sweep 0 unlabeled | ✅ |
| NFR Performance | code splitting; CLS reservation; self-hosted fonts | Lighthouse 83/100/100/100, CLS 0 | ✅ |
| NFR Supply chain | `npm audit fix`; pinned Python deps; vendored fonts | `npm audit` 0 vulnerabilities | ✅ |
| NFR Stateless hosted preview | `deploy/vercel/studio.py` recompute-from-inscription | health endpoint; no storage in function | ✅ |
| Kernel P1–P8 policies | `bsos/kernel/` middleware | kernel/policy suite (part of the 104) | ✅ |
| ESLint control | — | — | ⚠️ Open (finding #8) |
| E2E in CI | Playwright scripts (session scratchpad) | run locally, evidence in audit docs | ⚠️ Open (finding #9) |
| Rate limiting on public endpoints | Vercel platform defaults only | — | ⚠️ Open (finding #10) |

**Coverage summary:** all functional requirements traced to code and at
least one automated test or verified live journey; 3 non-functional gaps
remain open and are carried in `docs/RELEASE_READINESS_REPORT.md`.
