"""Reference data: categories (with Form 1120-S line mapping), system rules, budget targets.

Seeding is idempotent: existing rows are updated in place, user-created rules are never touched.
"""

from sqlalchemy.orm import Session

from .models import BudgetTarget, Category, Rule

# Form 1120-S (2025) deduction lines used by LedgerPilot.
IRS_LINES: dict[str, str] = {
    "7": "Compensation of officers",
    "8": "Salaries and wages",
    "11": "Rents",
    "12": "Taxes and licenses",
    "16": "Advertising",
    "17": "Pension, profit-sharing, etc., plans",
    "18": "Employee benefit programs",
    "20": "Other deductions",
}

# (id, name, group, irs_line, irs_detail, deductible_pct, personal_fallback_id)
CATEGORIES: list[tuple[str, str, str, str | None, str | None, int, str | None]] = [
    ("paycheck", "Paycheck", "income", None, None, 100, None),
    ("business_income", "Client revenue", "income", None, None, 100, None),
    ("interest", "Interest & dividends", "income", None, None, 100, None),
    ("other_income", "Other income", "income", None, None, 100, None),
    ("housing", "Rent & housing", "essential", None, None, 100, None),
    ("utilities", "Utilities", "essential", None, None, 100, None),
    ("phone_internet", "Phone & internet", "essential", "20", "Phone & internet", 100, None),
    ("groceries", "Groceries", "essential", None, None, 100, None),
    ("transportation", "Gas & transit", "essential", None, None, 100, None),
    ("insurance", "Insurance", "essential", None, None, 100, None),
    ("health", "Health & medical", "essential", None, None, 100, None),
    ("dining", "Dining out", "discretionary", None, None, 100, None),
    ("shopping", "Shopping", "discretionary", None, None, 100, None),
    ("entertainment", "Entertainment", "discretionary", None, None, 100, None),
    ("subscriptions", "Streaming & apps", "discretionary", None, None, 100, None),
    ("travel", "Travel", "discretionary", None, None, 100, None),
    ("personal_care", "Personal care & fitness", "discretionary", None, None, 100, None),
    ("gifts", "Gifts & giving", "discretionary", None, None, 100, None),
    ("transfer", "Transfer", "transfer", None, None, 100, None),
    ("card_payment", "Credit card payment", "transfer", None, None, 100, None),
    ("savings_transfer", "Savings & investing", "transfer", None, None, 100, None),
    ("owner_distribution", "Owner distribution", "transfer", None, None, 100, None),
    (
        "accountable_plan_reimbursement",
        "Accountable plan reimbursement",
        "transfer",
        None,
        None,
        100,
        None,
    ),
    ("estimated_taxes", "Estimated taxes", "taxes", None, None, 100, None),
    ("officer_comp", "Officer compensation", "business", "7", None, 100, "shopping"),
    ("salaries_wages", "Salaries & wages", "business", "8", None, 100, "shopping"),
    ("rent_office", "Coworking & office rent", "business", "11", None, 100, "shopping"),
    ("taxes_licenses", "Taxes & licenses", "business", "12", None, 100, "shopping"),
    ("advertising", "Advertising", "business", "16", None, 100, "shopping"),
    ("retirement_plan", "Retirement plan (employer)", "business", "17", None, 100, "shopping"),
    ("employee_benefits", "Employee benefits", "business", "18", None, 100, "shopping"),
    ("software_saas", "Software & SaaS", "business", "20", "Software & SaaS", 100, "subscriptions"),
    ("office_supplies", "Office supplies", "business", "20", "Office supplies", 100, "shopping"),
    (
        "professional_fees",
        "Professional fees",
        "business",
        "20",
        "Legal & professional fees",
        100,
        "shopping",
    ),
    ("business_travel", "Business travel", "business", "20", "Travel", 100, "travel"),
    ("business_meals", "Business meals (50%)", "business", "20", "Meals (50%)", 50, "dining"),
    ("contract_labor", "Contract labor", "business", "20", "Contract labor", 100, "shopping"),
    ("business_insurance", "Business insurance", "business", "20", "Insurance", 100, "insurance"),
    ("bank_fees", "Bank & payment fees", "business", "20", "Bank & payment fees", 100, "shopping"),
    (
        "education",
        "Education & training",
        "business",
        "20",
        "Education & training",
        100,
        "shopping",
    ),
    ("business_other", "Other business expense", "business", "20", "Other", 100, "shopping"),
    ("uncategorized", "Uncategorized", "other", None, None, 100, None),
]

