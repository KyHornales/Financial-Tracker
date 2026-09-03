import datetime as dt
from decimal import Decimal

from services.common import FinancialTrackerError, money


def iso_monday(year: int, week: int) -> dt.date:
    try:
        return dt.date.fromisocalendar(int(year), int(week), 1)
    except (TypeError, ValueError) as exc:
        raise FinancialTrackerError("Choose a valid ISO year and week.") from exc


def iso_week_dates(year: int, week: int) -> tuple[dt.date, dt.date]:
    start = iso_monday(year, week)
    return start, start + dt.timedelta(days=6)


def format_iso_week_dates(year: int, week: int) -> str:
    start, end = iso_week_dates(year, week)

    if start.year != end.year:
        return (
            f"{start.strftime('%b')} {start.day}, {start.year} – "
            f"{end.strftime('%b')} {end.day}, {end.year}"
        )
    if start.month != end.month:
        return (
            f"{start.strftime('%b')} {start.day} – "
            f"{end.strftime('%b')} {end.day}, {end.year}"
        )
    return f"{start.strftime('%b')} {start.day}–{end.day}, {end.year}"


def summarize(incomes: list[dict], transactions: list[dict]) -> dict:
    income = sum((money(row["amount"]) for row in incomes), Decimal("0.00"))
    active = [row for row in transactions if not row.get("is_sink", False)]
    allocated = sum((money(row["amount"]) for row in active), Decimal("0.00"))
    savings = sum(
        (money(row["amount"]) for row in active if row.get("category_group") == "Savings"),
        Decimal("0.00"),
    )
    expenses = allocated - savings
    return {
        "income": money(income),
        "allocated": money(allocated),
        "expenses": money(expenses),
        "savings_contributions": money(savings),
        "unallocated": money(income - allocated),
    }


def projected_close(period: dict, summary: dict, destination: str) -> dict:
    cash = money(period["starting_cash"])
    savings = money(period["total_savings"]) + money(summary["savings_contributions"])
    surplus = money(summary["unallocated"])
    if surplus < 0:
        raise ValueError("A deficit period cannot be closed.")
    if destination == "Keep as Cash":
        cash += surplus
    elif destination == "Add to Savings":
        savings += surplus
    elif destination != "Piggy Bank":
        raise ValueError("Unknown destination.")
    return {"ending_cash": money(cash), "total_savings": money(savings)}


def fixed_expense_status(budget, actual) -> str:
    planned = money(budget)
    spent = money(actual)
    if spent == 0:
        return "Not logged"
    if spent > planned:
        return "Over plan"
    return "Logged"
