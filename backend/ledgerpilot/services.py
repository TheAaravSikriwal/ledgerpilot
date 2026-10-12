"""Query + mutation helpers shared by API routes (keeps route handlers thin)."""

from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .budget import BudgetResult, BudgetTxn, compute_budget
from .business import match_reimbursements
from .categorize.rules import match_rule
from .models import (
    BUSINESS_OWNER,
    PERSONAL_OWNERS,
    Account,
    BudgetTarget,
    Category,
    Rule,
    Transaction,
)
from .settings_store import get_setting


def _month_start(year: int, month: int, offset: int = 0) -> date:
    index = year * 12 + (month - 1) + offset
    return date(index // 12, index % 12 + 1, 1)


def _budget_txns(session: Session, start: date, end: date) -> list[BudgetTxn]:
    rows = session.execute(
        select(
            Transaction.date,
            Transaction.merchant,
            Transaction.amount_cents,
            Transaction.category_id,
            Transaction.business_status,
            Transaction.business_pct,
        )
        .join(Account)
        .where(
            and_(
                Account.owner.in_(PERSONAL_OWNERS),
                Transaction.date >= start,
                Transaction.date < end,
            )
        )
    ).all()
    return [BudgetTxn(*row) for row in rows]


def load_budget(session: Session, year: int, month: int, today: date) -> BudgetResult:
    categories = {c.id: c for c in session.scalars(select(Category)).all()}
    targets = {b.category_id: b.monthly_cents for b in session.scalars(select(BudgetTarget))}
    month_start, next_start = _month_start(year, month), _month_start(year, month, 1)
    return compute_budget(
        year,
        month,
        today,
        targets,
        categories,
        _budget_txns(session, month_start, next_start),
        _budget_txns(session, _month_start(year, month, -4), month_start),
    )


def user_status_for(category: Category, owner: str, mixed_pct: int) -> tuple[str, int]:
    """Business status implied by a category the user picked by hand."""
    if owner == BUSINESS_OWNER or category.group == "business":
        return "business", 100
    if category.irs_line:  # mixed-use personal category, e.g. phone & internet
        return "business", mixed_pct
    return "personal", 0


def apply_user_edit(
    session: Session,
    txn: Transaction,
    *,
    category_id: str | None = None,
    business_status: str | None = None,
    business_pct: int | None = None,
    notes: str | None = None,
) -> None:
    mixed_pct = get_setting(session, "phone_internet_business_pct")
    if category_id is not None:
        category = session.get(Category, category_id)
        if category is None:
            raise ValueError(f"unknown category {category_id}")
        txn.category_id, txn.category = category.id, category
        txn.business_status, txn.business_pct = user_status_for(
            category, txn.account.owner, mixed_pct
        )
        txn.categorized_by = "user"
    if business_status is not None:
        if business_status not in ("business", "review", "personal"):
            raise ValueError(f"invalid business_status {business_status}")
        if business_status == "personal" and txn.category.group == "business":
            fallback = session.get(Category, txn.category.personal_fallback_id or "uncategorized")
            txn.category_id, txn.category = fallback.id, fallback
        txn.business_status = business_status
        if business_status == "personal":
            txn.business_pct = 0
        elif txn.business_pct == 0:
            txn.business_pct = mixed_pct if txn.category.group != "business" else 100
        txn.categorized_by = "user"
    if business_pct is not None:
        if not 0 <= business_pct <= 100:
            raise ValueError("business_pct must be between 0 and 100")
        txn.business_pct = business_pct
    if notes is not None:
        txn.notes = notes
    txn.user_locked = True
    session.flush()
    match_reimbursements(session)


def create_rule_from(session: Session, txn: Transaction) -> Rule:
    """'Always categorize <merchant> this way' — saves a user rule and applies it to every
    matching transaction the user has not edited by hand."""
    rule = Rule(
        pattern=txn.merchant.upper(),
        category_id=txn.category_id,
        business_status=txn.business_status if txn.business_status != "personal" else None,
        business_pct=txn.business_pct if txn.business_status == "business" else None,
        priority=100,
        created_by="user",
    )
    session.add(rule)
    session.flush()
    for other in session.scalars(
        select(Transaction).where(Transaction.user_locked.is_(False), Transaction.id != txn.id)
    ).all():
        if match_rule([rule], f"{other.description} {other.merchant}", other.account.owner):
            other.category_id, other.category = txn.category_id, txn.category
            other.business_status = txn.business_status
            other.business_pct = txn.business_pct
            other.categorized_by, other.rule_id = "rule", rule.id
    session.flush()
    match_reimbursements(session)
    return rule
