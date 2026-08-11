# Changelog

## [Unreleased] — improvement/production-uiux-performance (2026-08)

Audit-driven UX, accessibility, performance, and security pass. No
behavioural changes to the design pipeline; production not redeployed.

### Security
- `npm audit fix`: 3 high advisories (nanoid, react-router) → **0**.

### Performance
- Route-level code splitting (`React.lazy` + `Suspense`): initial JS
  318.9 kB → 258 kB shell + on-demand page chunks (5–18 kB).
- CLS 0.268 → **0**: landing showcase panel now reserves its space with
  a skeleton instead of injecting after fetch.
- Self-hosted fonts via `@fontsource` (Cinzel, Montserrat, Noto Sans
  Arabic); Google Fonts `<link>`s removed — no third-party render
  dependency.

### Accessibility (Lighthouse A11y 95 → 100)
- aria-labels on all previously unlabeled controls across DesignStudio,
  Reveal, Command, Studio, Workshop, Custody (12 → 0).
- Accessible names for icon-only links (Instagram, language toggle);
  `aria-pressed` on material/finish toggles; `aria-live` price totals;
  `h1` added to the Reveal showroom.
- Contrast fixes: demo banner → gold/ink (8.55:1); `stone-400` token
  `#98907f` → `#776E5B` (5.04:1 on white); Reveal secondary text →
  `stone-300` on black (11.12:1).

### SEO (92 → 100)
- Meta description + `theme-color` in `ui/index.html`; real
  `ui/public/robots.txt` (SPA rewrite had served HTML for it).

### Documentation
- New audit doc set under `docs/`: PROJECT_AUDIT_BASELINE,
  PRODUCT_REQUIREMENTS_AND_USER_JOURNEYS, UX_UI_DESIGN_SYSTEM,
  AI_SYSTEM_AND_PROMPT_ARCHITECTURE, AI_EVALUATION_PLAN,
  SECURITY_AND_RESPONSIBLE_AI_ASSESSMENT, PERFORMANCE_REPORT,
  REQUIREMENTS_TRACEABILITY_MATRIX, TEST_STRATEGY,
  DEPLOYMENT_AND_ROLLBACK, RELEASE_READINESS_REPORT; this CHANGELOG.

### Known gaps (recorded, not fixed in this pass)
- ESLint not configured; E2E sweep not wired into CI; no app-level rate
  limiting on public preview endpoints. See RELEASE_READINESS_REPORT.

## Earlier (session history, summarized)
- AI Custom Design Studio: deterministic HarfBuzz Arabic typography,
  Diwani-inspired variants, geometry validation, fail-closed trust
  ladder, workshop export package, pricing engine, transliteration,
  CALLIGRAPHER agent + `design.*` skills.
- Customer surfaces: live hosted pipeline (Vercel serverless), FINAL
  DESIGN hero, showroom Reveal screen with AED pricing and WhatsApp CTA,
  landing showcase, mobile-first shell.
