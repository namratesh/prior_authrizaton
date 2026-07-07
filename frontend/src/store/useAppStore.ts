import { create } from "zustand";

// DEMO-MOCKED: no real auth. Two hardcoded roles, and a single synthetic
// "logged in" patient record used to auto-populate the Submission view.
export const DEMO_PATIENT = {
  memberId: "AARP-90210-0001",
  name: "Jane Doe",
  dob: "1950-01-01",
  zip: "90210",
};

export const DEMO_REVIEWER_ID = "reviewer-1";

const CASE_HISTORY_KEY = "agenticpa_patient_case_history";

function loadCaseHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(CASE_HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

interface AppState {
  role: "patient" | "reviewer" | "admin";
  setRole: (role: AppState["role"]) => void;
  caseHistory: string[];
  addCaseToHistory: (caseId: string) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  role: "patient",
  setRole: (role) => set({ role }),
  caseHistory: loadCaseHistory(),
  addCaseToHistory: (caseId) => {
    const next = [caseId, ...get().caseHistory.filter((id) => id !== caseId)];
    localStorage.setItem(CASE_HISTORY_KEY, JSON.stringify(next));
    set({ caseHistory: next });
  },
}));
