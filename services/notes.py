from database import supabase
from services.common import FinancialTrackerError, clean_label, require_period

NOTE_TYPES = (
    "General",
    "Overspent",
    "Skipped plan",
    "Unexpected expense",
    "Changed priority",
)


def get_notes(user_id: str, period_id: str) -> list[dict]:
    require_period(user_id, period_id)
    response = (
        supabase.table("period_notes")
        .select("*")
        .eq("period_id", period_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def add_note(
    user_id: str,
    period_id: str,
    note_type: str,
    note_text: str,
    next_action: str = "",
    budget_id: str | None = None,
) -> dict:
    # Notes are reflections, so they may also be added after a week is closed.
    require_period(user_id, period_id)
    if note_type not in NOTE_TYPES:
        raise FinancialTrackerError("Choose a valid note type.")
    text = clean_label(note_text, "What happened")
    if len(text) > 1000:
        raise FinancialTrackerError("The note must be 1,000 characters or fewer.")

    category_name = None
    if budget_id:
        response = (
            supabase.table("budgets")
            .select("id, category_name")
            .eq("id", budget_id)
            .eq("period_id", period_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise FinancialTrackerError("Choose a category from this week.")
        category_name = response.data[0]["category_name"]

    action = " ".join((next_action or "").strip().split()) or None
    if action and len(action) > 1000:
        raise FinancialTrackerError("The next step must be 1,000 characters or fewer.")
    payload = {
        "period_id": period_id,
        "budget_id": budget_id,
        "note_type": note_type,
        "category_name": category_name,
        "note_text": text,
        "next_action": action,
    }
    response = supabase.table("period_notes").insert(payload).execute()
    return response.data[0]


def delete_note(user_id: str, period_id: str, note_id: str) -> None:
    require_period(user_id, period_id)
    response = (
        supabase.table("period_notes")
        .delete()
        .eq("id", note_id)
        .eq("period_id", period_id)
        .execute()
    )
    if not response.data:
        raise FinancialTrackerError("Note not found.")
