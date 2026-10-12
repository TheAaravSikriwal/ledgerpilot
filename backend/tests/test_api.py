from datetime import date

import pytest
from fastapi.testclient import TestClient

from ledgerpilot.config import AppConfig
from ledgerpilot.main import create_app

TODAY = date(2026, 10, 11)


@pytest.fixture
def client(tmp_path):
    config = AppConfig(
        _env_file=None,
        ledgerpilot_db_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        ledgerpilot_scheduler=False,
        anthropic_api_key=None,
    )
    with TestClient(create_app(config, today=lambda: TODAY)) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "version": "0.1.0"}


def test_summary(client):
    s = client.get("/api/summary").json()
    assert s["net_worth_cents"] > 0
    assert s["safe_to_spend_today_cents"] >= 0
    assert s["business"]["review_count"] > 0
    assert s["business"]["owed_to_you_cents"] > 0
    assert s["last_sync"]["status"] == "ok"


def test_transaction_filters(client):
    page = client.get("/api/transactions", params={"business_status": "review"}).json()
    assert page["total"] > 0
    assert all(t["business_status"] == "review" for t in page["items"])
    month = client.get("/api/transactions", params={"month": "2026-09", "limit": 5}).json()
    assert len(month["items"]) == 5 and all(t["date"].startswith("2026-09") for t in month["items"])


def test_confirm_review_item_creates_reimbursement(client):
    items = client.get(
        "/api/transactions", params={"business_status": "review", "owner": "personal"}
    ).json()["items"]
    target = next(t for t in items if t["amount_cents"] < 0)
    updated = client.patch(
        f"/api/transactions/{target['id']}", json={"business_status": "business"}
    ).json()
    assert updated["business_status"] == "business"
    assert updated["reimbursement_status"] == "owed"
    assert updated["reimbursable_cents"] == -target["amount_cents"]


def test_dismiss_review_item_moves_to_personal_fallback(client):
    item = client.get("/api/business/review").json()[0]
    updated = client.patch(
        f"/api/transactions/{item['id']}", json={"business_status": "personal"}
    ).json()
    assert updated["business_status"] == "personal"
    assert updated["category_group"] != "business"


def test_always_rule_recategorizes_matching_transactions(client):
    page = client.get("/api/transactions", params={"q": "Blue Bottle", "limit": 200}).json()
    assert page["total"] >= 2
    first = page["items"][0]
    client.patch(
        f"/api/transactions/{first['id']}", json={"category_id": "dining", "create_rule": True}
    )
    again = client.get("/api/transactions", params={"q": "Blue Bottle", "limit": 200}).json()
    assert all(t["category_id"] == "dining" for t in again["items"])


def test_budget_get_and_put(client):
    b = client.get("/api/budget").json()
    assert b["month"] == "2026-10" and b["days_remaining"] == 21
    assert any(c["category_id"] == "groceries" for c in b["categories"])
    assert client.put("/api/budget/groceries", json={"monthly_cents": 123_400}).status_code == 200
    b2 = client.get("/api/budget").json()
    assert (
        next(c for c in b2["categories"] if c["category_id"] == "groceries")["target_cents"]
        == 123_400
    )
    assert client.put("/api/budget/paycheck", json={"monthly_cents": 1}).status_code == 422


def test_business_summary_and_export(client):
    s = client.get("/api/business/summary").json()
    lines = {line["line"] for line in s["lines"]}
    assert {"7", "12", "20"} <= lines
    assert s["total_deductions_cents"] > 0 and s["income_cents"] > 0
    r = client.get("/api/business/export.csv")
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("date,description,account")
    reimb = client.get("/api/business/reimbursements").json()
    assert reimb["owed_total_cents"] > 0 and reimb["reimbursed"]


def test_settings_never_expose_key(client):
    s = client.get("/api/settings").json()
    assert "anthropic_api_key" not in s and s["ai_available"] is False
    assert client.put("/api/settings", json={"ai_enabled": True}).status_code == 422
    s2 = client.put("/api/settings", json={"sync_interval_minutes": 1}).json()
    assert s2["sync_interval_minutes"] == 1


def test_sync_now_adds_live_transactions(client):
    run = client.post("/api/sync").json()
    assert run["status"] == "ok" and 1 <= run["new_count"] <= 4


def test_csv_import_is_idempotent(client):
    account = client.get("/api/accounts").json()[0]
    csv_text = "Date,Description,Amount\n2026-10-09,CORNER BODEGA,-12.50\n10/10/2026,REFUND,5.00\n"
    files = {"file": ("s.csv", csv_text, "text/csv")}
    first = client.post("/api/import/csv", data={"account_id": account["id"]}, files=files)
    assert first.json() == {"imported": 2, "skipped": 0}
    second = client.post("/api/import/csv", data={"account_id": account["id"]}, files=files)
    assert second.json() == {"imported": 0, "skipped": 2}
    bad = client.post(
        "/api/import/csv",
        data={"account_id": account["id"]},
        files={"file": ("bad.csv", "when,what\n1,2\n", "text/csv")},
    )
    assert bad.status_code == 400


def test_demo_reset(client):
    client.post("/api/sync")
    run = client.post("/api/demo/reset").json()
    assert run["status"] == "ok" and run["trigger"] == "reset"
