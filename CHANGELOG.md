# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-11

### Added

- FastAPI backend bound to `127.0.0.1` with SQLite storage, Alembic migrations and integer-cent
  money handling.
- Source connector contract with a deterministic mock bank (fictional household + S-Corp, a year
  of history, live "drip" transactions on each sync) and idempotent CSV statement import.
- Sync engine with background scheduler, manual "Sync now", failure recording and Server-Sent
  Events so the dashboard updates without reloading.
- Rule-based categorization (user rules outrank system rules, "make it a rule" learns from
  corrections) plus opt-in Claude categorization that never sends account details.
- Monthly budget with recurring-bill-aware pacing, upcoming bill detection and
  "safe to spend today".
- S-Corp deduction tracking mapped to Form 1120-S lines, 50% meals, mixed-use phone & internet,
  review queue and CPA CSV export.
- Accountable-plan reimbursement queue with automatic FIFO matching of reimbursement transfers.
- React dashboard: Overview, Transactions, S-Corp, Budget, Accounts and Settings pages with
  light/dark themes and a colorblind-validated chart palette.
- One-command `npm run setup` / `npm run dev` / `npm test`, GitHub Actions CI (ruff, pytest,
  typecheck, vitest, build, gitleaks) and Dependabot.

[Unreleased]: https://github.com/TheAaravSikriwal/ledgerpilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/TheAaravSikriwal/ledgerpilot/releases/tag/v0.1.0
