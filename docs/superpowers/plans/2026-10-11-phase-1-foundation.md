# LedgerPilot Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A demo-ready local finance app (v0.1.0): mock bank data syncing live into a React dashboard with a daily budget pace, safe-to-spend, and S-Corp deduction / accountable-plan tracking.

**Architecture:** FastAPI + SQLite backend (127.0.0.1:8000) with a pluggable `Source` layer (MockSource now), a sync engine run by an asyncio scheduler, and pure-function budget/business modules. A Vite React dashboard consumes REST + SSE. Spec: `docs/superpowers/specs/2026-10-11-phase-1-foundation-design.md`.

**Tech Stack:** Python 3.12+ (FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest, ruff, anthropic), React 19 + TypeScript (Vite, TanStack Query, React Router, Tailwind v4, Recharts, lucide-react, Vitest), GitHub Actions.

**Execution note:** Executed inline in one session under time pressure. Interfaces, test cases and
commands are specified exactly below; full implementation lives in the commits.

---

## File map

```
backend/
  pyproject.toml                    deps, ruff + pytest config
  alembic.ini, migrations/          Alembic env + 0001 initial schema
  ledgerpilot/
    main.py                         create_app(), lifespan (migrate, seed, scheduler)
    config.py                       Settings (env): DATA_DIR, DB_URL, ANTHROPIC_API_KEY, CORS origin
    db.py                           engine, SessionLocal, get_session dependency
    models.py                       ORM: Account, Category, Transaction, Rule, BudgetTarget, Setting, SyncRun, MockState
    seed.py                         categories, system rules, budget targets, default settings
    money.py                        cents helpers
    settings_store.py               typed get/put for Setting rows
    categorize/rules.py             match_rule(), apply_categorization()
    categorize/ai.py                AICategorizer (opt-in, Claude)
    budget.py                       compute_budget() — pure
    business.py                     deductible_cents(), reimbursable_cents(), match_reimbursements(), business_summary(), export_csv()
    sources/base.py                 AccountData, TransactionData, Source protocol
    sources/mock.py                 MockSource (per-day deterministic generator + live drip)
    sources/csv_import.py           parse_csv() → TransactionData
    sync.py                         SyncEngine.run()
    events.py                       EventBus (asyncio fan-out for SSE)
    scheduler.py                    background sync loop
    api/schemas.py                  Pydantic response models
    api/routes/*.py                 summary, accounts, transactions, categories, budget, business, sync, events, settings, imports, demo
  tests/                            test_rules, test_business, test_budget, test_mock, test_sync, test_csv, test_ai, test_api
frontend/
  package.json, vite.config.ts, tsconfig*.json, index.html
  src/main.tsx, App.tsx, index.css
  src/lib/api.ts (typed client), types.ts, format.ts (+ format.test.ts), useLiveSync.ts
  src/components/ Layout, Card, Money, StatusPill, CategoryBar, TxnTable, SyncButton, Disclaimer ...
  src/pages/ Dashboard, Transactions, Business, Budget, Accounts, Settings
scripts/setup.mjs, scripts/dev-api.mjs   cross-platform venv bootstrap / backend launcher
package.json                              npm run setup | dev | test
.github/workflows/ci.yml                  backend, frontend, gitleaks
README.md, CHANGELOG.md, .env.example, .gitattributes
```

## Key contracts

Sign convention: negative = money out. All money fields are integer `*_cents`.

```python
@dataclass
class AccountData:  external_id: str; name: str; institution: str; type: str; owner: str; current_balance_cents: int | None
@dataclass
class TransactionData: external_id: str; account_external_id: str; date: date; description: str; amount_cents: int
                       merchant: str | None = None; category_id: str | None = None
                       hint_business_status: str | None = None; hint_business_pct: int | None = None
class Source(Protocol):
    name: str
    def list_accounts(self) -> list[AccountData]: ...
    def fetch_transactions(self, since: date | None) -> list[TransactionData]: ...
```

Business math (in `business.py`):
- `reimbursable_cents(t) = round(|amount| * business_pct / 100)` for outflows with `business_status == "business"` on personal owners, else 0.
- `deductible_cents(t, cat) = round(|amount| * business_pct/100 * cat.deductible_pct/100)` for outflows with `business_status == "business"` and `cat.irs_line` set (or `business_other` fallback → line 20); inflow refunds subtract.
- `match_reimbursements(session)`: for each unapplied positive `accountable_plan_reimbursement` txn on a personal account (date order), mark owed items with date ≤ transfer date oldest-first while cumulative ≤ amount + 1¢; stop at first that does not fit; mark transfer `reimbursement_status="applied"`.

Budget (in `budget.py`), personal owners only, categories in groups `essential`/`discretionary`:
- counted amount = `|amount| * (100 - business_pct)/100` when status `business`; review items count in their category's `personal_fallback_id`; refunds subtract.
- status: `over` > target; `running_hot` > expected×1.10; else `on_track`.
- recurring merchant: ≥3 of previous 4 months, amounts within ±15% of median; upcoming if not posted this month and median day > today.
- `safe_to_spend_today = max(0, Σtarget − Σspent − Σupcoming) // days_remaining_incl_today`.

