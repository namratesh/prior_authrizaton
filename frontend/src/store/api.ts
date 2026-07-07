// DEMO-REAL: thin fetch wrappers over the 5 FastAPI endpoints in CLAUDE.md's API table.
// In production (docker-compose), nginx proxies /api/ to the backend container,
// so requests stay same-origin and no build-time API URL needs to be baked in.
// In dev (`npm run dev`), there's no proxy, so fall back to the local backend port.
export const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://localhost:8000" : "");

export interface StatusResponse {
  case_id: string;
  case_number: string;
  current_phase: string;
  final_status: string | null;
  needs_human_review: boolean;
  case_status: string | null;
  interrupt_reason: string | null;
  requested_service_description: string | null;
  patient_query: string | null;
  estimated_out_of_pocket: number | null;
  sla_deadline: string | null;
  is_expedite: boolean;
}

export interface ReviewResponse {
  case_id: string;
  case_number: string;
  patient_name: string | null;
  current_phase: string;
  final_status: string | null;
  needs_human_review: boolean;
  clinical: Record<string, any>;
  financial: Record<string, any>;
  policy: Record<string, any>;
  routing: Record<string, any>;
  decision_letter: string | null;
  agent_trace: Record<string, any>[];
}

export interface FairnessCohort {
  cohort: string;
  total: number;
  approval_rate: number;
}

export interface Segment {
  key: string;
  total: number;
  override_rate: number | null;
  leakage: number;
}

export interface AdminMetrics {
  leakage_prevented: number;
  accuracy_drift: { date: string; accuracy: number | null }[];
  fairness_cohorts: FairnessCohort[];
  fairness_finalized_total: number;
  segments: Segment[] | null;
  cases: {
    case_id: string;
    case_number: string;
    current_phase: string;
    final_status: string | null;
    needs_human_review: boolean;
    assigned_to: string | null;
    sla_deadline: string | null;
    requested_service_description: string | null;
    flags: string[];
    rationale: string | null;
  }[];
}

export interface AdminSettings {
  sla_hours: number;
  expedite_hours: number;
  confidence_threshold: number;
  agents_enabled: { cost: boolean; rag: boolean; alternative: boolean };
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

export async function uploadCase(file: File, query: string): Promise<{ case_id: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("query", query);
  const res = await fetch(`${API_URL}/api/v1/upload`, { method: "POST", body: form });
  return json(res);
}

export async function getStatus(caseId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_URL}/api/v1/status/${caseId}`);
  return json(res);
}

export async function getReview(caseId: string): Promise<ReviewResponse> {
  const res = await fetch(`${API_URL}/api/v1/review/${caseId}`);
  return json(res);
}

export interface AdjudicatePayload {
  action: "approve" | "modify" | "deny" | "clarify" | "provider_responded";
  reviewer_id?: string;
  diffs?: { clinical?: Record<string, any>; financial?: Record<string, any> };
  question?: string;
  original_reason?: string;
  reason?: string;
}

export async function adjudicate(caseId: string, payload: AdjudicatePayload) {
  const res = await fetch(`${API_URL}/api/v1/review/${caseId}/adjudicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return json<{ case_id: string; final_status: string | null; case_status: string | null; decision_letter: string | null }>(res);
}

export async function getAdminMetrics(groupBy?: "provider" | "service" | "reviewer"): Promise<AdminMetrics> {
  const qs = groupBy ? `?group_by=${groupBy}` : "";
  const res = await fetch(`${API_URL}/api/v1/admin/metrics${qs}`);
  return json(res);
}

export async function getAdminSettings(): Promise<AdminSettings> {
  const res = await fetch(`${API_URL}/api/v1/admin/settings`);
  return json(res);
}

export async function updateAdminSettings(payload: Partial<AdminSettings>): Promise<AdminSettings> {
  const res = await fetch(`${API_URL}/api/v1/admin/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return json(res);
}

export async function assignCase(caseId: string, reviewerId: string): Promise<{ case_id: string; assigned_to: string }> {
  const res = await fetch(`${API_URL}/api/v1/review/${caseId}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_id: reviewerId }),
  });
  return json(res);
}

export async function unassignCase(caseId: string): Promise<{ case_id: string; assigned_to: null }> {
  const res = await fetch(`${API_URL}/api/v1/review/${caseId}/unassign`, { method: "POST" });
  return json(res);
}

export function exportCaseAuditUrl(caseId: string): string {
  return `${API_URL}/api/v1/review/${caseId}/audit-export`;
}

export function exportAllAuditUrl(): string {
  return `${API_URL}/api/v1/admin/audit-export`;
}
