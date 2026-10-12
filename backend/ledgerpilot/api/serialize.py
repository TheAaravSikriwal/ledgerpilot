"""JSON shapes returned by the API. Money is always integer cents."""

from dataclasses import asdict
from typing import Any

from ..budget import BudgetResult
from ..business import deductible_cents, deduction_line, txn_reimbursable
from ..models import Account, Category, Transaction


def account_out(a: Account) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.name,
        "institution": a.institution,
        "type": a.type,
        "owner": a.owner,
        "balance_cents": a.balance_cents,
        "source": a.source,
        "updated_at": a.updated_at,
    }


def category_out(c: Category) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "group": c.group,
        "irs_line": c.irs_line,
        "irs_detail": c.irs_detail,
        "deductible_pct": c.deductible_pct,
        "personal_fallback_id": c.personal_fallback_id,
    }


def txn_out(t: Transaction) -> dict[str, Any]:
    line = deduction_line(t.category)
    return {
        "id": t.id,
        "account_id": t.account_id,
        "account_name": t.account.name,
        "owner": t.account.owner,
        "date": t.date,
        "description": t.description,
        "merchant": t.merchant,
        "amount_cents": t.amount_cents,
        "category_id": t.category_id,
        "category_name": t.category.name,
        "category_group": t.category.group,
        "categorized_by": t.categorized_by,
        "ai_rationale": t.ai_rationale,
        "business_status": t.business_status,
        "business_pct": t.business_pct,
        "irs_line": line[0] if line and t.business_status != "personal" else None,
        # For items still in review this is the potential deduction if confirmed.
        "deductible_cents": deductible_cents(
            t.amount_cents,
            "personal" if t.business_status == "personal" else "business",
            t.business_pct,
            t.category,
        ),
        "reimbursable_cents": txn_reimbursable(t),
        "reimbursement_status": t.reimbursement_status,
        "user_locked": t.user_locked,
        "notes": t.notes,
        "created_at": t.created_at,
    }


def budget_out(r: BudgetResult) -> dict[str, Any]:
    return {
        "month": f"{r.year:04d}-{r.month:02d}",
        "today": r.today,
        "days_in_month": r.days_in_month,
        "days_remaining": r.days_remaining,
        "target_cents": r.target_cents,
        "spent_cents": r.spent_cents,
        "expected_by_today_cents": r.expected_by_today_cents,
        "upcoming_bills_cents": r.upcoming_bills_cents,
        "safe_to_spend_today_cents": r.safe_to_spend_today_cents,
        "status": r.status,
        "categories": [asdict(c) for c in r.categories],
        "upcoming_bills": [asdict(b) for b in r.upcoming_bills],
    }
