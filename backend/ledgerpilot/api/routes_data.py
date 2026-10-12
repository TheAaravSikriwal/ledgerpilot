"""Read/write endpoints for accounts, transactions, categories, budget and summary."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from ..business import business_summary
from ..db import get_session
from ..models import Account, BudgetTarget, Category, SyncRun, Transaction
from ..services import apply_user_edit, create_rule_from, load_budget
from ..sync import run_to_dict
from .serialize import account_out, budget_out, category_out, txn_out

router = APIRouter()

CASH_TYPES = ("checking", "savings")
RETIREMENT_TYPES = ("401k", "ira_roth", "ira_traditional")


def today_of(request: Request) -> date:
    return request.app.state.today()


@router.get("/summary")
def summary(request: Request, session: Session = Depends(get_session)):
    today = today_of(request)
    accounts = session.scalars(select(Account)).all()
    breakdown = {"cash": 0, "credit": 0, "business": 0, "investments": 0, "retirement": 0}
    for a in accounts:
        if a.owner == "business":
            breakdown["business"] += a.balance_cents
        elif a.type in CASH_TYPES:
            breakdown["cash"] += a.balance_cents
        elif a.type == "credit_card":
            breakdown["credit"] += a.balance_cents
        elif a.type in RETIREMENT_TYPES:
            breakdown["retirement"] += a.balance_cents
        else:
            breakdown["investments"] += a.balance_cents
    budget = load_budget(session, today.year, today.month, today)
    biz = business_summary(session, today.year)
    last = session.scalars(
        select(SyncRun).where(SyncRun.finished_at.is_not(None)).order_by(SyncRun.id.desc())
    ).first()
    return {
        "today": today,
        "net_worth_cents": sum(breakdown.values()),
        "net_worth_breakdown": {f"{k}_cents": v for k, v in breakdown.items()},
        "safe_to_spend_today_cents": budget.safe_to_spend_today_cents,
        "budget": {
            "month": f"{budget.year:04d}-{budget.month:02d}",
            "target_cents": budget.target_cents,
            "spent_cents": budget.spent_cents,
            "expected_by_today_cents": budget.expected_by_today_cents,
            "upcoming_bills_cents": budget.upcoming_bills_cents,
            "days_remaining": budget.days_remaining,
            "days_in_month": budget.days_in_month,
            "status": budget.status,
        },
        "business": {
            "ytd_deductions_cents": biz["total_deductions_cents"],
            "ytd_income_cents": biz["income_cents"],
            "review_count": biz["review_count"],
            "owed_to_you_cents": biz["owed_cents"],
        },
        "last_sync": run_to_dict(last) if last else None,
    }


@router.get("/accounts")
def accounts(session: Session = Depends(get_session)):
    return [account_out(a) for a in session.scalars(select(Account).order_by(Account.id)).all()]


@router.get("/categories")
def categories(session: Session = Depends(get_session)):
    rows = session.scalars(select(Category).order_by(Category.sort_order)).all()
    return [category_out(c) for c in rows]


@router.get("/transactions")
def transactions(
    session: Session = Depends(get_session),
    account_id: int | None = None,
    owner: str | None = None,
    category_id: str | None = None,
    business_status: str | None = None,
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    q: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(Transaction).join(Account)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if owner == "personal":
        stmt = stmt.where(Account.owner != "business")
    elif owner:
        stmt = stmt.where(Account.owner == owner)
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if business_status:
        stmt = stmt.where(Transaction.business_status == business_status)
    if month:
        y, m = (int(p) for p in month.split("-"))
        stmt = stmt.where(
            extract("year", Transaction.date) == y, extract("month", Transaction.date) == m
        )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Transaction.description.ilike(like), Transaction.merchant.ilike(like))
        )
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(
        stmt.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).offset(offset)
    ).unique()
    return {"items": [txn_out(t) for t in rows], "total": total}


class TransactionPatch(BaseModel):
    category_id: str | None = None
    business_status: str | None = None
    business_pct: int | None = Field(None, ge=0, le=100)
    notes: str | None = None
    create_rule: bool = False


@router.patch("/transactions/{txn_id}")
def update_transaction(
    txn_id: int, patch: TransactionPatch, request: Request, session: Session = Depends(get_session)
):
    txn = session.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(404, "transaction not found")
    try:
        apply_user_edit(
            session,
            txn,
            category_id=patch.category_id,
            business_status=patch.business_status,
            business_pct=patch.business_pct,
            notes=patch.notes,
        )
        if patch.create_rule:
            create_rule_from(session, txn)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.commit()
    request.app.state.bus.publish("updated", {"transaction_id": txn_id})
    return txn_out(txn)


@router.get("/budget")
def budget(
    request: Request,
    session: Session = Depends(get_session),
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
):
    today = today_of(request)
    y, m = (int(p) for p in month.split("-")) if month else (today.year, today.month)
    return budget_out(load_budget(session, y, m, today))


class BudgetPut(BaseModel):
    monthly_cents: int = Field(ge=0, le=100_000_000)


@router.put("/budget/{category_id}")
def set_budget(
    category_id: str, body: BudgetPut, request: Request, session: Session = Depends(get_session)
):
    category = session.get(Category, category_id)
    if category is None or category.group not in ("essential", "discretionary"):
        raise HTTPException(422, "category is not budgetable")
    target = session.get(BudgetTarget, category_id)
    if target is None:
        session.add(BudgetTarget(category_id=category_id, monthly_cents=body.monthly_cents))
    else:
        target.monthly_cents = body.monthly_cents
    session.commit()
    request.app.state.bus.publish("updated", {"budget": category_id})
    return {"category_id": category_id, "monthly_cents": body.monthly_cents}
