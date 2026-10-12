// Shapes returned by the LedgerPilot API. Money is always integer cents; negative = money out.

export type Owner = "self" | "spouse" | "joint" | "business";
export type BusinessStatus = "business" | "review" | "personal";
export type PaceStatus = "on_track" | "running_hot" | "over";

export interface SyncRun {
  id: number | null;
  source: string;
  trigger: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "ok" | "error";
  new_count: number;
  new_ids: number[];
  error: string | null;
}

export interface Summary {
  today: string;
  net_worth_cents: number;
  net_worth_breakdown: {
    cash_cents: number;
    credit_cents: number;
    business_cents: number;
    investments_cents: number;
    retirement_cents: number;
  };
  safe_to_spend_today_cents: number;
  budget: {
    month: string;
    target_cents: number;
    spent_cents: number;
    expected_by_today_cents: number;
    upcoming_bills_cents: number;
    days_remaining: number;
    days_in_month: number;
    status: PaceStatus;
  };
  business: {
    ytd_deductions_cents: number;
    ytd_income_cents: number;
    review_count: number;
    owed_to_you_cents: number;
  };
  last_sync: SyncRun | null;
}

export interface Account {
  id: number;
  name: string;
  institution: string;
  type: "checking" | "savings" | "credit_card" | "brokerage" | "ira_traditional" | "ira_roth" | "401k";
  owner: Owner;
  balance_cents: number;
  source: string;
  updated_at: string;
}

export interface Category {
  id: string;
  name: string;
  group: "income" | "essential" | "discretionary" | "transfer" | "taxes" | "business" | "other";
  irs_line: string | null;
  irs_detail: string | null;
  deductible_pct: number;
  personal_fallback_id: string | null;
}

export interface Txn {
  id: number;
  account_id: number;
  account_name: string;
  owner: Owner;
  date: string;
  description: string;
  merchant: string;
  amount_cents: number;
  category_id: string;
  category_name: string;
  category_group: Category["group"];
  categorized_by: "source" | "rule" | "ai" | "user" | "fallback";
  ai_rationale: string | null;
  business_status: BusinessStatus;
  business_pct: number;
  irs_line: string | null;
  deductible_cents: number;
  reimbursable_cents: number;
  reimbursement_status: "owed" | "reimbursed" | "applied" | null;
  user_locked: boolean;
  notes: string | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface CategoryLine {
  category_id: string;
  name: string;
  group: string;
  target_cents: number;
  spent_cents: number;
  expected_by_today_cents: number;
  status: PaceStatus;
}

export interface Budget {
  month: string;
  today: string;
  days_in_month: number;
  days_remaining: number;
  target_cents: number;
  spent_cents: number;
  expected_by_today_cents: number;
  upcoming_bills_cents: number;
  safe_to_spend_today_cents: number;
  status: PaceStatus;
  categories: CategoryLine[];
  upcoming_bills: { merchant: string; category_id: string; expected_day: number; amount_cents: number }[];
  daily: { day: number; spent_cents: number | null; pace_cents: number }[];
}

export interface BusinessSummary {
  year: number;
  income_cents: number;
  total_deductions_cents: number;
  lines: { line: string; label: string; amount_cents: number; details: { name: string; amount_cents: number }[] }[];
  review_count: number;
  owed_cents: number;
  reimbursed_cents: number;
}

export interface Reimbursements {
  owed: Txn[];
  reimbursed: Txn[];
  owed_total_cents: number;
  reimbursed_total_cents: number;
}

export interface Settings {
  ai_enabled: boolean;
  ai_available: boolean;
  sync_interval_minutes: number;
  self_name: string;
  spouse_name: string;
  business_name: string;
  filing_status: "single" | "mfj" | "mfs" | "hoh";
  phone_internet_business_pct: number;
}
