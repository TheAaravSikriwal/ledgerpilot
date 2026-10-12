"""S-Corp deductions (Form 1120-S lines) and the accountable-plan reimbursement queue.

Rules of the road:
- A deduction lives on the original expense. Reimbursement transfers and owner distributions
  are transfer categories and are never deductible, so nothing is counted twice.
- Business costs paid from personal accounts are reimbursable at 100% of their business share
  (meals included); the S-Corp then deducts per the category's deductible percentage.
"""

import csv
import io
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from .categorize.rules import PERSONAL_LOOKING_GROUPS
from .models import BUSINESS_OWNER, PERSONAL_OWNERS, Account, Category, Transaction
from .money import dollars, pct_of
from .seed import IRS_LINES

REIMBURSEMENT_CATEGORY = "accountable_plan_reimbursement"
ROUNDING_TOLERANCE_CENTS = 1


def deduction_line(category: Category) -> tuple[str, str] | None:
    """The 1120-S line (and statement detail) a confirmed business expense rolls up to."""
    if category.irs_line:
        return category.irs_line, category.irs_detail or category.name
    if category.group in PERSONAL_LOOKING_GROUPS:
        return "20", "Other"
    return None


def deductible_cents(
    amount_cents: int, business_status: str, business_pct: int, category: Category
) -> int:
    """Deductible amount (positive for expenses, negative for refunds)."""
    if business_status != "business" or deduction_line(category) is None:
        return 0
    return pct_of(-amount_cents, business_pct, category.deductible_pct)


def reimbursable_cents(
    amount_cents: int, owner: str, business_status: str, business_pct: int
) -> int:
    """What the S-Corp owes the owner for a business cost paid from a personal account."""
    if owner not in PERSONAL_OWNERS or business_status != "business" or amount_cents >= 0:
        return 0
    return pct_of(-amount_cents, business_pct)


def allocate_reimbursement(
    amount_cents: int, transfer_date: date, owed: Sequence[tuple[int, date, int]]
) -> list[int]:
    """FIFO-allocate a reimbursement transfer to owed items (id, date, reimbursable_cents).

    Takes items dated on/before the transfer, oldest first, while the running total fits;
    stops at the first item that does not fit.
    """
    taken: list[int] = []
    remaining = amount_cents
    for item_id, item_date, cents in sorted(owed, key=lambda o: (o[1], o[0])):
        if item_date > transfer_date:
            break
        if cents > remaining + ROUNDING_TOLERANCE_CENTS:
            break
        taken.append(item_id)
        remaining -= cents
    return taken


def txn_reimbursable(t: Transaction) -> int:
    return reimbursable_cents(t.amount_cents, t.account.owner, t.business_status, t.business_pct)


def refresh_owed_flags(session: Session) -> None:
    """Keep reimbursement_status consistent with each personal transaction's business status."""
    rows = session.scalars(
        select(Transaction)
        .join(Account)
        .where(Account.owner.in_(PERSONAL_OWNERS), Transaction.amount_cents < 0)
        .where(Transaction.category_id != REIMBURSEMENT_CATEGORY)
    ).all()
    for t in rows:
        owes = txn_reimbursable(t) > 0
        if owes and t.reimbursement_status is None:
            t.reimbursement_status = "owed"
        elif not owes and t.reimbursement_status == "owed":
            t.reimbursement_status = None


def match_reimbursements(session: Session) -> int:
    """Apply unallocated reimbursement transfers to owed items. Returns items marked."""
    refresh_owed_flags(session)
    transfers = session.scalars(
        select(Transaction)
        .join(Account)
        .where(
            Transaction.category_id == REIMBURSEMENT_CATEGORY,
            Transaction.amount_cents > 0,
            Account.owner.in_(PERSONAL_OWNERS),
            Transaction.reimbursement_status.is_(None),
        )
        .order_by(Transaction.date, Transaction.id)
    ).all()
    marked = 0
    for transfer in transfers:
        owed_rows = session.scalars(
            select(Transaction).where(Transaction.reimbursement_status == "owed")
        ).all()
        by_id = {t.id: t for t in owed_rows}
        owed = [(t.id, t.date, txn_reimbursable(t)) for t in owed_rows]
        for item_id in allocate_reimbursement(transfer.amount_cents, transfer.date, owed):
            by_id[item_id].reimbursement_status = "reimbursed"
            by_id[item_id].reimbursed_by_id = transfer.id
            marked += 1
        transfer.reimbursement_status = "applied"
    session.flush()
    return marked


def _year_business_rows(session: Session, year: int) -> list[Transaction]:
    return list(
        session.scalars(
            select(Transaction)
            .where(extract("year", Transaction.date) == year)
            .where(Transaction.business_status == "business")
            .order_by(Transaction.date)
        ).all()
    )


def business_summary(session: Session, year: int) -> dict:
    lines: dict[str, dict] = {}
    details: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    income = 0
    for t in _year_business_rows(session, year):
        if t.account.owner == BUSINESS_OWNER and t.category_id == "business_income":
            income += t.amount_cents
        line = deduction_line(t.category)
        if line is None:
            continue
        amount = deductible_cents(t.amount_cents, t.business_status, t.business_pct, t.category)
        number, detail = line
        details[number][detail] += amount

    for number, label in IRS_LINES.items():
        if number not in details:
            continue
        items = sorted(details[number].items(), key=lambda kv: -kv[1])
        lines[number] = {
            "line": number,
            "label": label,
            "amount_cents": sum(v for _, v in items),
            "details": [{"name": k, "amount_cents": v} for k, v in items],
        }

    owed_rows = session.scalars(
        select(Transaction).where(Transaction.reimbursement_status == "owed")
    ).all()
    reimbursed_rows = session.scalars(
        select(Transaction)
        .where(Transaction.reimbursement_status == "reimbursed")
        .where(extract("year", Transaction.date) == year)
    ).all()
    review_count = len(
        session.scalars(select(Transaction.id).where(Transaction.business_status == "review")).all()
    )
    ordered = [lines[n] for n in sorted(lines, key=int)]
    return {
        "year": year,
        "income_cents": income,
        "total_deductions_cents": sum(line["amount_cents"] for line in ordered),
        "lines": ordered,
        "review_count": review_count,
        "owed_cents": sum(txn_reimbursable(t) for t in owed_rows),
        "reimbursed_cents": sum(txn_reimbursable(t) for t in reimbursed_rows),
    }


def export_csv(session: Session, year: int) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "date",
            "description",
            "account",
            "paid_from",
            "category",
            "form_1120s_line",
            "line_detail",
            "amount",
            "business_pct",
            "deductible_pct",
            "deductible_amount",
            "reimbursement_status",
        ]
    )
    for t in _year_business_rows(session, year):
        line = deduction_line(t.category)
        if line is None:
            continue
        writer.writerow(
            [
                t.date.isoformat(),
                t.description,
                t.account.name,
                "business" if t.account.owner == BUSINESS_OWNER else "personal",
                t.category.name,
                line[0],
                line[1],
                dollars(t.amount_cents),
                t.business_pct,
                t.category.deductible_pct,
                dollars(
                    deductible_cents(t.amount_cents, t.business_status, t.business_pct, t.category)
                ),
                t.reimbursement_status or "",
            ]
        )
    return out.getvalue()
