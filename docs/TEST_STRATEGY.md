# Test Strategy — BSOS

## Layers

1. **Backend unit + integration (`pytest tests/`, 104 passing).**
   Kernel/policy/grants/ledger suites plus `tests/test_design_studio.py`
   (18 tests): typography goldens (زهران reference, 29-name battery,
   diacritics skeleton, empty input), geometry (item frames, descender
   centering), trust ladder ordering, export package contents, grant
   isolation, transliteration, pricing (floor, tiers, rounding,
   quote-on-request).
2. **Architectural invariants.** `tests/test_import_graph.py` walks the
   AST and fails the build if `agents/`, `skills/`, or `orchestrator/`
   import `bsos.adapters` directly — only the composition root may.
3. **Type safety + build.** `npm run build` runs `tsc` (strict) then
   Vite; a type error fails the build. This substitutes for ESLint until
   finding #8 is closed.
4. **E2E journeys (Playwright, scripted, local).** 9-route sweep
   asserting: zero console errors, zero unlabeled controls, zero unnamed
   icon links; plus the customer journey (type name → verified variants →
   FINAL DESIGN hero → ZIP links present) on a mobile viewport in EN and
   AR/RTL. Chromium at `/opt/pw-browsers/chromium`.
5. **Performance lab.** Lighthouse 12 mobile emulation against the
   production build with the real pipeline mounted (see
   `docs/PERFORMANCE_REPORT.md`).
6. **Production smoke.** After each deploy: `/api/studio/health`, a
   preview request, and one ZIP export fetched from the deployed URL.

## Principles

- Golden tests for everything deterministic; the manufacturing path must
  never depend on statistical behaviour.
- Fail-closed regressions get a named regression test (e.g. the
  camelCase glyph-name incident produced the 29-name battery).
- No simulated results: numbers quoted in docs come from actual runs,
  with commands recorded.

## Commands

```bash
pytest tests/ -q            # backend, 104 tests
cd ui && npm run build      # type-check + production build
cd ui && npm audit          # supply chain (0 vulnerabilities)
```

## Gaps and plan (recorded)

- **CI wiring (finding #9):** add a GitHub Actions workflow running
  pytest + npm build + npm audit on push, and the Playwright sweep
  against a built preview. Not yet present.
- **ESLint (finding #8):** adopt flat-config ESLint with
  typescript-eslint + jsx-a11y to lock in the a11y wins mechanically.
- **Visual regression:** JewelPreview renders are stable SVG; snapshot
  testing would catch unintended render changes cheaply.
