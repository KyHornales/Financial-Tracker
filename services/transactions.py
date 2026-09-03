import datetime as dt

from database import supabase
from services.calculations import summarize
from services.common import FinancialTrackerError, clean_label, money, money_payload, require_period
from services.income import get_incomes


def get_transactions(user_id: str, period_id: str, include_sinks: bool = False) -> list[dict]:
    require_period(user_id, period_id)
    query = supabase.table("transactions").select("*").eq("period_id", period_id)
    if not include_sinks:
        query = query.eq("is_sink", False)
    response = (
        query.order("transaction_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def log_transaction(
    user_id: str,
    period_id: str,
    amount,
    transaction_date,
    budget_id: str | None = None,
    unbudgeted_category: str | None = None,
) -> dict:
    return log_transactions_batch(
        user_id,
        period_id,
        [
            {
                "amount": amount,
                "transaction_date": transaction_date,
                "budget_id": budget_id,
                "unbudgeted_category": unbudgeted_category,
            }
        ],
    )[0]


def log_transactions_batch(
    user_id: str, period_id: str, entries: list[dict]
) -> list[dict]:
    """Validate and insert several transactions in one atomic request."""
    period = require_period(user_id, period_id, open_only=True)
    if not entries:
        raise FinancialTrackerError("Add at least one transaction.")
    if len(entries) > 20:
        raise FinancialTrackerError("You can add up to 20 transactions at once.")

    period_start = dt.date.fromisoformat(period["start_date"])
    period_end = period_start + dt.timedelta(days=6)

    requested_budget_ids = {
        entry.get("budget_id") for entry in entries if entry.get("budget_id")
    }
    budgets_by_id = {}
    if requested_budget_ids:
        budget_rows = (
            supabase.table("budgets")
            .select("id, category_group, category_name")
            .eq("period_id", period_id)
            .in_("id", list(requested_budget_ids))
            .execute()
        )
        budgets_by_id = {row["id"]: row for row in (budget_rows.data or [])}
        if set(budgets_by_id) != requested_budget_ids:
            raise FinancialTrackerError("One of the selected budget categories is invalid.")

    payloads = []
    for position, entry in enumerate(entries, start=1):
        raw_date = entry.get("transaction_date")
        if raw_date is None:
            raise FinancialTrackerError(f"Choose a date for transaction {position}.")
        try:
            transaction_date = (
                raw_date.date()
                if isinstance(raw_date, dt.datetime)
                else raw_date
                if isinstance(raw_date, dt.date)
                else dt.date.fromisoformat(str(raw_date))
            )
        except (TypeError, ValueError) as exc:
            raise FinancialTrackerError(
                f"Transaction {position} has an invalid date."
            ) from exc
        if not period_start <= transaction_date <= period_end:
            raise FinancialTrackerError(
                f"Transaction {position} must be dated from "
                f"{period_start.strftime('%m-%d-%Y')} through "
                f"{period_end.strftime('%m-%d-%Y')}."
            )

        value = money(entry.get("amount"))
        if value <= 0:
            raise FinancialTrackerError(
                f"Transaction {position} must have an amount greater than zero."
            )

        budget_id = entry.get("budget_id")
        if budget_id:
            selected = budgets_by_id[budget_id]
            payloads.append(
                {
                    "period_id": period_id,
                    "budget_id": selected["id"],
                    "category_group": selected["category_group"],
                    "category_name": selected["category_name"],
                    "amount": money_payload(value),
                    "transaction_date": transaction_date.isoformat(),
                    "is_sink": False,
                }
            )
        else:
            name = clean_label(
                entry.get("unbudgeted_category") or "",
                f"Transaction {position} category",
            )
            payloads.append(
                {
                    "period_id": period_id,
                    "budget_id": None,
                    "category_group": "Unbudgeted",
                    "category_name": name,
                    "amount": money_payload(value),
                    "transaction_date": transaction_date.isoformat(),
                    "is_sink": False,
                }
            )

    response = supabase.table("transactions").insert(payloads).execute()
    return response.data or []


def delete_transaction(user_id: str, period_id: str, transaction_id: str) -> None:
    require_period(user_id, period_id, open_only=True)
    response = (
        supabase.table("transactions")
        .delete()
        .eq("id", transaction_id)
        .eq("period_id", period_id)
        .eq("is_sink", False)
        .execute()
    )
    if not response.data:
        raise FinancialTrackerError("Transaction not found.")


def get_period_summary(user_id: str, period_id: str) -> dict:
    incomes = get_incomes(user_id, period_id)
    transactions = get_transactions(user_id, period_id)
    return summarize(incomes, transactions)


def calculate_unallocated(user_id: str, period_id: str):
    return get_period_summary(user_id, period_id)["unallocated"]


def get_budget_performance(user_id: str, period_id: str) -> list[dict]:
    require_period(user_id, period_id)
    budgets = (
        supabase.table("budgets")
        .select("id, category_group, category_name, allocated_amount, is_fixed")
        .eq("period_id", period_id)
        .order("category_group")
        .order("category_name")
        .execute()
        .data
        or []
    )
    transactions = get_transactions(user_id, period_id)
    actual_by_budget = {}
    for row in transactions:
        if row.get("budget_id"):
            actual_by_budget[row["budget_id"]] = actual_by_budget.get(row["budget_id"], money(0)) + money(row["amount"])
    result = []
    for budget in budgets:
        allocated = money(budget["allocated_amount"])
        actual = money(actual_by_budget.get(budget["id"], 0))
        result.append(
            {
                "Group": budget["category_group"],
                "Category": budget["category_name"],
                "Type": "Fixed" if budget.get("is_fixed") else "Flexible",
                "Budget": float(allocated),
                "Actual": float(actual),
                "Remaining": float(allocated - actual),
            }
        )
    return result


def route_surplus_and_close(
    user_id: str, period_id: str, destination: str
) -> dict:
    require_period(user_id, period_id, open_only=True)
    response = supabase.rpc(
        "close_financial_period",
        {
            "p_user_id": user_id,
            "p_period_id": period_id,
            "p_destination": destination,
        },
    ).execute()
    if not response.data:
        raise FinancialTrackerError("The period could not be closed.")
    return response.data[0]
