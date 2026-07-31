/**
 * Demo-preview mode (VITE_DEMO=1 builds, e.g. the hosted Vercel preview).
 *
 * Serves the interface with clearly-labelled SAMPLE data and disables
 * mutations. The real system is the local install (`make dev`): the kernel,
 * policies, ledger, and asset library are local-first by design and do not
 * run on a static host.
 */

import type { FeedEvent } from "./api";

export const DEMO = import.meta.env.VITE_DEMO === "1";

const now = () => new Date().toISOString();

const ASSETS = [
  { id: "demo0001", filename: "asset1.png", origin: "workshop_photograph", source_handle: "beyond_style_workshop", licence_id: "OWN", flags: [], review_state: "clear", category: "necklaces", width: 1200, height: 1200 },
  { id: "demo0002", filename: "asset2.png", origin: "workshop_photograph", source_handle: "beyond_style_workshop", licence_id: "OWN", flags: [], review_state: "clear", category: "bracelets", width: 1200, height: 1200 },
  { id: "demo0003", filename: "asset3.png", origin: "workshop_photograph", source_handle: "beyond_style_workshop", licence_id: "OWN", flags: [], review_state: "clear", category: "rings", width: 1200, height: 1200 },
  { id: "demo0004", filename: "asset4.png", origin: "supplier_authorised", source_handle: "supplier_atelier_a", licence_id: "LIC-2026-004", flags: [], review_state: "clear", category: "necklaces", width: 1080, height: 1080 },
  { id: "demo0005", filename: "asset5.png", origin: "business_discovery", source_handle: "market_account_b", licence_id: "LIC-2026-007", flags: ["brand_mark_detected"], review_state: "mark_review", category: "bracelets", width: 1080, height: 1350 },
  { id: "demo0006", filename: "asset6.png", origin: "manual_inbox", source_handle: "supplier_atelier_c", licence_id: "LIC-2026-009", flags: ["near_duplicate"], review_state: "duplicate_review", category: "rings", width: 900, height: 900 },
];

const REF_ATTRS = [
  { form: { silhouette: "pendant drop", dominant_geometry: "teardrop" }, motif: { primary: "arabic name", cultural_register: "khaleeji" }, material_finish: { apparent_metal: "yellow gold tone", finish: "high polish" }, commercial: { occasion: "eid", perceived_tier: "mid", target_segment: "mothers" } },
  { form: { silhouette: "bar", dominant_geometry: "rectangle" }, motif: { primary: "initial letter", cultural_register: "contemporary" }, material_finish: { apparent_metal: "silver tone", finish: "brushed" }, commercial: { occasion: "graduation", perceived_tier: "accessible", target_segment: "young women" } },
  { form: { silhouette: "cuff", dominant_geometry: "organic curve" }, motif: { primary: "palm frond", cultural_register: "minimal" }, material_finish: { apparent_metal: "rose gold tone", finish: "matte" }, commercial: { occasion: "wedding", perceived_tier: "premium", target_segment: "mothers" } },
  { form: { silhouette: "charm cluster", dominant_geometry: "circle" }, motif: { primary: "falcon", cultural_register: "khaleeji" }, material_finish: { apparent_metal: "yellow gold tone", finish: "high polish" }, commercial: { occasion: "birthday", perceived_tier: "mid", target_segment: "men" } },
];

const AUTHENTICITY =
  "Diwani-INSPIRED composition over a licensed base font; not certified traditional Diwani Jali";

const MFG_CHECKS = [
  { check: "geometry_present", ok: true, detail: "area 32.08 mm²" },
  { check: "paths_closed_and_valid", ok: true, detail: "all rings valid" },
  { check: "min_stroke", ok: true, detail: "erosion by 0.35 mm keeps 37% of area (threshold 35%)" },
  { check: "min_gap", ok: true, detail: "6 components -> 4 after 0.23 mm dilation" },
  { check: "edge_clearance", ok: true, detail: "0.000 mm² outside the safe diameter" },
  { check: "tiny_islands", ok: true, detail: "0 island(s) below 0.29 mm²" },
  { check: "scale_and_units", ok: true, detail: "artwork 12.6 × 6.6 mm inside 20.0 mm face" },
];

