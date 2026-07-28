/** Typed API client. Policy outcomes surface as structured errors. */

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
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