REST endpoints and JSON shapes: as in spec §9; response models in `api/schemas.py`.
SSE: `event: sync` with `data: {"run_id", "new_count", "new_ids": [...], "status"}`; `event: ping` every 20s.

---

### Task 0: Repo hygiene & GitHub
- [ ] `.gitattributes` (`* text=auto eol=lf`), README skeleton, `.env.example`, CHANGELOG (Unreleased).
- [ ] `gh repo create TheAaravSikriwal/ledgerpilot --public --source . --push`.
- [ ] `git switch -c feat/phase-1-foundation`.

### Task 1: Backend scaffold
- [ ] `backend/pyproject.toml` (fastapi, uvicorn[standard], sqlalchemy>=2, alembic, pydantic-settings, python-multipart, anthropic; dev: pytest, httpx, ruff).
- [ ] `config.py`, `db.py`, `main.py` with `GET /api/health → {"status":"ok","version":"0.1.0"}`.
- [ ] Test `tests/test_api.py::test_health` → run `pytest -q` → PASS. Commit `feat(backend): scaffold FastAPI app`.

### Task 2: Models, migration, seed
- [ ] `models.py` per spec §4 (+ `Category.personal_fallback_id`, `Transaction.reimbursement_status` incl. `applied`).
- [ ] Alembic env reading `ledgerpilot.models.Base.metadata`; generate `0001_initial`.
- [ ] `seed.py` idempotent: categories (incl. 1120-S lines 7, 8, 11, 12, 16, 17, 18, 20), system rules, budget targets, settings defaults.
- [ ] Test: fresh DB → migrate → seed twice → counts stable. Commit.

### Task 3: Rule engine
- [ ] Tests: user rule beats system rule; business account + business category → `business`; personal account + business rule → `review`; phone_internet rule on personal → `business` with `phone_internet_business_pct`; unknown business-account outflow → `review` + `business_other`; no match → `uncategorized`.
- [ ] Implement `categorize/rules.py`. PASS. Commit.

### Task 4: Business module
- [ ] Tests: meal 50%; phone 40% of $100 → deductible $40, reimbursable $40; refunds subtract; FIFO reimbursement exact match marks items, leaves later items owed; summary groups by line with line-20 details; CSV header row.
- [ ] Implement `business.py`. PASS. Commit.

### Task 5: Budget module
- [ ] Tests: pace statuses at day 15/30; business-pct exclusion; review → fallback category; recurring detection (3 of 4 months, ±15%); safe-to-spend formula incl. floor at 0; past month → days_remaining 0.
- [ ] Implement `budget.py`. PASS. Commit.

### Task 6: MockSource
- [ ] Tests: same seed+date → identical output; external_ids unique; history ends yesterday; live drip count n → n live txns dated today; Visa business items exist with hints; monthly reimbursement equals hinted reimbursable sum of prior month.
- [ ] Implement `sources/base.py`, `sources/mock.py`. PASS. Commit.

### Task 7: Sync engine, events, scheduler
- [ ] Tests: first sync inserts history + balances; second sync inserts only new live items; user edits not overwritten by re-sync; SyncRun recorded; failure recorded without data loss.
- [ ] Implement `sync.py`, `events.py`, `scheduler.py`; wire into lifespan. PASS. Commit.

### Task 8: CSV import
- [ ] Tests: parse valid file; missing header → 400; re-import same file → 0 new.
- [ ] Implement `sources/csv_import.py` + route. PASS. Commit.

### Task 9: AI categorizer (opt-in)
- [ ] Tests with fake client: disabled → not called; enabled → payload has no account numbers/balances; bad response → falls back to uncategorized.
- [ ] Implement `categorize/ai.py` with Claude tool-use structured output. PASS. Commit.

### Task 10: API routes
- [ ] Implement all routes in spec §9 with schemas.
- [ ] TestClient smoke: reset demo → summary has safe_to_spend; transactions filter by business_status=review; PATCH with create_rule creates rule; budget PUT; business summary; export.csv content-type; settings never return key. PASS. Commit.

### Task 11: Frontend scaffold
- [ ] Vite React TS + Tailwind v4 + Router + Query; `/api` proxy; typed client; `useLiveSync` (EventSource → invalidate queries, track new ids); Layout with sidebar nav, theme, disclaimer footer.
- [ ] Vitest `format.test.ts` (money, signed money, dates). `npm run build` passes. Commit.

### Task 12–15: Pages
- [ ] Dashboard, Transactions, Business, Budget, Accounts, Settings per spec §10. Commit per page.

### Task 16: Tooling & CI
- [ ] Root `package.json` (`setup`, `dev`, `test`), `scripts/setup.mjs`, `scripts/dev-api.mjs`.
- [ ] `.github/workflows/ci.yml` (backend ruff+pytest on 3.14, frontend tsc+vitest+build on Node 20, gitleaks).
- [ ] README: what it is, screenshots, quick start, privacy, roadmap, disclaimer. CHANGELOG 0.1.0. Commit.

### Task 17: Verify & release
- [ ] `npm run dev`; verify in browser: dashboard loads, Sync now adds highlighted txns, review → confirm moves item to reimbursements, budget edit updates pace, export downloads.
- [ ] Push branch, open PR, CI green, merge, tag `v0.1.0`, GitHub release.