# (pattern, category_id, business_status, business_pct, account_scope, priority)
SYSTEM_RULES: list[tuple[str, str, str | None, int | None, str | None, int]] = [
    # Income
    ("PAYROLL", "paycheck", None, None, "personal", 10),
    ("DIRECT DEP", "paycheck", None, None, "personal", 10),
    ("INTEREST PAYMENT", "interest", None, None, None, 10),
    # Housing & utilities
    ("AVALONBAY", "housing", None, None, "personal", 10),
    ("EVERSOURCE", "utilities", None, None, None, 10),
    ("NATIONAL GRID", "utilities", None, None, None, 10),
    # Mixed-use: business share comes from the phone_internet_business_pct setting.
    ("VERIZON", "phone_internet", "business", None, "personal", 10),
    ("XFINITY", "phone_internet", "business", None, "personal", 10),
    # Groceries
    ("WHOLE FOODS", "groceries", None, None, None, 10),
    ("TRADER JOE", "groceries", None, None, None, 10),
    ("STAR MARKET", "groceries", None, None, None, 10),
    ("COSTCO", "groceries", None, None, None, 10),
    # Dining
    ("STARBUCKS", "dining", None, None, None, 10),
    ("SWEETGREEN", "dining", None, None, None, 10),
    ("CHIPOTLE", "dining", None, None, None, 10),
    ("DOORDASH", "dining", None, None, None, 10),
    ("TATTE", "dining", None, None, None, 10),
    ("OLEANA", "dining", None, None, None, 10),
    # Transportation
    ("SHELL OIL", "transportation", None, None, None, 10),
    ("MBTA", "transportation", None, None, None, 10),
    ("UBER", "transportation", None, None, None, 5),
    ("LYFT", "transportation", None, None, None, 10),
    # Insurance & health
    ("GEICO", "insurance", None, None, "personal", 10),
    ("LEMONADE", "insurance", None, None, "personal", 10),
    ("CVS", "health", None, None, None, 10),
    ("ONE MEDICAL", "health", None, None, None, 10),
    # Shopping
    ("AMAZON", "shopping", None, None, None, 5),
    ("TARGET", "shopping", None, None, None, 10),
    ("REI ", "shopping", None, None, None, 10),
    ("UNIQLO", "shopping", None, None, None, 10),
    # Entertainment & subscriptions
    ("AMC ", "entertainment", None, None, None, 10),
    ("TICKETMASTER", "entertainment", None, None, None, 10),
    ("NETFLIX", "subscriptions", None, None, None, 10),
    ("SPOTIFY", "subscriptions", None, None, None, 10),
    ("NYTIMES", "subscriptions", None, None, None, 10),
    ("PLANET FITNESS", "personal_care", None, None, None, 10),
    ("SEPHORA", "personal_care", None, None, None, 10),
    ("GOFUNDME", "gifts", None, None, None, 10),
    # Travel: airlines/hotels on personal cards are often business trips → review.
    ("JETBLUE", "travel", None, None, None, 10),
    ("AIRBNB", "travel", None, None, None, 10),
    ("DELTA AIR", "business_travel", "review", None, None, 20),
    ("UNITED AIRLINES", "business_travel", "review", None, None, 20),
    ("MARRIOTT", "business_travel", "review", None, None, 20),
    # Business tools — likely business wherever they appear.
    ("GITHUB", "software_saas", "review", None, None, 20),
    ("ADOBE", "software_saas", "review", None, None, 20),
    ("ZOOM.US", "software_saas", "review", None, None, 20),
    ("NOTION", "software_saas", "review", None, None, 20),
    ("FIGMA", "software_saas", "review", None, None, 20),
    ("GOOGLE *WORKSPACE", "software_saas", "review", None, None, 25),
    ("AMAZON WEB SERVICES", "software_saas", "review", None, None, 25),
    ("ANTHROPIC", "software_saas", "review", None, None, 20),
    ("STAPLES", "office_supplies", "review", None, None, 20),
    ("WEWORK", "rent_office", "review", None, None, 20),
    ("LINKEDIN ADS", "advertising", "review", None, None, 20),
    ("GOOGLE ADS", "advertising", "review", None, None, 20),
    ("COURSERA", "education", "review", None, None, 20),
    ("UPWORK", "contract_labor", "review", None, None, 20),
    ("HISCOX", "business_insurance", "review", None, None, 20),
    ("STRIPE FEE", "bank_fees", "review", None, None, 20),
    ("SERVICE FEE", "bank_fees", None, None, "business", 20),
    (" CPA ", "professional_fees", "review", None, None, 15),
    # S-Corp payroll & owner flows (business accounts only)
    ("GUSTO WAGES", "officer_comp", "business", None, "business", 30),
    ("GUSTO TAX", "taxes_licenses", "business", None, "business", 30),
    ("SECRETARY OF THE COMMONWEALTH", "taxes_licenses", "business", None, "business", 30),
    ("SOLO 401K", "retirement_plan", "business", None, "business", 30),
    # Taxes
    ("IRS USATAXPYMT", "estimated_taxes", None, None, "personal", 30),
    ("MA DOR", "estimated_taxes", None, None, "personal", 30),
]

BUDGET_TARGETS_CENTS: dict[str, int] = {
    "housing": 3_200_00,
    "utilities": 260_00,
    "phone_internet": 160_00,
    "groceries": 1_100_00,
    "transportation": 320_00,
    "insurance": 180_00,
    "health": 120_00,
    "dining": 650_00,
    "shopping": 750_00,
    "entertainment": 180_00,
    "subscriptions": 60_00,
    "travel": 450_00,
    "personal_care": 120_00,
    "gifts": 150_00,
}


def seed_reference_data(session: Session) -> None:
    for order, (cid, name, group, line, detail, ded_pct, fallback) in enumerate(CATEGORIES):
        cat = session.get(Category, cid) or Category(id=cid)
        cat.name, cat.group, cat.irs_line, cat.irs_detail = name, group, line, detail
        cat.deductible_pct, cat.personal_fallback_id, cat.sort_order = ded_pct, fallback, order
        session.merge(cat)
    session.flush()

    existing = {r.pattern: r for r in session.query(Rule).filter(Rule.created_by == "system")}
    wanted = {spec[0] for spec in SYSTEM_RULES}
    for pattern, rule in existing.items():
        if pattern not in wanted:
            session.delete(rule)
    for pattern, cid, status, pct, scope, priority in SYSTEM_RULES:
        rule = existing.get(pattern) or Rule(pattern=pattern, created_by="system")
        rule.category_id, rule.business_status, rule.business_pct = cid, status, pct
        rule.account_scope, rule.priority = scope, priority
        session.add(rule)

    for cid, cents in BUDGET_TARGETS_CENTS.items():
        if session.get(BudgetTarget, cid) is None:
            session.add(BudgetTarget(category_id=cid, monthly_cents=cents))
    session.commit()
