# LedgerPilot — Phase 1: Foundation, Live Budget & S-Corp Deductions

**Date:** 2026-10-11
**Status:** Approved
**Target release:** v0.1.0

## 1. Context

LedgerPilot is a local-first personal + small-business finance app. It runs on the user's
machine (browser on localhost now, packaged desktop app later), pulls transactions from
banks/cards/brokerages, keeps a live daily budget, flags S-Corp business deductions, and —
in later phases — supports tax-loss harvesting and IRA/401(k) planning.

**Household profile the app is built around:**

- Married filing jointly.
- One spouse has a W-2 job with an employer 401(k) (still contributing), RSUs and ESPP.
- The same person owns an **S-Corp** (files Form 1120-S). Business expenses are paid through
  **mixed** accounts: mostly business checking/card, sometimes personal cards.
- Investment accounts: taxable brokerage, IRAs/401(k)s, employer stock.
- Retirement accounts to plan for: Traditional/Roth IRA, Solo 401(k) via the S-Corp, old employer 401(k)s.
- Budget style: monthly category targets with a daily pace.

LedgerPilot computes and surfaces information. It is **not** tax, legal or investment advice;
the UI states this and recommends confirming decisions with a CPA/CFP.

## 2. Phasing

| Phase | Scope | Release |
|---|---|---|
| **1 (this spec)** | App skeleton, source connector layer + mock source, CSV import, local DB, categorization (rules + opt-in Claude), monthly budget with daily pace and safe-to-spend, live updates, S-Corp deduction flagging, accountable-plan reimbursement queue | v0.1.0 |
| 2 | Investments & tax-loss harvesting (lots, RSU/ESPP basis, wash-sale checks across taxable + IRA/401(k)) | v0.2.0 |
| 3 | Retirement planning (document upload/parse, shared 402(g) limit across W-2 401(k) + Solo 401(k), backdoor Roth checks, rollovers, projections) | v0.3.0 |
| 4 | Real connector (Plaid), packaged desktop app | v0.4.0 |

Phase 1 mock data already includes brokerage and retirement accounts (balances only) so
phases 2–3 build on it.

## 3. Architecture

```
React dashboard (Vite dev server, localhost:5173, proxies /api → backend)
        │  REST (JSON) + Server-Sent Events (/api/events)
FastAPI backend (binds 127.0.0.1:8000 only)
  ├─ sources/        Source protocol; MockSource (phase 1); CSV import
  ├─ sync engine     scheduler → fetch → upsert/dedupe → categorize → reimbursement match → publish event
  ├─ categorize/     user/system rules first, Claude second (opt-in), user corrections become rules
  ├─ budget          pure functions: pace, upcoming bills, safe-to-spend
  ├─ business        deduction status, 1120-S line mapping, reimbursement queue, YTD summary, CSV export
  └─ SQLite (SQLAlchemy 2 + Alembic migrations) in data/ (gitignored)
```

**Real-time model (Approach A):** an asyncio background task in the FastAPI lifespan runs a
sync every `sync_interval_minutes` (default 15, configurable down to 1 for demos). "Sync now"
triggers the same sync on demand. After each sync the backend publishes an SSE event; the
dashboard invalidates its queries and re-renders without a page reload. Bank webhooks are not
used because they cannot reach localhost without a tunnel.

**Tech stack**

- Backend: Python ≥ 3.12 (developed on 3.14), FastAPI, Uvicorn, SQLAlchemy 2, Alembic,
  Pydantic v2, `anthropic` SDK (optional feature), pytest, ruff.
- Frontend: React 19 + TypeScript, Vite, TanStack Query, React Router, Tailwind CSS v4,
  Recharts, lucide-react icons, Vitest.
- Root `package.json` with `concurrently`: `npm run setup` (create venv, install both sides),
  `npm run dev` (backend + frontend), `npm test`.

**Money:** stored as integer cents. Sign convention: negative = money out of the account,
positive = money in. Connectors normalize to this convention.

## 4. Data model

- **Account**: id, source (`mock`/`csv`), external_id, name, institution, type
  (`checking`, `savings`, `credit_card`, `brokerage`, `ira_traditional`, `ira_roth`, `401k`),
  owner (`self`, `spouse`, `joint`, `business`), opening_balance_cents, balance_cents, updated_at.
  For accounts with transactions, balance = opening balance + Σ amounts. Investment accounts
  carry a stored balance (no transactions in phase 1).