/** The زهران reference project, produced by the real deterministic pipeline. */
const DESIGN_PROJECT = {
  id: 1,
  inscription: "زهران",
  normalized_inscription: "زهران",
  item_type: "cufflink",
  status: "workshop_approved",
  selected_variant: "manufacturing_optimized",
  approver: "owner",
  created_at: now(),
  frame: { face_diameter_mm: 20, safe_diameter_mm: 17, edge_clearance_mm: 1.5, min_stroke_mm: 0.7, min_gap_mm: 0.45 },
  letter_sequence: [
    { char: "ز", codepoint: "U+0632", name: "ARABIC LETTER ZAIN" },
    { char: "ه", codepoint: "U+0647", name: "ARABIC LETTER HEH" },
    { char: "ر", codepoint: "U+0631", name: "ARABIC LETTER REH" },
    { char: "ا", codepoint: "U+0627", name: "ARABIC LETTER ALEF" },
    { char: "ن", codepoint: "U+0646", name: "ARABIC LETTER NOON" },
  ],
  verification: { passed: true, status: "typography_verified", issues: [] },
  variants: [
    { variant_id: "luxury_diwani_jali", font: "Amiri-Regular", spelling_verified: true, legibility: 0.71, feasibility_hint: 0.55, text_mm: [13.6, 8.9], validation_passed: false,
      meta: { label_en: "Luxury Diwani Jali (inspired)", label_ar: "ديواني جلي فاخر (مستوحى)", expert_review_recommended: true, notes: "rich overlap and curved baseline", authenticity: AUTHENTICITY } },
    { variant_id: "balanced_diwani", font: "Amiri-Regular", spelling_verified: true, legibility: 0.87, feasibility_hint: 0.6, text_mm: [12.2, 8.1], validation_passed: false,
      meta: { label_en: "Balanced Diwani (inspired)", label_ar: "ديواني متوازن (مستوحى)", expert_review_recommended: false, notes: "elegant and easier to read", authenticity: AUTHENTICITY } },
    { variant_id: "manufacturing_optimized", font: "Amiri-Bold", spelling_verified: true, legibility: 1, feasibility_hint: 1, text_mm: [12.6, 6.6], validation_passed: true,
      meta: { label_en: "Manufacturing-Optimized", label_ar: "محسّن للتصنيع", expert_review_recommended: false, notes: "bolder strokes, safer spacing", authenticity: AUTHENTICITY } },
  ],
  validations: { manufacturing_optimized: { passed: true, checks: MFG_CHECKS } },
  export_manifest: {
    approval_id: "BS-DS-1-MANU",
    files: { svg: "demo", png_flat: "demo", png_enamel_macro: "demo", png_pair: "demo" },
  },
};

/** Same rules the server serves from /api/design/pricing (AED, starting prices). */
const PRICING_RULES = {
  currency: "AED",
  price_floor_aed: 265,
  policy_note_en: "Starting price. Final price is confirmed with the customer on WhatsApp.",
  policy_note_ar: "سعر ابتدائي. يُؤكد السعر النهائي مع العميل عبر واتساب.",
  base_by_item: { cufflink: 295, pendant: 265, bracelet: 285, ring: 275, brooch: 295, coin: 320, corporate_gift: 350 },
  material_multiplier: {
    silver_925: { label_en: "925 Silver", label_ar: "فضة ٩٢٥", factor: 1.0 },
    gold_plated: { label_en: "Gold plated", label_ar: "مطلي ذهب", factor: 1.18 },
    rose_gold_plated: { label_en: "Rose gold plated", label_ar: "مطلي ذهب وردي", factor: 1.18 },
    oxidized_silver: { label_en: "Oxidized silver", label_ar: "فضة مؤكسدة", factor: 1.08 },
    solid_gold_18k: { label_en: "18k Gold", label_ar: "ذهب ١٨ قيراط", factor: null, quote_on_request: true },
  },
  finish_adder: {
    mirror_polish: { label_en: "Mirror polish", label_ar: "تلميع مرآة", aed: 0 },
    brushed: { label_en: "Brushed", label_ar: "مصقول ناعم", aed: 15 },
    black_enamel: { label_en: "Black enamel", label_ar: "مينا سوداء", aed: 45 },
    white_enamel: { label_en: "White enamel", label_ar: "مينا بيضاء", aed: 45 },
  },
  variant_factor: { luxury_diwani_jali: 1.25, balanced_diwani: 1.1, manufacturing_optimized: 1.0 },
  per_letter_after: { letters_included: 4, aed_per_letter: 12 },
  quantity_tiers: [
    { min_qty: 10, factor: 0.85 }, { min_qty: 5, factor: 0.9 },
    { min_qty: 2, factor: 0.95 }, { min_qty: 1, factor: 1.0 },
  ],
};

