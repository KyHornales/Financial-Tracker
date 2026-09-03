from database import supabase
from services.common import FinancialTrackerError, clean_label, money, money_payload, require_period

GROUPS = ("Need", "Want", "Savings")


def _sync_budget_transactions(
    period_id: str,
    budget_id: str,
    category_group: str,
    category_name: str,
) -> None:
    supabase.table("transactions").update(
        {
            "category_group": category_group,
            "category_name": category_name,
        }
    ).eq("period_id", period_id).eq("budget_id", budget_id).execute()


def get_budgets(user_id: str, period_id: str) -> list[dict]:
    require_period(user_id, period_id)
    response = (
        supabase.table("budgets")
        .select("*")
        .eq("period_id", period_id)
        .order("category_group")
        .order("category_name")
        .execute()
    )
    return response.data or []


def upsert_budget(
    user_id: str,
    period_id: str,
    category_group: str,
    category_name: str,
    amount,
    is_fixed: bool = False,
) -> dict:
    require_period(user_id, period_id, open_only=True)
    if category_group not in GROUPS:
        raise FinancialTrackerError("Choose Need, Want, or Savings.")
    name = clean_label(category_name, "Category name")
    value = money(amount)
    if value < 0:
        raise FinancialTrackerError("Budget amount cannot be negative.")
    key = name.casefold()
    existing = (
        supabase.table("budgets")
        .select("id")
        .eq("period_id", period_id)
        .eq("category_key", key)
        .limit(1)
        .execute()
    )
    payload = {
        "period_id": period_id,
        "category_group": category_group,
        "category_name": name,
        "category_key": key,
        "allocated_amount": money_payload(value),
        "is_fixed": bool(is_fixed),
    }
    if existing.data:
        budget_id = existing.data[0]["id"]
        response = (
            supabase.table("budgets")
            .update(payload)
            .eq("id", budget_id)
            .eq("period_id", period_id)
            .execute()
        )
        _sync_budget_transactions(period_id, budget_id, category_group, name)
    else:
        response = supabase.table("budgets").insert(payload).execute()
    return response.data[0]


def upsert_budgets_batch(
    user_id: str,
    period_id: str,
    entries: list[dict],
) -> list[dict]:
    require_period(user_id, period_id, open_only=True)
    if not entries:
        raise FinancialTrackerError("Add at least one budget category.")

    validated_entries = []
    category_keys = set()
    for position, entry in enumerate(entries, start=1):
        category_group = entry.get("category_group")
        if category_group not in GROUPS:
            raise FinancialTrackerError(
                f"Budget category {position}: choose Need, Want, or Savings."
            )

        category_name = clean_label(
            entry.get("category_name") or "",
            f"Budget category {position} name",
        )
        category_key = category_name.casefold()
        if category_key in category_keys:
            raise FinancialTrackerError(
                f'"{category_name}" appears more than once. Use each category name once.'
            )
        category_keys.add(category_key)

        amount = money(entry.get("amount", 0))
        if amount < 0:
            raise FinancialTrackerError(
                f"Budget category {position} amount cannot be negative."
            )
        validated_entries.append(
            {
                "category_group": category_group,
                "category_name": category_name,
                "amount": amount,
                "is_fixed": bool(entry.get("is_fixed", False)),
            }
        )

    return [
        upsert_budget(
            user_id,
            period_id,
            entry["category_group"],
            entry["category_name"],
            entry["amount"],
            entry["is_fixed"],
        )
        for entry in validated_entries
    ]


def update_budget(
    user_id: str,
    period_id: str,
    budget_id: str,
    category_group: str,
    category_name: str,
    amount,
    is_fixed: bool = False,
) -> dict:
    require_period(user_id, period_id, open_only=True)
    if category_group not in GROUPS:
        raise FinancialTrackerError("Choose Need, Want, or Savings.")

    name = clean_label(category_name, "Category name")
    value = money(amount)
    if value < 0:
        raise FinancialTrackerError("Budget amount cannot be negative.")

    key = name.casefold()
    duplicate = (
        supabase.table("budgets")
        .select("id")
        .eq("period_id", period_id)
        .eq("category_key", key)
        .neq("id", budget_id)
        .limit(1)
        .execute()
    )
    if duplicate.data:
        raise FinancialTrackerError(
            "Another budget category already uses that name."
        )

    response = (
        supabase.table("budgets")
        .update(
            {
                "category_group": category_group,
                "category_name": name,
                "category_key": key,
                "allocated_amount": money_payload(value),
                "is_fixed": bool(is_fixed),
            }
        )
        .eq("id", budget_id)
        .eq("period_id", period_id)
        .execute()
    )
    if not response.data:
        raise FinancialTrackerError("Budget category not found.")

    _sync_budget_transactions(period_id, budget_id, category_group, name)
    return response.data[0]


def delete_budget(user_id: str, period_id: str, budget_id: str) -> None:
    require_period(user_id, period_id, open_only=True)
    try:
        response = (
            supabase.table("budgets")
            .delete()
            .eq("id", budget_id)
            .eq("period_id", period_id)
            .execute()
        )
    except Exception as exc:
        if "foreign key" in str(exc).lower():
            raise FinancialTrackerError(
                "This category already has transactions and cannot be deleted."
            ) from exc
        raise
    if not response.data:
        raise FinancialTrackerError("Budget category not found.")
