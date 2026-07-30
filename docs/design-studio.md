# AI Custom Design Studio — استوديو التصميم المخصص

Turns a customer's name or phrase into jewellery artwork whose spelling is
**provable, not plausible**, and into workshop-ready vector files. Lives in
`bsos/design_studio/` (engine) + `bsos/skills/design_studio.py` (kernel
skills) + the **Design Studio** UI workspace (`/design`).

## The load-bearing principle

Arabic spelling is NEVER trusted to an image-generation model. The pipeline
is deterministic end to end:

1. **Normalize** — Unicode NFC; zero-width/control characters stripped.
2. **Shape** — HarfBuzz with the approved font's own OpenType GSUB/GPOS
   rules (contextual forms, ligatures, RTL).
3. **Verify structurally** — every input codepoint's cluster must produce a
   glyph whose name maps back to the expected base letter
   (ز → `zain-ar*`, ه → `heh-ar*`, …). Any mismatch, missing glyph, or
   direction anomaly → `human_review`. Fail-closed; there is no visual-guess
   path.
4. **Compose** — three Diwani-*inspired* variants (luxury / balanced /
   manufacturing-optimized) in millimetres inside the item frame. The
   manufacturing variant applies real geometric stroke reinforcement
   (shapely outward buffering), not a label.
5. **Validate** — shapely geometry checks against configurable workshop
   rules: min positive stroke (erosion survival), min negative gap (dilation
   merging), edge clearance, tiny islands, closure/validity, scale sanity.
6. **Approve** — a recorded human decision (`design.approve`), provenanced.
7. **Export** — SVG (mm) + mirrored SVG, layered DXF R2010 (mm), Illustrator-
   compatible vector PDF (no native `.AI` claimed), technical PDF with the
   validation report, deterministic PNG renders (flat, enamel macro,
   cufflink pair) and a manifest.

## The trust ladder (status, fail-closed in skills)

```
draft → typography_verified → variants_composed → manufacturing_checked
      → workshop_approved          (failures → human_review)
```

- An AI concept image can never advance this ladder or become a production
  file.
- `design.export_package` refuses anything not `workshop_approved`, and
  re-validates geometry before writing files.
- Every rung appends to the hash-chained provenance store
  (`design-<project>` chain, `/api/design/audit/{id}`).

## Honesty constraints (encoded, not aspirational)

- Variants carry `authenticity: "Diwani-INSPIRED … not certified traditional
  Diwani Jali"`; the luxury variant is flagged
  `expert_review_recommended: true` for calligrapher review.
- Fonts come from `bsos/design_studio/registry.json` only — an approved-font
  registry with full licensing metadata (SIL OFL 1.1 Amiri vendored with its
  licence). No runtime font downloads; no commercial binaries without
  confirmed licensing (NotoKufiArabic is listed `review-required` and
  unusable until vendored).

## Workshop rules (configurable per frame, defaults for 20 mm cufflink)

| Rule | Default |
|---|---|
| face diameter | 20.0 mm |
| safe diameter | 17.0 mm |
| edge clearance | 1.5 mm |
| min positive stroke | 0.70 mm |
| min negative gap | 0.45 mm |

## Reference test

`tests/test_design_studio.py` runs the زهران cufflink reference end to end:
letter sequence ز ه ر ا ن, structural verification, three variants, real
geometry validation (including a proof that shrinking the rules flips the
verdict), the fail-closed ladder, grant isolation (only the `calligrapher`
agent holds `design.*`), and the full export package.

## Agent

`calligrapher` — allow `design.*`, `brain.search`; deny generation, library,
vision, graph and catalogue-export tools. The twelve specialist roles from
the studio specification map onto BSOS agents: intake/typography/composition
→ calligrapher; concept imagery → designer (concept-only, P1/P5 still
apply); manufacturability & specs → producer; exports/publication →
publisher; custody & licences → custodian; memory/audit → kernel services.
