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

const DATA: Record<string, unknown> = {
  "/api/health": { ok: true, agents: ["custodian", "analyst", "designer", "producer", "publisher"], skills: 44 },
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
  ] },
  "/api/runs": { runs: [{ id: 1, state: "workshop_spec", history: [] }] },
  "/api/progress": { milestones: [{ id: 1, title: "First catalogue export", status: "in_progress", notes: "" }] },
  "/api/sessions-log": { sessions: [] },
  "/api/brain/notes": { notes: [{ id: 1, title: "Clasp rule", tags: "workshop", created_at: now() }] },
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
  if (path.startsWith("/api/agents/") && path.includes("/avatar")) return null;
  return null;
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