const DATA: Record<string, unknown> = {
  "/api/health": { ok: true, agents: ["custodian", "analyst", "designer", "producer", "publisher", "calligrapher"], skills: 51 },
  "/api/policies": {
    thresholds: { originality_max_similarity: 0.86, corpus_min_references: 40, corpus_min_sources: 12, provenance_min_sources: 3, price_floor_aed: 265 },
    policies: [
      { id: "P1", name: "NO_IMAGE_TO_GENERATOR", tags: ["imagegen"], description: "Generation adapters accept text prompts only." },
      { id: "P2", name: "LICENCE_REQUIRED", tags: ["licence_required"], description: "No third-party asset without an active licence." },
      { id: "P3", name: "PROVENANCE_MINIMUM", tags: ["brief_promote"], description: "Three independent sources per brief attribute." },
      { id: "P4", name: "CORPUS_FLOOR", tags: ["synthesis"], description: "40 references / 12 sources before synthesis." },
      { id: "P5", name: "NO_AI_PUBLICATION", tags: ["catalogue_export"], description: "Only workshop photographs publish." },
      { id: "P6", name: "NO_UNVERIFIED_MATERIAL_CLAIMS", tags: ["material_write"], description: "Materials need a verified source." },
      { id: "P7", name: "NO_SCRAPING", tags: ["outbound_http"], description: "Graph API with OAuth only." },
      { id: "P8", name: "CONTEXT_SEPARATION", tags: ["*"], description: "Commercial and public-sector data never mix." },
    ],
    grants: {},
  },
  "/api/assets": { assets: ASSETS },
  "/api/inbox": { pending: [], count: 0 },
  "/api/licences": { licences: [
    { id: "OWN", licensor: "Beyond Style UAE", scope: "ingest,derive,export", valid_to: "2099-01-01T00:00:00", days_left: 26000, expiring_soon: false, expired: false },
    { id: "LIC-2026-004", licensor: "Supplier Atelier A", scope: "ingest,derive", valid_to: "2027-03-01T00:00:00", days_left: 215, expiring_soon: false, expired: false },
    { id: "LIC-2026-007", licensor: "Market Account B", scope: "ingest", valid_to: "2026-08-20T00:00:00", days_left: 23, expiring_soon: true, expired: false },
  ] },
  "/api/corpus/health": { references: 57, required_references: 40, sources: 14, required_sources: 12, floor_met: true, shortfall: { references: 0, sources: 0 }, by_source: { supplier_atelier_a: 9, market_account_b: 7, beyond_style_workshop: 6 } },
  "/api/corpus/refs": { rows: Array.from({ length: 12 }, (_, i) => ({ id: i + 1, source_id: `demo${(i % 6) + 1}`.padStart(8, "0"), source_handle: ["supplier_atelier_a", "market_account_b", "supplier_atelier_c"][i % 3], attributes: REF_ATTRS[i % REF_ATTRS.length] })) },
  "/api/trends/frequency": { total_references: 57, ranking: {
    "motif.primary": [["arabic name", 14], ["initial letter", 9], ["falcon", 5], ["palm frond", 4]],
    "form.silhouette": [["pendant drop", 12], ["bar", 8], ["cuff", 6], ["charm cluster", 4]],
    "material_finish.finish": [["high polish", 18], ["brushed", 11], ["matte", 7]],
    "commercial.occasion": [["eid", 10], ["wedding", 9], ["birthday", 8], ["graduation", 6]],
  } },
  "/api/trends/cooccurrence": { total_references: 57, pairs: [
    { a: "motif.primary=arabic name", b: "material_finish.finish=high polish", count: 11 },
    { a: "form.silhouette=pendant drop", b: "commercial.occasion=eid", count: 8 },
    { a: "motif.primary=initial letter", b: "commercial.target_segment=young women", count: 7 },
    { a: "form.silhouette=cuff", b: "material_finish.finish=matte", count: 3 },
  ] },
  "/api/trends/whitespace": { total_references: 57, whitespace: [
    { a: "motif.primary=falcon", b: "form.silhouette=bar", combo_count: 0, a_count: 5, b_count: 8, opportunity_score: 40, a_sources: [], b_sources: [] },
    { a: "motif.primary=palm frond", b: "material_finish.finish=brushed", combo_count: 1, a_count: 4, b_count: 11, opportunity_score: 22, a_sources: [], b_sources: [] },
    { a: "form.silhouette=charm cluster", b: "commercial.occasion=graduation", combo_count: 0, a_count: 4, b_count: 6, opportunity_score: 24, a_sources: [], b_sources: [] },
  ] },
  "/api/trends/segments": { segments: { mothers: { total: 21 }, "young women": { total: 18 }, men: { total: 10 }, kids: { total: 8 } } },
  "/api/briefs": { briefs: [
    { id: 1, title: "falcon bar pendant", status: "approved", attributes: { "motif.primary": { value: "falcon", source_ids: ["a1", "b2", "c3", "d4"] }, "form.silhouette": { value: "bar", source_ids: ["a1", "c3", "e5"] } }, dropped_attributes: {} },
    { id: 2, title: "palm frond cuff", status: "review", attributes: { "motif.primary": { value: "palm frond", source_ids: ["a1", "b2", "c3"] } }, dropped_attributes: { "typography.script": { reason: "insufficient_provenance" } } },
  ] },
  "/api/concepts": { concepts: [
    { id: 1, brief_id: 1, model_id: "gemini-3.1-flash-lite-image", status: "approved", gate_result: { passed: true, advisory: true, max_similarity: 0.41, threshold: 0.86, nearest: [{ key: "corpus:demo0001", similarity: 0.41 }, { key: "corpus:demo0004", similarity: 0.37 }, { key: "corpus:demo0002", similarity: 0.33 }] } },
    { id: 2, brief_id: 1, model_id: "gemini-3.1-flash-lite-image", status: "gate_rejected", gate_result: { passed: false, max_similarity: 0.91, threshold: 0.86, nearest: [{ key: "corpus:demo0004", similarity: 0.91 }, { key: "corpus:demo0001", similarity: 0.62 }, { key: "corpus:demo0005", similarity: 0.5 }] } },
    { id: 3, brief_id: 2, model_id: "gemini-3-pro-image", status: "gate_passed", gate_result: { passed: true, advisory: true, max_similarity: 0.52, threshold: 0.86, nearest: [{ key: "corpus:demo0003", similarity: 0.52 }] } },
  ] },
  "/api/specs": { specs: [
    { id: 1, concept_id: 1, components: [{ part: "bar body" }, { part: "falcon inlay" }, { part: "chain" }], complexity_band: "B", starting_price_aed: 345, open_questions: ["clasp type?", "confirm chain gauge for 8g pendant"], state: "workshop_spec", materials: { metal: "pending_workshop_verification", purity: "pending_workshop_verification" }, personalisation_zones: [] },
  ] },
  "/api/escalations": { escalations: [
    { id: 1, policy_id: "E_LICENCE_EXPIRING", message: "licence 'LIC-2026-007' expires 2026-08-20 (within 30 days); 7 asset(s) affected", status: "open", created_at: now() },
  ] },
  "/api/ledger": { verified: true, entries: Array.from({ length: 40 }, (_, i) => ({ seq: i + 1, event_type: i % 4 === 0 ? "policy_evaluation" : "tool_call", actor: ["custodian", "analyst", "designer"][i % 3], outcome: "ok" })) },
  "/api/agents/profiles": { agents: [
    { name: "custodian", role: "Licensed asset custody", display_name: "Zaid", tagline: "asset custody & licences", avatar_path: "", grant: { allow: [], deny: [] } },
    { name: "analyst", role: "Trend synthesis", display_name: "Layla", tagline: "corpus & whitespace", avatar_path: "", grant: { allow: [], deny: [] } },
    { name: "designer", role: "Concept origination", display_name: "Amir", tagline: "original concepts, text-only", avatar_path: "", grant: { allow: [], deny: [] } },
    { name: "producer", role: "Workshop specification", display_name: "Hana", tagline: "specs & pricing bands", avatar_path: "", grant: { allow: [], deny: [] } },
    { name: "publisher", role: "Export guard", display_name: "Noor", tagline: "manifested exports only", avatar_path: "", grant: { allow: [], deny: [] } },
    { name: "calligrapher", role: "Deterministic typography & workshop files", display_name: "Rashid", tagline: "provable spelling, verified vectors", avatar_path: "", grant: { allow: [], deny: [] } },
  ] },
  "/api/runs": { runs: [{ id: 1, state: "workshop_spec", history: [] }] },
  "/api/progress": { milestones: [{ id: 1, title: "First catalogue export", status: "in_progress", notes: "" }] },
  "/api/sessions-log": { sessions: [] },
  "/api/brain/notes": { notes: [{ id: 1, title: "Clasp rule", tags: "workshop", created_at: now() }] },
  "/api/design/projects": { projects: [DESIGN_PROJECT] },
  "/api/design/projects/1": DESIGN_PROJECT,
  "/api/design/pricing": { rules: PRICING_RULES },
};

