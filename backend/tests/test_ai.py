import json
from datetime import date
from types import SimpleNamespace

from ledgerpilot.categorize.ai import AICategorizer, build_payload
from ledgerpilot.models import Account, Transaction


class FakeMessages:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.reply


def fake_client(text, stop_reason="end_turn"):
    reply = SimpleNamespace(
        stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)]
    )
    messages = FakeMessages(reply)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


class FakeSession:
    def flush(self):
        pass


def make_txn(owner="self"):
    account = Account(id=7, name="Summit Rewards Visa 4242", owner=owner, balance_cents=-99999)
    t = Transaction(
        id=1,
        date=date(2026, 10, 11),
        description="SQ *BLUE BOTTLE COFFEE",
        merchant="Blue Bottle Coffee",
        amount_cents=-650,
        category_id="uncategorized",
        business_status="personal",
        business_pct=0,
    )
    t.account = account
    return t


def test_payload_excludes_account_details():
    payload = build_payload([make_txn()])
    assert set(payload[0]) == {"id", "date", "description", "merchant", "amount", "paid_from"}
    assert "4242" not in json.dumps(payload) and "99999" not in json.dumps(payload)


def test_apply_sets_category_and_rationale(categories):
    text = json.dumps(
        {
            "results": [
                {
                    "id": 1,
                    "category_id": "dining",
                    "likely_business": False,
                    "rationale": "Coffee shop purchase",
                }
            ]
        }
    )
    client, messages = fake_client(text)
    txn = make_txn()
    updated = AICategorizer(client=client).apply(FakeSession(), [txn], categories, 40)
    assert updated == 1
    assert (txn.category_id, txn.categorized_by, txn.business_status) == (
        "dining",
        "ai",
        "personal",
    )
    assert txn.ai_rationale == "Coffee shop purchase"
    call = messages.calls[0]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default"


def test_likely_business_goes_to_review(categories):
    text = json.dumps(
        {
            "results": [
                {
                    "id": 1,
                    "category_id": "business_meals",
                    "likely_business": True,
                    "rationale": "Client coffee",
                }
            ]
        }
    )
    client, _ = fake_client(text)
    txn = make_txn()
    AICategorizer(client=client).apply(FakeSession(), [txn], categories, 40)
    assert (txn.category_id, txn.business_status) == ("business_meals", "review")


def test_bad_output_and_refusal_leave_item_uncategorized(categories):
    for client, _ in (fake_client("not json"), fake_client("{}", stop_reason="refusal")):
        txn = make_txn()
        assert AICategorizer(client=client).apply(FakeSession(), [txn], categories, 40) == 0
        assert txn.category_id == "uncategorized"


def test_unknown_category_ignored(categories):
    text = json.dumps(
        {
            "results": [
                {"id": 1, "category_id": "yachts", "likely_business": False, "rationale": "?"}
            ]
        }
    )
    client, _ = fake_client(text)
    txn = make_txn()
    assert AICategorizer(client=client).apply(FakeSession(), [txn], categories, 40) == 0
