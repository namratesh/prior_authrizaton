// Client-side mirror of backend/app/core/supervisor.py's is_expedite — the
// case list / queue responses carry the raw sla_deadline, not a precomputed
// boolean, so the "within N hours" check is re-evaluated here on every render.
//
// expedite_hours is admin-tunable server-side (settings_store.py); syncSlaSettings
// refreshes the local mirror from GET /admin/settings so this stays in step with
// the Admin Portal instead of drifting from a value frozen at build time.
import { getAdminSettings } from "./api";

let expediteWindowMs = 2 * 60 * 60 * 1000;

export function syncSlaSettings(): void {
  getAdminSettings()
    .then((s) => {
      expediteWindowMs = s.expedite_hours * 60 * 60 * 1000;
    })
    .catch(() => {
      // keep the last-known/default value if the settings fetch fails
    });
}

export function is_expedite_client(slaDeadline: string | null | undefined): boolean {
  if (!slaDeadline) return false;
  const deadline = new Date(slaDeadline).getTime();
  return deadline - Date.now() <= expediteWindowMs;
}