export function demoResponse(path: string): unknown | undefined {
  const clean = path.split("?")[0].replace(/\/$/, "");
  return DATA[clean];
}

export function demoImageUrl(path: string): string | null {
  let m = path.match(/^\/api\/assets\/demo000(\d)\/file/);
  if (m) return `/demo/asset${m[1]}.png`;
  m = path.match(/^\/api\/concepts\/(\d)\/image/);
  if (m) return `/demo/concept${m[1]}.png`;
  m = path.match(/^\/api\/design\/projects\/\d+\/variants\/(\w+)\.svg/);
  if (m) return `/demo/design_${m[1]}.svg`;
  m = path.match(/^\/api\/design\/projects\/\d+\/files\/(\w+)/);
  if (m) {
    const files: Record<string, string> = {
      svg: "/demo/design_manufacturing_optimized.svg",
      png_flat: "/demo/design_flat.png",
      png_enamel_macro: "/demo/design_macro.png",
      png_pair: "/demo/design_pair.png",
    };
    return files[m[1]] ?? null;
  }
  if (path.startsWith("/api/agents/") && path.includes("/avatar")) return null;
  return null;
}

/** Client-side mirror of the transliteration dictionary for the static demo. */
const DEMO_NAMES: Record<string, string> = {
  zahran: "زهران", mohammed: "محمد", muhammad: "محمد", ahmed: "أحمد", ahmad: "أحمد",
  ali: "علي", omar: "عمر", khalid: "خالد", khaled: "خالد", hamdan: "حمدان",
  rashid: "راشد", zayed: "زايد", salem: "سالم", saif: "سيف", sultan: "سلطان",
  fatima: "فاطمة", maryam: "مريم", mariam: "مريم", aisha: "عائشة", sara: "سارة",
  sarah: "سارة", noura: "نورة", noor: "نور", layla: "ليلى", reem: "ريم",
  shaghaf: "شغف", farah: "فرح", rose: "روز", hessa: "حصة", moza: "موزة",
};