- **Category**: id (slug), name, group (`income`, `essential`, `discretionary`, `transfer`,
  `business`), irs_line (business categories only), deductible_pct (100, or 50 for meals).
- **Transaction**: id, account_id, source, external_id (unique per source), date, description
  (raw), merchant (normalized), amount_cents, category_id, categorized_by
  (`rule`/`ai`/`user`/`source`), rule_id, ai_rationale, business_status
  (`business`/`review`/`personal`), business_pct (0–100), reimbursement_status
  (`null`/`owed`/`reimbursed`), reimbursed_by_id, created_at, notes.
- **Rule**: id, pattern (case-insensitive substring on merchant/description), category_id,
  business_status, business_pct, priority, created_by (`system`/`user`).
- **BudgetTarget**: category_id, monthly_cents (same target every month in phase 1).
- **Setting**: key → JSON value (ai_enabled, sync_interval_minutes, household names,
  filing_status, phone_business_pct, internet_business_pct).
- **SyncRun**: id, source, started_at, finished_at, new_count, status, error.
- **MockState**: counter used to generate the deterministic "live" transaction sequence.

## 5. Sources

`Source` protocol: `list_accounts() -> list[AccountData]`,
`fetch_transactions(since: date | None) -> list[TransactionData]`. Sync upserts on
`(source, external_id)`, so re-running a sync never duplicates transactions.

**MockSource** (fictional household "Alex & Jordan Rivera", fictional institutions):

- Accounts: Harbor Federal joint checking, Summit Rewards Visa (personal), Rivera Consulting
  LLC business checking + business card (S-Corp), taxable brokerage, Northwind 401(k),
  Roth IRA, Traditional IRA, old employer 401(k).
- 12 months of history ending yesterday, generated from a fixed seed (`random.Random(42)`)
  relative to today's date: W-2 paychecks (Northwind Systems, semimonthly; Jordan's employer,
  biweekly), S-Corp client payments, officer payroll (Gusto) + payroll taxes, quarterly owner
  distributions, monthly accountable-plan reimbursements, rent, utilities, phone/internet,
  groceries, dining, gas/rideshare, shopping, subscriptions, travel, insurance, card payments.
  A realistic share of business costs (GitHub, Adobe, Zoom, AWS, flights, client meals,
  coworking) lands on the **personal** Visa.
- **Live drip:** each sync generates 1–4 new transactions dated today, seeded from
  `MockState.counter` so the sequence is deterministic.
- **Reset demo** (`POST /api/demo/reset`) wipes the DB and regenerates everything.

**CSV import** (`POST /api/import/csv`, multipart): columns `date, description, amount`
(header required; optional `category`), imported into a chosen account. external_id is a hash
of (account, date, description, amount, occurrence index) so re-importing the same file is
idempotent.

## 6. Categorization

Order for each new transaction:

1. Source-provided category (mock only, for transfers/payroll it knows about).
2. Rules, highest priority first, first match wins. User rules outrank system rules.
3. Claude (only if `ai_enabled` and `ANTHROPIC_API_KEY` set): sends merchant, description,
   amount, date and account owner — never account numbers or balances. Returns category,
   business likelihood and a one-line rationale. Uses a small/fast current Claude model.
4. Fallback: `uncategorized`.

When the user changes a category in the UI they may tick **"Always categorize <merchant> this
way"**, which creates a user rule.

## 7. Budget

For the selected month (default current), over personal owners only (`self`, `spouse`,
`joint`), excluding `transfer` and `business` categories and any transaction with
`business_status = business`:

- `spent[c]` = outflows − refunds in category `c` for the month.
- `expected_by_today[c]` = `target[c] × day_of_month / days_in_month`.
- Pace status: `over` if spent > target; `running_hot` if spent > expected × 1.10;
  else `on_track`.
- **Upcoming bills**: a merchant is recurring if it appears in ≥ 3 of the previous 4 months
  with amounts within ±15% of their median. If it has not posted yet this month and its typical
  day-of-month is after today, its median amount is an upcoming bill.
- **Safe to spend today** =
  `max(0, Σ targets − Σ spent − Σ upcoming bills) / days_remaining_including_today`,
  over budgeted categories.

## 8. S-Corp deductions & accountable plan

- Every transaction has a `business_status`:
  - **business account outflows** default to `business` if a rule maps them to a business
    category, otherwise `review`.
  - **personal account outflows** matching a business rule are `review` ("Likely business").
  - Everything else is `personal`.
