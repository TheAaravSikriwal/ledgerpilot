"""S-Corp endpoints: deduction summary, review queue, reimbursements, CPA export."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from ..business import business_summary, export_csv, txn_reimbursable
from ..db import get_session
from ..models import Transaction
from .serialize import txn_out

router = APIRouter(prefix="/business")


def _year(request: Request, year: int | None) -> int:
    return year or request.app.state.today().year


@router.get("/summary")
def summary(request: Request, year: int | None = None, session: Session = Depends(get_session)):
    return business_summary(session, _year(request, year))


@router.get("/review")
def review(session: Session = Depends(get_session)):
    rows = session.scalars(
        select(Transaction)
        .where(Transaction.business_status == "review")
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    ).unique()
    return [txn_out(t) for t in rows]


@router.get("/reimbursements")
def reimbursements(
    request: Request, year: int | None = None, session: Session = Depends(get_session)
):
    owed = (
        session.scalars(
            select(Transaction)
            .where(Transaction.reimbursement_status == "owed")
            .order_by(Transaction.date.desc())
        )
        .unique()
        .all()
    )
    reimbursed = (
        session.scalars(
            select(Transaction)
            .where(Transaction.reimbursement_status == "reimbursed")
            .where(extract("year", Transaction.date) == _year(request, year))
            .order_by(Transaction.date.desc())
        )
        .unique()
        .all()
    )
    return {
        "owed": [txn_out(t) for t in owed],
        "reimbursed": [txn_out(t) for t in reimbursed],
        "owed_total_cents": sum(txn_reimbursable(t) for t in owed),
        "reimbursed_total_cents": sum(txn_reimbursable(t) for t in reimbursed),
    }


@router.get("/export.csv")
def export(request: Request, year: int | None = None, session: Session = Depends(get_session)):
    y = _year(request, year)
    return Response(
        export_csv(session, y),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="ledgerpilot-1120s-{y}.csv"'},
    )
