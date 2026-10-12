from datetime import date

from ledgerpilot.business import (
    allocate_reimbursement,
    deductible_cents,
    deduction_line,
    reimbursable_cents,
)


def test_meals_are_50_percent_deductible(categories):
    meals = categories["business_meals"]
    assert deductible_cents(-18000, "business", 100, meals) == 9000


def test_mixed_use_phone_deduction_and_reimbursement(categories):
    phone = categories["phone_internet"]
    assert deductible_cents(-10000, "business", 40, phone) == 4000
    assert reimbursable_cents(-10000, "joint", "business", 40) == 4000


def test_meal_reimbursement_is_full_business_share(categories):
    # The S-Corp reimburses 100% of the meal but only deducts 50%.
    assert reimbursable_cents(-18000, "self", "business", 100) == 18000


def test_refund_reduces_deduction(categories):
    software = categories["software_saas"]
    assert deductible_cents(2100, "business", 100, software) == -2100


def test_review_and_personal_items_are_not_deductible(categories):
    software = categories["software_saas"]
    assert deductible_cents(-2100, "review", 100, software) == 0
    assert deductible_cents(-2100, "personal", 0, software) == 0


def test_business_account_items_are_never_reimbursable():
    assert reimbursable_cents(-2100, "business", "business", 100) == 0


def test_revenue_and_transfers_have_no_deduction_line(categories):
    assert deduction_line(categories["business_income"]) is None
    assert deduction_line(categories["owner_distribution"]) is None
    assert deductible_cents(850000, "business", 100, categories["business_income"]) == 0


def test_deduction_lines(categories):
    assert deduction_line(categories["officer_comp"]) == ("7", "Officer compensation")
    assert deduction_line(categories["software_saas"]) == ("20", "Software & SaaS")
    # Personal-looking category confirmed as business lands in "Other deductions".
    assert deduction_line(categories["shopping"]) == ("20", "Other")


def test_allocation_is_fifo_and_exact():
    owed = [
        (1, date(2026, 9, 2), 2100),
        (2, date(2026, 9, 10), 5999),
        (3, date(2026, 9, 28), 1599),
        (4, date(2026, 10, 2), 1000),  # after the September batch
    ]
    assert allocate_reimbursement(2100 + 5999 + 1599, date(2026, 10, 3), owed) == [1, 2, 3]


def test_allocation_stops_at_first_item_that_does_not_fit():
    owed = [(1, date(2026, 9, 2), 5000), (2, date(2026, 9, 3), 9000), (3, date(2026, 9, 4), 100)]
    assert allocate_reimbursement(5200, date(2026, 10, 3), owed) == [1]


def test_allocation_ignores_items_after_transfer_date():
    owed = [(1, date(2026, 10, 5), 1000)]
    assert allocate_reimbursement(1000, date(2026, 10, 3), owed) == []


def test_allocation_tolerates_one_cent_rounding():
    owed = [(1, date(2026, 9, 2), 5687), (2, date(2026, 9, 9), 3600)]
    assert allocate_reimbursement(9286, date(2026, 10, 3), owed) == [1, 2]
