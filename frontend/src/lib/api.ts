import type {
  Account,
  Budget,
  BusinessSummary,
  Category,
  Page,
  Reimbursements,
  Settings,
  Summary,
  SyncRun,
  Txn,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : "";
}

export interface TxnFilters {
  account_id?: number;
  owner?: string;
  category_id?: string;
  business_status?: string;
  month?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface TxnPatch {
  category_id?: string;
  business_status?: "business" | "review" | "personal";
  business_pct?: number;
  notes?: string;
  create_rule?: boolean;
}

export const api = {
  summary: () => request<Summary>("/summary"),
  accounts: () => request<Account[]>("/accounts"),
  categories: () => request<Category[]>("/categories"),
  transactions: (f: TxnFilters = {}) => request<Page<Txn>>(`/transactions${qs({ ...f })}`),
  updateTransaction: (id: number, patch: TxnPatch) =>
    request<Txn>(`/transactions/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  budget: (month?: string) => request<Budget>(`/budget${qs({ month })}`),
  setBudget: (categoryId: string, monthly_cents: number) =>
    request(`/budget/${categoryId}`, { method: "PUT", body: JSON.stringify({ monthly_cents }) }),
  businessSummary: (year?: number) => request<BusinessSummary>(`/business/summary${qs({ year })}`),
  businessReview: () => request<Txn[]>("/business/review"),
  reimbursements: () => request<Reimbursements>("/business/reimbursements"),
  exportUrl: (year?: number) => `/api/business/export.csv${qs({ year })}`,
  sync: () => request<SyncRun>("/sync", { method: "POST" }),
  settings: () => request<Settings>("/settings"),
  updateSettings: (values: Partial<Settings>) =>
    request<Settings>("/settings", { method: "PUT", body: JSON.stringify(values) }),
  importCsv: (accountId: number, file: File) => {
    const form = new FormData();
    form.append("account_id", String(accountId));
    form.append("file", file);
    return request<{ imported: number; skipped: number }>("/import/csv", { method: "POST", body: form });
  },
  resetDemo: () => request<SyncRun>("/demo/reset", { method: "POST" }),
};