export function demoTransliterate(text: string) {
  const words = text.trim().split(/[\s,،]+/).filter(Boolean);
  const perWord = words.map((w) => {
    const hit = DEMO_NAMES[w.replace(/[^A-Za-z]/g, "").toLowerCase()];
    return {
      latin: w,
      suggestions: hit
        ? [{ arabic: hit, source: "dictionary", requires_confirmation: false, typography_verifiable: true }]
        : [{ arabic: "", source: "rules", requires_confirmation: true, typography_verifiable: false }],
    };
  });
  const ok = perWord.every((w) => w.suggestions[0].arabic);
  return {
    input: text,
    words: perWord,
    combined: ok
      ? [{ arabic: perWord.map((w) => w.suggestions[0].arabic).join(" "),
           source: "dictionary", requires_confirmation: false, typography_verifiable: true }]
      : [],
  };
}

export const DEMO_BLOCKED_MESSAGE =
  "Demo preview: actions are disabled here. Run BSOS locally (make dev) for the real, kernel-enforced system.";

/** Synthetic feed for the demo's live streams. */
export function startDemoFeed(push: (e: FeedEvent) => void): () => void {
  const samples: Array<Partial<FeedEvent>> = [
    { agent: "custodian", tool: "library.ingest", outcome: "ok" },
    { agent: "analyst", tool: "corpus.whitespace", outcome: "ok" },
    { agent: "designer", tool: "generate.image", outcome: "ok" },
    { agent: "designer", tool: "originality.gate", outcome: "deny", policy_id: "GATE", message: "similarity 0.91 ≥ 0.86 — rejected, nearest 3 attached" },
    { agent: "publisher", tool: "export.flat", outcome: "deny", policy_id: "P5", message: "AI render blocked from customer-facing export" },
    { agent: "custodian", tool: "library.ingest", outcome: "escalate", policy_id: "E_LICENCE_EXPIRING", message: "licence LIC-2026-007 expires within 30 days" },
  ];
  let seq = 1000;
  const timer = setInterval(() => {
    const s = samples[seq % samples.length];
    push({ seq: seq++, ts: now(), agent: s.agent!, tool: s.tool!, outcome: s.outcome!, policy_id: s.policy_id, message: s.message });
  }, 2600);
  return () => clearInterval(timer);
}
