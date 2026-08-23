# UX / UI Design System — BSOS

React 18 + Vite + TypeScript + Tailwind. Bilingual (EN/AR) with full RTL.
All tokens live in `ui/tailwind.config.js`; shared strings in
`ui/src/i18n.tsx`.

## Brand foundations

| Token | Value | Use |
|---|---|---|
| `ink` | `#101010` | Primary text, dark surfaces, showroom background |
| `gold` | `#C5A059` | Brand accent, banner, highlights |
| `gold-deep` | `#8a6d3b` | Small-caps labels |
| `stone-25…900` | warm neutral ramp | Surfaces and text; `stone-400` = `#776E5B` (5.04:1 on white — AA) |
| `deny` / `amber-flag` | red / amber | Policy outcomes only |

Typography: **Cinzel** (display, latin headings), **Montserrat** (body),
**Noto Sans Arabic** (Arabic UI text). All three are self-hosted via
`@fontsource` (imported in `ui/src/main.tsx`) — no external font requests.
Arabic inscriptions in previews are *not* UI fonts; they are real Amiri
outlines rendered by the deterministic pipeline.

## Contrast (measured)

- Banner: gold background + ink text — 8.55:1.
- Secondary text on white: `#776E5B` — 5.04:1.
- Showroom secondary on black: `stone-300` `#c3bcae` — 11.12:1.
- Never place `stone-400` on tinted surfaces without re-checking.

## Components (`ui/src/index.css` + shared components)

- `.card`, `.chip`, `.btn`, `.btn-primary` — `.btn-primary` uses
  `!`-guarded overrides (`!bg-ink !text-stone-25 !border-ink`) because the
  base `.btn` white background is emitted later in the compiled CSS.
- `JewelPreview` (`ui/src/components/JewelPreview.tsx`) — the single
  product-render component: metal gradients (`METAL_STOPS`), engraved vs
  raised vs enamel treatment, face size parsed from the SVG viewBox. Used
  by DesignStudio cards, the FINAL DESIGN hero, and the Reveal screen so
  the piece looks identical everywhere.

## Layout rules

- **Mobile-first.** Phones get a sticky top bar (`lg:hidden`) with
  horizontal nav chips; the sidebar is `hidden lg:flex`. The right-hand
  telemetry rail is `hidden xl:block`.
- **Showroom mode.** Any `/reveal/*` route renders full-bleed on `ink`
  with no operator chrome.
- **Reserved space.** Async panels (landing showcase) always render their
  container (`min-h`) with a skeleton so CLS stays 0.
- **RTL.** Direction flips from the language context; use logical
  properties (`border-e`, `me-*`) — never `left/right` utilities.

## Accessibility standards (enforced, verified 0 violations)

- Every input/select/file control has a visible label or `aria-label`.
- Icon-only links/buttons carry `aria-label` (Instagram, language toggle).
- Toggle groups (materials, finishes) use `aria-pressed`; price totals use
  `aria-live="polite"`.
- One `h1` per view (Reveal: "BEYOND STYLE").
- Route transitions expose `role="status"` fallbacks.

## Motion

Subtle only: material-cycling showcase (2.6 s interval), soft reveal
transitions. No motion carries information; all states are readable
static.

## Voice

Bilingual, concise, honest about status: previews are labeled as previews
(`PREVIEW - PENDING WORKSHOP APPROVAL`); trust-ladder states use the same
wording in UI, API, and exports.
