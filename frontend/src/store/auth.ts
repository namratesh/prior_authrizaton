// DEMO-MOCKED: hardcoded per-role credentials, no real auth backend/session.
// Override defaults via VITE_<ROLE>_USERNAME / VITE_<ROLE>_PASSWORD — see .env.example.
export type Role = "patient" | "reviewer" | "admin";

interface RoleCredential {
  username: string;
  password: string;
  label: string;
}

export const ROLE_CREDENTIALS: Record<Role, RoleCredential> = {
  patient: {
    username: import.meta.env.VITE_PATIENT_USERNAME || "patient_demo",
    password: import.meta.env.VITE_PATIENT_PASSWORD || "patient123",
    label: "Patient",
  },
  reviewer: {
    username: import.meta.env.VITE_REVIEWER_USERNAME || "reviewer_demo",
    password: import.meta.env.VITE_REVIEWER_PASSWORD || "reviewer123",
    label: "Reviewer",
  },
  admin: {
    username: import.meta.env.VITE_ADMIN_USERNAME || "admin_demo",
    password: import.meta.env.VITE_ADMIN_PASSWORD || "admin123",
    label: "Admin",
  },
};

const STORAGE_KEY = "agentic_pa_auth";

export interface AuthSession {
  role: Role;
  loggedInAt: number;
}

export function login(role: Role, username: string, password: string): boolean {
  const credential = ROLE_CREDENTIALS[role];
  if (username === credential.username && password === credential.password) {
    const session: AuthSession = { role, loggedInAt: Date.now() };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    return true;
  }
  return false;
}

export function logout(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function getAuth(): AuthSession | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.role === "string") return parsed as AuthSession;
  } catch {
    return null;
  }
  return null;
}
