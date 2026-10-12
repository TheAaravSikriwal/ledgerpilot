from ledgerpilot.categorize.rules import categorize, match_rule
from ledgerpilot.models import Rule


def run(text, owner, amount, categories, rules, **kw):
    return categorize(
        text=text,
        owner=owner,
        amount_cents=amount,
        rules=rules,
        categories=categories,
        mixed_use_pct=40,
        **kw,
    )


def test_user_rule_beats_system_rule(categories, system_rules):
    user_rule = Rule(
        id=999,
        pattern="AMAZON",
        category_id="office_supplies",
        business_status="review",
        business_pct=None,
        account_scope=None,
        priority=0,
        created_by="user",
    )
    rule = match_rule([*system_rules, user_rule], "AMAZON MKTPL*2K4", "self")
    assert rule is user_rule


def test_more_specific_system_rule_wins(categories, system_rules):
    result = run("AMAZON WEB SERVICES AWS.AMAZON.CO", "business", -4210, categories, system_rules)
    assert result.category_id == "software_saas"


def test_business_account_business_category_is_business(categories, system_rules):
    result = run("GITHUB, INC.", "business", -2100, categories, system_rules)
    assert (result.category_id, result.business_status, result.business_pct) == (
        "software_saas",
        "business",
        100,
    )
    assert result.categorized_by == "rule"


def test_personal_account_business_rule_is_review(categories, system_rules):
    result = run("GITHUB, INC.", "self", -2100, categories, system_rules)
    assert (result.category_id, result.business_status) == ("software_saas", "review")


def test_mixed_use_phone_uses_setting_pct(categories, system_rules):
    result = run("VERIZON WIRELESS PAYMENT", "joint", -14218, categories, system_rules)
    assert (result.category_id, result.business_status, result.business_pct) == (
        "phone_internet",
        "business",
        40,
    )


def test_unknown_business_outflow_needs_review(categories, system_rules):
    result = run("MYSTERY VENDOR 123", "business", -5000, categories, system_rules)
    assert (result.category_id, result.business_status) == ("business_other", "review")


def test_unknown_business_inflow_is_revenue(categories, system_rules):
    result = run("ACME LABS ACH PAYMENT", "business", 850000, categories, system_rules)
    assert (result.category_id, result.business_status) == ("business_income", "business")


def test_personal_category_on_business_account_needs_review(categories, system_rules):
    result = run("TARGET 00012345", "business", -4599, categories, system_rules)
    assert (result.category_id, result.business_status) == ("business_other", "review")


def test_no_match_is_uncategorized(categories, system_rules):
    result = run("SQ *CORNER BODEGA", "self", -1250, categories, system_rules)
    assert (result.category_id, result.business_status, result.categorized_by) == (
        "uncategorized",
        "personal",
        "fallback",
    )


def test_scoped_rule_ignored_on_other_scope(categories, system_rules):
    # "PAYROLL" is personal-scoped; on a business account it must not become a paycheck.
    result = run("GUSTO PAYROLL", "business", -100, categories, system_rules)
    assert result.category_id != "paycheck"


def test_source_category_and_hint_override(categories, system_rules):
    result = run(
        "UBER *TRIP",
        "self",
        -2350,
        categories,
        system_rules,
        source_category_id="business_travel",
        hint_status="business",
    )
    assert (result.category_id, result.business_status, result.business_pct) == (
        "business_travel",
        "business",
        100,
    )
    assert result.categorized_by == "source"


def test_patterns_match_at_word_end(categories, system_rules):
    result = run("REI", "self", -8900, categories, system_rules)
    assert result.category_id == "shopping"
