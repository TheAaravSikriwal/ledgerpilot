"""Sync, live events, settings, CSV import, demo reset and health."""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import __version__
from ..business import match_reimbursements
from ..db import get_session
from ..demo import reset_demo
from ..models import Account, SyncRun, Transaction
from ..settings_store import FILING_STATUSES, get_settings, put_settings
from ..sources.csv_import import CSVImportError, parse_csv
from ..sync import ingest, recompute_balances, run_to_dict

router = APIRouter()

MAX_CSV_BYTES = 5 * 1024 * 1024


@router.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@router.post("/sync")
async def sync_now(request: Request):
    return await asyncio.to_thread(request.app.state.sync_engine.run, "manual")


@router.get("/sync/runs")
def sync_runs(session: Session = Depends(get_session)):
    rows = session.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(20)).all()
    return [run_to_dict(r) for r in rows]


@router.get("/events")
async def events(request: Request):
    return StreamingResponse(
        request.app.state.bus.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _settings_out(request: Request, session: Session) -> dict[str, Any]:
    # The API key itself is never returned — only whether one is configured.
    return {**get_settings(session), "ai_available": request.app.state.config.ai_available}


@router.get("/settings")
def read_settings(request: Request, session: Session = Depends(get_session)):
    return _settings_out(request, session)


class SettingsPut(BaseModel):
    ai_enabled: bool | None = None
    sync_interval_minutes: int | None = Field(None, ge=1, le=1440)
    self_name: str | None = Field(None, min_length=1, max_length=40)
    spouse_name: str | None = Field(None, max_length=40)
    business_name: str | None = Field(None, min_length=1, max_length=80)
    filing_status: str | None = None
    phone_internet_business_pct: int | None = Field(None, ge=0, le=100)


@router.put("/settings")
def write_settings(body: SettingsPut, request: Request, session: Session = Depends(get_session)):
    values = body.model_dump(exclude_none=True)
    if "filing_status" in values and values["filing_status"] not in FILING_STATUSES:
        raise HTTPException(422, f"filing_status must be one of {', '.join(FILING_STATUSES)}")
    if values.get("ai_enabled") and not request.app.state.config.ai_available:
        raise HTTPException(422, "add ANTHROPIC_API_KEY to .env to enable AI features")
    put_settings(session, values)
    if "phone_internet_business_pct" in values:
        pct = values["phone_internet_business_pct"]
        for t in session.scalars(
            select(Transaction).where(
                Transaction.category_id == "phone_internet",
                Transaction.business_status == "business",
                Transaction.user_locked.is_(False),
            )
        ).unique():
            t.business_pct = pct
        session.flush()
        match_reimbursements(session)
        session.commit()
    request.app.state.bus.publish("updated", {"settings": list(values)})
    return _settings_out(request, session)


@router.post("/import/csv")
async def import_csv(
    request: Request,
    account_id: int = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "account not found")
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(413, "CSV larger than 5 MB")
    try:
        rows = parse_csv(raw.decode("utf-8-sig"), f"account-{account.id}")
    except (CSVImportError, UnicodeDecodeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    created = ingest(
        session, "csv", rows, lambda _d: account, request.app.state.sync_engine.ai_categorizer
    )
    recompute_balances(session, [account])
    match_reimbursements(session)
    session.commit()
    request.app.state.bus.publish(
        "sync", {"status": "ok", "new_count": len(created), "new_ids": [t.id for t in created]}
    )
    return {"imported": len(created), "skipped": len(rows) - len(created)}


def _reset_and_sync(state) -> dict[str, Any]:
    with state.sync_engine.lock:  # never wipe data while a sync is mid-flight
        reset_demo(state.session_factory, state.config.ledgerpilot_mock_seed, state.today())
    return state.sync_engine.run("reset")


@router.post("/demo/reset")
async def demo_reset(request: Request):
    return await asyncio.to_thread(_reset_and_sync, request.app.state)
