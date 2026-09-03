import datetime as dt

from database import supabase
from services.calculations import iso_monday
from services.common import FinancialTrackerError, money_payload, require_period


def current_iso_period() -> tuple[int, int]:
    iso = dt.date.today().isocalendar()
    return iso.year, iso.week


def list_periods(user_id: str) -> list[dict]:
    response = (
        supabase.table("financial_periods")
        .select("*")
        .eq("user_id", user_id)
        .order("start_date", desc=True)
        .execute()
    )
    return response.data or []


def get_period(user_id: str, period_id: str) -> dict:
    return require_period(user_id, period_id)


def get_open_period(user_id: str) -> dict | None:
    response = (
        supabase.table("financial_periods")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_closed", False)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_period(user_id: str, year: int, week: int) -> dict:
    start = iso_monday(year, week)
    existing = (
        supabase.table("financial_periods")
        .select("*")
        .eq("user_id", user_id)
        .eq("year", int(year))
        .eq("week_number", int(week))
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    open_period = get_open_period(user_id)
    if open_period:
        raise FinancialTrackerError(
            f"Close {open_period['year']}-W{int(open_period['week_number']):02d} before starting another week."
        )

    latest = (
        supabase.table("financial_periods")
        .select("start_date")
        .eq("user_id", user_id)
        .order("start_date", desc=True)
        .limit(1)
        .execute()
    )
    if latest.data and start <= dt.date.fromisoformat(latest.data[0]["start_date"]):
        raise FinancialTrackerError(
            "New periods must be later than your most recently created period."
        )

    prior = (
        supabase.table("financial_periods")
        .select("id, ending_cash, total_savings")
        .eq("user_id", user_id)
        .eq("is_closed", True)
        .lt("start_date", start.isoformat())
        .order("start_date", desc=True)
        .limit(1)
        .execute()
    )
    cash = prior.data[0]["ending_cash"] if prior.data else 0
    savings = prior.data[0]["total_savings"] if prior.data else 0
    payload = {
        "user_id": user_id,
        "year": int(year),
        "week_number": int(week),
        "start_date": start.isoformat(),
        "starting_cash": money_payload(cash),
        "ending_cash": money_payload(cash),
        "total_savings": money_payload(savings),
        "is_closed": False,
    }
    response = supabase.table("financial_periods").insert(payload).execute()
    new_period = response.data[0]

    # Fixed weekly expenses are recurring by definition, so copy only those
    # categories into the new plan. Flexible budgets remain week-specific.
    if prior.data:
        fixed_budgets = (
            supabase.table("budgets")
            .select("category_group, category_name, category_key, allocated_amount, is_fixed")
            .eq("period_id", prior.data[0]["id"])
            .eq("is_fixed", True)
            .execute()
        )
        if fixed_budgets.data:
            copies = [
                {**item, "period_id": new_period["id"]}
                for item in fixed_budgets.data
            ]
            supabase.table("budgets").insert(copies).execute()
    return new_period


def get_or_create_current_period(user_id: str) -> dict:
    open_period = get_open_period(user_id)
    if open_period:
        return open_period
    year, week = current_iso_period()
    return create_period(user_id, year, week)


def can_set_initial_balances(user_id: str, period_id: str) -> bool:
    period = require_period(user_id, period_id, open_only=True)
    earlier = (
        supabase.table("financial_periods")
        .select("id")
        .eq("user_id", user_id)
        .lt("start_date", period["start_date"])
        .limit(1)
        .execute()
    )
    return not bool(earlier.data)


def set_initial_balances(user_id: str, period_id: str, cash, savings) -> dict:
    if not can_set_initial_balances(user_id, period_id):
        raise FinancialTrackerError("Initial balances can only be set on your first period.")
    cash_value = money_payload(cash)
    savings_value = money_payload(savings)
    if float(cash_value) < 0 or float(savings_value) < 0:
        raise FinancialTrackerError("Initial balances cannot be negative.")
    response = (
        supabase.table("financial_periods")
        .update(
            {
                "starting_cash": cash_value,
                "ending_cash": cash_value,
                "total_savings": savings_value,
            }
        )
        .eq("id", period_id)
        .eq("user_id", user_id)
        .eq("is_closed", False)
        .execute()
    )
    if not response.data:
        raise FinancialTrackerError("The initial balances could not be updated.")
    return response.data[0]


def check_if_closed(user_id: str, period_id: str) -> bool:
    return bool(require_period(user_id, period_id)["is_closed"])
