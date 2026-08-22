# UI Generation Prompt — Beyond Style UAE Design Studio

Paste the prompt below into an AI design-generation tool to produce UI
concepts consistent with the shipped product. Source of truth for tokens
and components: `docs/UX_UI_DESIGN_SYSTEM.md`.

---

## PROMPT

You are designing the user interface for **Beyond Style UAE — AI Custom
Design Studio**, a luxury personalised-jewellery web app for a Dubai
brand (Instagram: beyond.style.uae). Customers type a name in Arabic or
English and instantly see it as a finished piece of jewellery — cufflinks,
pendant, ring, brooch, coin, bracelet, or corporate gift — with live AED
pricing and downloadable design files. Orders close over WhatsApp, not a
cart. Design every screen mobile-first, fully bilingual English/Arabic
with true RTL mirroring.

### Brand identity

- Mood: quiet luxury, Arabian craft heritage meets precision engineering.
  Think jewellery-atelier, not e-commerce. Generous whitespace, restrained
  motion, no gradients except on metal renders.
- Colors: ink black `#101010` (primary text, showroom background), brand
  gold `#C5A059` (accents, highlights, CTA emphasis), deep gold `#8a6d3b`
  (small uppercase tracking labels), warm stone neutrals from `#FAF9F6`
  (page background) through `#776E5B` (secondary text) — never pure grey.
  Status colors: deep red for "needs review", amber for "escalated",
  green only for verified/approved.
- Typography: Cinzel (display serif, Latin headings, letter-spaced
  uppercase), Montserrat (body, UI labels), Noto Sans Arabic (Arabic UI
  text). All contrast must meet WCAG AA.

### CRITICAL constraint — Arabic calligraphy

Never draw, generate, or stylize Arabic letterforms yourself. The real
product renders inscriptions with a deterministic typography engine and
places them as SVG. In your designs, represent every inscription as a
**placeholder: an elegant circular medallion frame containing a smooth
abstract calligraphic squiggle**, clearly marked as a content slot. Do not
attempt readable Arabic script anywhere.

### App shell

- Phone: sticky top bar — small round brand logo, "Beyond Style" in
  Cinzel, a compact language toggle (EN ⇄ ع), and below it a horizontally
  scrollable row of pill-shaped nav chips (active chip = ink background,
  white text). Content fills the rest of the viewport, single column.
- Desktop (≥1024px): left sidebar 224px, white, logo + wordmark +
  "BSOS · AGENTIC OS" micro-label in deep gold, vertical nav with icons
  (Command, Custody, Corpus, Trends, Studio, Design Studio, Workshop),
  language button pinned at bottom. Optional right rail (≥1280px) with
  live "policy feed" and "escalations" cards for operators.
- A slim gold banner may sit above everything: dark text on gold, one
  sentence, dismissible feel.

### Screen 1 — Design Studio (`/design`, the hero screen)

Top to bottom:
1. **Landing showcase**: a dark ink panel, rounded-2xl, showing one
   jewellery piece (circular medallion with the calligraphy placeholder)
   rendered as polished metal — the metal cycles subtly between yellow
   gold, rose gold, and silver. Title in Cinzel, one-line promise
   underneath ("Your name, engraved as art — priced instantly").
2. **Input row**: one large text field ("Type a name — عربي or English"),
   an item-type select (cufflinks, pendant, ring, brooch, coin, bracelet,
   corporate gift), and a gold-accented "Generate" primary button (ink
   background, light text). Enter key submits. Under it, small helper
   text: "English name? We'll suggest the Arabic spelling."
3. **Transliteration strip** (conditional): when the user typed Latin
   letters, show 2–4 Arabic-spelling suggestion chips with a small
   "verified" check on the ones the engine can engrave.
4. **Results — three variant cards** in a responsive grid (1-col phone,
   3-col desktop): each card shows the piece as a product render
   (medallion + placeholder), variant name EN+AR ("Luxury Diwani Jali",
   "Balanced Diwani", "Manufacturing-Optimized"), a verified-spelling
   badge, and "from AED 275" price. Selected card gets a gold ring
   outline.
5. **FINAL DESIGN hero**: a large presentation panel of the selected
   variant — big product render on ink background, material swatch dots
   (yellow gold, rose gold, silver, brushed steel), finish toggle
   (polished / brushed / enamel), and a live price line in AED that
   updates instantly. Quantity stepper. 18k gold shows "price on
   request" instead of a number.
6. **Download row**: primary button "Download all files (ZIP)" plus small
   labeled chips: PNG, SVG, Mirrored SVG, Vector PDF, Technical PDF, DXF.
   A subtle caption: "Files are watermarked PREVIEW until workshop
   approval."
7. **WhatsApp CTA**: pill button in WhatsApp green with logo — "Order on
   WhatsApp" — prefilled summary implied.

States to design: empty (before first generate), loading ("generating"
shimmer on the three card slots), spelling-needs-review (bilingual notice
card, red-tinted, with the issues listed), mixed-script picker (two
buttons: "Engrave the Arabic part" / "Engrave the English part").

### Screen 2 — Showroom Reveal (`/reveal`)

A full-bleed, chrome-less presentation screen shown to the customer on a
studio display or phone. Pure black background. Centered: "BEYOND STYLE"
in Cinzel letter-spaced caps, the jewellery piece large and dramatic
(placeholder medallion, metallic render), material dots, quantity
selector, a large elegant price ("AED 345", with "per piece" caption),
and two actions: gold-outlined "Order on WhatsApp" and a subtle Instagram
icon link. Secondary text is warm light stone `#c3bcae`, never grey.
This screen must feel like a jewelry reveal moment — cinematic, minimal.

### Screen 3 — Operator workspaces (brief)

Same shell, light background, information-dense but calm: Command
(metrics cards + live event feed), Workshop (spec cards with
approve/reject decision buttons), Custody (asset table with licence
chips). Cards are white, rounded, 1px warm-stone borders, no shadows
heavier than sm.

### Interaction and accessibility rules

- Everything reachable and labeled: every icon-only control has a
  hidden label; toggles show pressed state; price updates announce
  politely.
- RTL: when Arabic is selected the entire layout mirrors (nav, cards,
  text alignment); numbers and prices stay LTR.
- Async panels always reserve their space with a skeleton — nothing may
  shift the layout after loading.
- Motion: gentle fades and the metal-cycling showcase only; nothing
  bounces.

Deliver: mobile (390px) and desktop (1440px) versions of Screens 1 and 2,
plus the loading / needs-review / mixed-script states of Screen 1.
