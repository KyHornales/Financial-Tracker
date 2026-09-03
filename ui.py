import datetime as dt

import streamlit as st

from services.calculations import format_iso_week_dates, iso_monday
from services.common import FinancialTrackerError
from services.periods import get_or_create_current_period, list_periods


def initialize_session() -> None:
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("user_name", None)
    st.session_state.setdefault("selected_period_id", None)


def format_currency(value) -> str:
    return f"₱{float(value):,.2f}"


def period_label(period: dict) -> str:
    year = int(period["year"])
    week = int(period["week_number"])
    return f"{year}-W{week:02d} · {format_iso_week_dates(year, week)}"


def choose_period(user_id: str) -> tuple[dict, list[dict]]:
    periods = list_periods(user_id)
    if not periods:
        try:
            periods = [get_or_create_current_period(user_id)]
        except FinancialTrackerError as exc:
            st.error(str(exc))
            st.stop()

    ids = [period["id"] for period in periods]
    selected_id = st.session_state.get("selected_period_id")
    if selected_id not in ids:
        preferred = next((item for item in periods if not item["is_closed"]), periods[0])
        selected_id = preferred["id"]

    selected_id = st.selectbox(
        "Week",
        ids,
        index=ids.index(selected_id),
        format_func=lambda value: period_label(next(p for p in periods if p["id"] == value)),
    )
    st.session_state["selected_period_id"] = selected_id
    return next(period for period in periods if period["id"] == selected_id), periods


def suggested_next_period_date(periods: list[dict]) -> dt.date:
    latest = periods[0]
    latest_start = iso_monday(latest["year"], latest["week_number"])
    earliest_start = latest_start + dt.timedelta(days=7)
    today_iso = dt.date.today().isocalendar()
    current_start = iso_monday(today_iso.year, today_iso.week)
    return dt.date.today() if current_start >= earliest_start else earliest_start
