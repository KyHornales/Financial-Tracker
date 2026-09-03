from database import supabase
from services.common import require_period
from services.periods import list_periods


def get_closed_periods(user_id: str) -> list[dict]:
    return list(reversed([period for period in list_periods(user_id) if period["is_closed"]]))


def get_historical_transactions(user_id: str, period_ids: list[str]) -> list[dict]:
    if not period_ids:
        return []
    # Ownership is established for every supplied period before the IN query.
    for period_id in period_ids:
        require_period(user_id, period_id)
    response = (
        supabase.table("transactions")
        .select("*")
        .in_("period_id", period_ids)
        .eq("is_sink", False)
        .execute()
    )
    return response.data or []
