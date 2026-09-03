from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")


class FinancialTrackerError(RuntimeError):
    """An expected, user-facing business-rule failure."""


class AuthenticationError(FinancialTrackerError):
    pass


class AuthorizationError(FinancialTrackerError):
    pass


class ClosedPeriodError(FinancialTrackerError):
    pass


def money(value) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise FinancialTrackerError("Enter a valid monetary amount.") from exc


def money_payload(value) -> str:
    return format(money(value), ".2f")


def require_period(user_id: str, period_id: str, open_only: bool = False) -> dict:
    # Lazy import keeps pure calculation modules testable without database secrets.
    from database import supabase

    query = (
        supabase.table("financial_periods")
        .select("*")
        .eq("id", period_id)
        .eq("user_id", user_id)
        .limit(1)
    )
    response = query.execute()
    if not response.data:
        raise AuthorizationError("That financial period does not belong to this user.")
    period = response.data[0]
    if open_only and period["is_closed"]:
        raise ClosedPeriodError("This financial period is permanently closed.")
    return period


def clean_label(value: str, field_name: str) -> str:
    label = " ".join((value or "").strip().split())
    if not label:
        raise FinancialTrackerError(f"{field_name} is required.")
    if len(label) > 80:
        raise FinancialTrackerError(f"{field_name} must be 80 characters or fewer.")
    return label
