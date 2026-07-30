/** Typed API client. Policy outcomes surface as structured errors. */

import { DEMO, DEMO_BLOCKED_MESSAGE, demoImageUrl, demoResponse } from "./demo";

export interface PolicyDecision {
  policy_id: string;
  action: string;
  message: string;
  detail: Record<string, unknown>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public kind: string,
    public decisions: PolicyDecision[] = [],
    message?: string,
  ) {
    super(message ?? decisions.map((d) => `[${d.policy_id}] ${d.message}`).join("; "));
  }
}

export function getToken(): string {
  return localStorage.getItem("bsos-token") ?? "";
}

export function setToken(token: string): void {
  localStorage.setItem("bsos-token", token);
}

/** For <img> tags and EventSource, which cannot carry headers. */
export function authedUrl(path: string): string {
  if (DEMO) {
    const mapped = demoImageUrl(path);
    if (mapped) return mapped;
    return path;
  }
  const token = getToken();
  if (!token) return path;
  return path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(token);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (DEMO) {
    if (init?.method && init.method !== "GET") {
      throw new ApiError(400, "demo", [], DEMO_BLOCKED_MESSAGE);
    }
    const canned = demoResponse(path);
    if (canned !== undefined) return canned as T;
    throw new ApiError(404, "demo", [], "not part of the demo dataset");
  }
  const token = getToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail: any = undefined;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* non-JSON error body */
    }
    if (detail && typeof detail === "object" && detail.kind) {
      throw new ApiError(res.status, detail.kind, detail.decisions ?? [], undefined);
    }
    throw new ApiError(res.status, "error", [], String(detail ?? res.statusText));
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
};

export interface Asset {
  id: string;
  filename: string;
  origin: string;
  source_handle: string;
  licence_id: string | null;
  flags: string[];
  review_state: string;
  category: string;
  width: number;
  height: number;
}

export interface Licence {
  id: string;
  licensor: string;
  scope: string;
  valid_to: string;
  days_left: number;
  expiring_soon: boolean;
  expired: boolean;
}

export interface CorpusHealth {
  references: number;
  required_references: number;
  sources: number;
  required_sources: number;
  floor_met: boolean;
  shortfall: { references: number; sources: number };
  by_source: Record<string, number>;
}

export interface WhitespaceEntry {
  a: string;
  b: string;
  combo_count: number;
  a_count: number;
  b_count: number;
  opportunity_score: number;
}

export interface Brief {
  id: number;
  title: string;
  attributes: Record<string, { value: string; source_ids: string[] }>;
  dropped_attributes: Record<string, unknown>;
  status: string;
}

export interface Concept {
  id: number;
  brief_id: number;
  model_id: string;
  status: string;
  gate_result: {
    passed?: boolean;
    advisory?: boolean;
    advisory_note?: string;
    max_similarity?: number;
    threshold?: number;
    nearest?: { key: string; similarity: number }[];
  };
}

export interface Spec {
  id: number;
  concept_id: number;
  components: { part: string }[];
  complexity_band: string;
  starting_price_aed: number;
  open_questions: string[];
  state: string;
  materials: Record<string, string>;
}

export interface Escalation {
  id: number;
  policy_id: string;
  message: string;
  status: string;
  created_at: string;
}

export interface AgentInfo {
  name: string;
  role: string;
  display_name: string;
  tagline: string;
  avatar_path: string;
  grant: { allow: string[]; deny: string[] };
}

export interface DesignVariant {
  variant_id: string;
  font: string;
  spelling_verified: boolean;
  legibility: number;
  feasibility_hint: number;
  text_mm: [number, number];
  validation_passed: boolean;
  meta: {
    label_en: string;
    label_ar: string;
    expert_review_recommended: boolean;
    estimated_stroke_mm?: number;
    notes: string;
    authenticity: string;
  };
}

export interface DesignProjectSummary {
  id: number;
  inscription: string;
  item_type: string;
  status: string;
  selected_variant: string;
  created_at: string;
}

export interface DesignProjectDetail extends DesignProjectSummary {
  normalized_inscription: string;
  frame: Record<string, number>;
  letter_sequence: { char: string; codepoint: string; name: string }[];
  verification: { passed: boolean; status: string; issues: string[] };
  variants: DesignVariant[];
  validations: Record<string, { passed: boolean; checks: { check: string; ok: boolean; detail: string }[] }>;
  approver: string;
  export_manifest: { approval_id?: string; files?: Record<string, string> };
}

export interface FeedEvent {
  seq: number;
  ts: string;
  agent: string;
  tool: string;
  outcome: string;
  policy_id?: string;
  message?: string;
  topic?: string;
}
