from datetime import datetime, timedelta, timezone

import bcrypt

from database import supabase
from services.common import AuthenticationError, FinancialTrackerError, clean_label

MAX_ATTEMPTS = 5
LOCK_MINUTES = 15


def normalize_name(display_name: str) -> tuple[str, str]:
    clean = clean_label(display_name, "Display name")
    if len(clean) < 2:
        raise FinancialTrackerError("Display name must contain at least two characters.")
    return clean, clean.casefold()


def validate_pin(pin: str) -> str:
    if not isinstance(pin, str) or len(pin) != 4 or not pin.isdigit():
        raise FinancialTrackerError("PIN must contain exactly four digits.")
    return pin


def register_user(display_name: str, pin: str) -> dict:
    clean_name, normalized = normalize_name(display_name)
    valid_pin = validate_pin(pin)
    existing = (
        supabase.table("users")
        .select("id")
        .eq("display_name_normalized", normalized)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise FinancialTrackerError("That display name is already registered.")

    pin_hash = bcrypt.hashpw(valid_pin.encode(), bcrypt.gensalt(rounds=12)).decode()
    try:
        response = (
            supabase.table("users")
            .insert(
                {
                    "display_name": clean_name,
                    "display_name_normalized": normalized,
                    "pin_hash": pin_hash,
                }
            )
            .execute()
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise FinancialTrackerError("That display name is already registered.") from exc
        raise
    return {"id": response.data[0]["id"], "display_name": clean_name}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def authenticate_user(display_name: str, pin: str) -> dict:
    _, normalized = normalize_name(display_name)
    valid_pin = validate_pin(pin)
    try:
        response = (
            supabase.table("users")
            .select(
                "id, display_name, pin_hash, failed_login_attempts, locked_until, theme_primary, theme_secondary, theme_bg, theme_text"
            )
            .eq("display_name_normalized", normalized)
            .limit(1)
            .execute()
        )
    except Exception:
        # Fallback if theme columns don't exist
        response = (
            supabase.table("users")
            .select("id, display_name, pin_hash, failed_login_attempts, locked_until")
            .eq("display_name_normalized", normalized)
            .limit(1)
            .execute()
        )
    # The message deliberately does not reveal whether a name exists.
    if not response.data:
        raise AuthenticationError("Invalid display name or PIN.")

    user = response.data[0]
    now = datetime.now(timezone.utc)
    locked_until = _parse_timestamp(user.get("locked_until"))
    if locked_until and locked_until > now:
        remaining = max(1, int((locked_until - now).total_seconds() // 60) + 1)
        raise AuthenticationError(
            f"Too many attempts. Try again in {remaining} minute(s)."
        )

    if not bcrypt.checkpw(valid_pin.encode(), user["pin_hash"].encode()):
        attempts = int(user.get("failed_login_attempts") or 0) + 1
        update = {"failed_login_attempts": attempts, "locked_until": None}
        if attempts >= MAX_ATTEMPTS:
            update = {
                "failed_login_attempts": 0,
                "locked_until": (now + timedelta(minutes=LOCK_MINUTES)).isoformat(),
            }
        supabase.table("users").update(update).eq("id", user["id"]).execute()
        raise AuthenticationError("Invalid display name or PIN.")

    supabase.table("users").update(
        {"failed_login_attempts": 0, "locked_until": None}
    ).eq("id", user["id"]).execute()
    return {
        "id": user["id"],
        "display_name": user["display_name"],
        "theme_primary": user.get("theme_primary") or "#FF4B4B",
        "theme_secondary": user.get("theme_secondary") or "#E8E8E8",
        "theme_bg": user.get("theme_bg") or "#FFFFFF",
        "theme_text": user.get("theme_text") or "#31333F",
    }


def update_theme(user_id: str, primary: str, secondary: str, bg: str, text: str):
    try:
        supabase.table("users").update(
            {
                "theme_primary": primary,
                "theme_secondary": secondary,
                "theme_bg": bg,
                "theme_text": text,
            }
        ).eq("id", user_id).execute()
    except Exception as exc:
        # If theme columns don't exist, try without secondary
        try:
            supabase.table("users").update(
                {
                    "theme_primary": primary,
                    "theme_bg": bg,
                    "theme_text": text,
                }
            ).eq("id", user_id).execute()
        except Exception:
            raise FinancialTrackerError("Could not save theme to database.") from exc