- Confirming a personal-account transaction as business sets `reimbursement_status = owed`.
  Deductible amount = `|amount| × business_pct × deductible_pct`.
- **Reimbursement matching:** when a positive transaction in category
  `accountable_plan_reimbursement` posts to a personal account, owed items are marked
  `reimbursed` oldest-first while their cumulative reimbursable amount fits in the transfer.
  Items that don't fully fit stay `owed`.
- **No double counting:** the deduction lives on the original expense. The business-side
  reimbursement outflow and owner distributions are `transfer` categories, never deductions.
- **1120-S line mapping (2025 form):** Line 7 Compensation of officers; Line 8 Salaries and
  wages; Line 11 Rents (coworking/office); Line 12 Taxes and licenses (payroll taxes, state
  fees); Line 16 Advertising; Line 17 Pension/profit-sharing plans (employer Solo 401(k));
  Line 18 Employee benefit programs; **Line 20 Other deductions** with statement detail:
  software & SaaS, office supplies, professional fees, travel, meals (50%), phone & internet
  (business %), contract labor, insurance, bank & payment fees, education.
- YTD summary by line (and by statement detail for line 20) plus CSV export
  (`GET /api/business/export.csv?year=YYYY`).

## 9. API (all under `/api`)

`GET /health` · `GET /summary` (net worth, safe-to-spend, month totals, last sync) ·
`GET /accounts` · `GET /transactions` (filters: account, owner, category, business_status,
month, search; paginated) · `PATCH /transactions/{id}` (category, business_status,
business_pct, notes, `create_rule`) · `GET /categories` · `GET /budget?month=YYYY-MM` ·
`PUT /budget/{category_id}` · `GET /business/summary?year=` · `GET /business/review` ·
`GET /business/reimbursements` · `GET /business/export.csv` · `POST /sync` ·
`GET /sync/runs` · `GET /events` (SSE) · `GET/PUT /settings` · `POST /import/csv` ·
`POST /demo/reset`.

## 10. UI

- **Dashboard:** safe-to-spend today (hero number), month pace bar, category budget bars
  with pace status, live transaction feed (new items highlighted), net worth with
  personal/business/retirement breakdown, S-Corp-owes-you total, sync status + "Sync now".
- **Transactions:** filterable table, inline category edit with "always" rule option,
  business status toggle.
- **Business:** YTD deductions by 1120-S line, review queue (confirm/dismiss), reimbursement
  queue, CSV export.
- **Budget:** edit monthly targets per category, month selector.
- **Accounts:** grouped balances, source badge, CSV import.
- **Settings:** AI toggle + key status (key itself never shown), sync interval, household
  names, filing status, phone/internet business %, Reset demo.
- A persistent footer disclaimer: informational only, not tax/investment advice.
- Light and dark themes; responsive down to tablet width.

## 11. Errors & privacy

- Backend binds to 127.0.0.1 only. CORS limited to the Vite dev origin.
- Sync errors are recorded on `SyncRun` and shown in the sync status; a failed sync never
  deletes data. AI errors fall back to rules/uncategorized and are logged, not fatal.
- `data/` and `.env` are gitignored from the first commit. The API key is read from `.env`
  and never returned by the API.

## 12. Testing

- pytest: budget math (pace, upcoming bills, safe-to-spend), rule engine, business status
  and deductible amounts (meals 50%, business %), reimbursement FIFO matching, mock
  generator determinism, sync idempotency, CSV import idempotency, API smoke via TestClient.
- Vitest: money/date formatting utilities. TypeScript type-check and production build in CI.
- Manual: dashboard verified in a browser (live update after "Sync now").

## 13. Version control

- Public GitHub repo `TheAaravSikriwal/ledgerpilot`, MIT license.
- `main` is the release branch. Phase work happens on `feat/phase-1-foundation`, small
  conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`), merged via PR.
- GitHub Actions on push/PR: backend (ruff + pytest), frontend (tsc + vitest + build),
  secret scan (gitleaks).
- On merge: tag `v0.1.0`, GitHub release, `CHANGELOG.md` (Keep a Changelog format).

## 14. Out of scope for phase 1

Real bank connections, investment lots/TLH, retirement documents, PDF statement parsing,
budget rollovers, multi-currency, authentication (single local user), DB encryption at rest
(planned before real data arrives in phase 4).
