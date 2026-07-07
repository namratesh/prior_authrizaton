// Client-side mirror of backend/app/core/supervisor.py's is_expedite — the
// case list / queue responses carry the raw sla_deadline, not a precomputed
// boolean, so the "within 2h" check is re-evaluated here on every render.
const EXPEDITE_WINDOW_MS = 2 * 60 * 60 * 1000;

export function is_expedite_client(slaDeadline: string | null | undefined): boolean {
  if (!slaDeadline) return false;
  const deadline = new Date(slaDeadline).getTime();
  return deadline - Date.now() <= EXPEDITE_WINDOW_MS;
}
