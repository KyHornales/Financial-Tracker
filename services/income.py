from database import supabase
from services.common import FinancialTrackerError, clean_label, money, money_payload, require_period


def log_income(user_id: str, period_id: str, source_name: str, amount) -> dict:
    require_period(user_id, period_id, open_only=True)
    source = clean_label(source_name, "Income source")
    value = money(amount)
    if value <= 0:
        raise FinancialTrackerError("Income must be greater than zero.")
    response = (
        supabase.table("incomes")
        .insert({"period_id": period_id, "source_name": source, "amount": money_payload(value)})
        .execute()
    )
    return response.data[0]


def log_incomes_batch(user_id: str, period_id: str, entries: list[dict]) -> list[dict]:
    require_period(user_id, period_id, open_only=True)
    if not entries:
        raise FinancialTrackerError("Add at least one income entry.")

    payloads = []
    for position, entry in enumerate(entries, start=1):
        source = clean_label(
            entry.get("source_name") or "",
            f"Income {position} source",
        )
        value = money(entry.get("amount", 0))
        if value <= 0:
            raise FinancialTrackerError(
                f"Income {position} must be greater than zero."
            )
        payloads.append(
            {
                "period_id": period_id,
                "source_name": source,
                "amount": money_payload(value),
            }
        )

    response = supabase.table("incomes").insert(payloads).execute()
    return response.data or []


def get_incomes(user_id: str, period_id: str) -> list[dict]:
    require_period(user_id, period_id)
    response = (
        supabase.table("incomes")
        .select("*")
        .eq("period_id", period_id)
        .order("created_at")
        .execute()
    )
    return response.data or []


def get_total_income(user_id: str, period_id: str):
    return sum((money(row["amount"]) for row in get_incomes(user_id, period_id)), money(0))


def update_income(
    user_id: str,
    period_id: str,
    income_id: str,
    source_name: str,
    amount,
) -> dict:
    require_period(user_id, period_id, open_only=True)
    source = clean_label(source_name, "Income source")
    value = money(amount)
    if value <= 0:
        raise FinancialTrackerError("Income must be greater than zero.")

    response = (
        supabase.table("incomes")
        .update(
            {
                "source_name": source,
                "amount": money_payload(value),
            }
        )
        .eq("id", income_id)
        .eq("period_id", period_id)
        .execute()
    )
    if not response.data:
        raise FinancialTrackerError("Income entry not found.")
    return response.data[0]


def delete_income(user_id: str, period_id: str, income_id: str) -> None:
    require_period(user_id, period_id, open_only=True)
    response = (
        supabase.table("incomes")
        .delete()
        .eq("id", income_id)
        .eq("period_id", period_id)
        .execute()
    )
    if not response.data:
        raise FinancialTrackerError("Income entry not found.")
