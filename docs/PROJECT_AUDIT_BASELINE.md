# Project Audit Baseline — BSOS / AI Custom Design Studio

Audit branch: `improvement/production-uiux-performance` · Date: 2026-08 ·
Auditor: automated + manual review inside the repository.

## Executive summary

BSOS is a kernel-enforced agentic OS for Beyond Style UAE (personalised
jewellery). The audited surface: Python 3.11 / FastAPI / SQLModel backend
with a policy kernel (P1–P8), the deterministic Design Studio pipeline
(HarfBuzz typography → geometry validation → exports → pricing), a React 18
/ Vite / Tailwind bilingual UI, and a Vercel hosted preview (static UI +
serverless Python pipeline). At baseline the system was functional with a
passing test suite; the audit found no Critical defects, four High/Medium
defects (all fixed in this pass), and several documented limitations.

## Scope note (recorded assumption)

The audit prompt referenced AIB901 course files (business-plan templates,
McKinsey AI notes, etc.). **None of these files exist in this repository**,
and this codebase is a jewellery design studio, not a business-plan
generator. The gap is recorded here as instructed; requirements were taken
from the repository itself (README, ARCHITECTURE.md, COMPLIANCE.md,
docs/design-studio.md) and the studio specification driven in-session.

## Baseline measurements (before this pass)

| Check | Result |
|---|---|
| Backend tests (`pytest tests/ -q`) | 104 passed |
| UI type-check + build (`npm run build`) | clean |
| `npm audit` | **3 high** (nanoid; react-router RSC CSRF advisory) |
| Console errors (9 routes, Playwright) | 1 per route (Google Fonts blocked in sandbox; third-party render dependency in prod) |
| Unlabeled form controls (9 routes) | 12 total |
| Icon links without accessible names | 2 |
| `meta description` | missing |
| robots.txt | missing (SPA rewrite served HTML → 22 robots errors) |
| Lighthouse (/design, local prod build, mobile emulation) | Perf 73 · A11y 95 · BP 100 · SEO 92 |
| Core Web Vitals (lab) | LCP 3.4 s · **CLS 0.268** · TBT 30 ms |
| Initial JS bundle | 318.9 kB (100.4 kB gzip), no code splitting |
| ESLint | **not configured** (missing control, recorded) |
| E2E in CI | **not present** (journeys verified via Playwright scripts in-session; recorded gap) |

## Findings and classification

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | High | 3 high npm advisories (nanoid, react-router) | **Fixed** — `npm audit fix`, 0 vulnerabilities |
| 2 | High | CLS 0.268 on /design (showcase panel injected after fetch) | **Fixed** — reserved panel space; CLS now 0 |
| 3 | Medium | 12 unlabeled inputs, 2 unnamed icon links, missing h1 on showroom | **Fixed** — aria-labels/headings; sweep now 0 |
| 4 | Medium | Contrast failures: banner 3.61:1, secondary text 3.0–3.2:1 | **Fixed** — gold/ink banner (8.55:1), stone-400 token → #776E5B (5.04:1), showroom text bumped a step lighter on black |
| 5 | Medium | Google Fonts third-party render dependency | **Fixed** — self-hosted via @fontsource; zero external font requests |
| 6 | Medium | Missing meta description, robots.txt | **Fixed** — SEO 100 |
| 7 | Medium | No route-level code splitting (319 kB initial JS) | **Fixed** — React.lazy per page; initial 258 kB, pages 5–18 kB on demand |
| 8 | Low | ESLint not configured | Open — recorded; build enforces TS strictness |
| 9 | Low | No E2E suite in CI | Open — journeys scripted with Playwright locally; not wired into CI |
| 10 | Low | Public serverless preview endpoints have no rate limiting (platform-level only) | Open — documented in security assessment |
| 11 | Info | Hosted preview is stateless by design (no saved projects/approvals) | By design — full workflow runs locally |

## After this pass (verified)

- Lighthouse /design: **Perf 83 · A11y 100 · BP 100 · SEO 100**; CLS **0**, TBT 40 ms
- Console errors across 9 routes: **0** · unlabeled controls: **0** · unnamed links: **0**
- `npm audit`: **0 vulnerabilities** · backend: **104 tests passing**
- Live generation journey (type name → verified variants → hero → ZIP links) passes on mobile viewport, EN and AR/RTL.

Reproduction commands are listed in docs/RELEASE_READINESS_REPORT.md.
