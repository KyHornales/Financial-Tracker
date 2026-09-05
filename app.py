import datetime as dt

import pandas as pd
import streamlit as st

from services.analytics import get_closed_periods, get_historical_transactions
from services.auth import authenticate_user, register_user, update_theme
from services.budgets import (
    GROUPS,
    delete_budget,
    get_budgets,
    update_budget,
    upsert_budgets_batch,
)
from services.calculations import (
    fixed_expense_status,
    format_iso_week_dates,
    projected_close,
)
from services.common import AuthenticationError, FinancialTrackerError
from services.income import delete_income, get_incomes, log_incomes_batch, update_income
from services.notes import NOTE_TYPES, add_note, delete_note, get_notes
from services.periods import (
    can_set_initial_balances,
    create_period,
    set_initial_balances,
)
from services.transactions import (
    delete_transaction,
    get_budget_performance,
    get_period_summary,
    get_transactions,
    log_transactions_batch,
    route_surplus_and_close,
)
from ui import (
    choose_period,
    format_currency,
    initialize_session,
    suggested_next_period_date,
)

st.set_page_config(
    page_title="My Money Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)
initialize_session()

st.markdown(
    f"""
    <style>
    /* 1. Global App Colors */
    .stApp {{
        background-color: {st.session_state.get("theme_bg", "#FFFFFF")};
    }}
    
    /* Force text elements to use the chosen text color */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .week-status-label {{
        color: {st.session_state.get("theme_text", "#31333F")} !important;
    }}

    /* 2. Your existing layout */
    .block-container {{max-width: 1380px; padding-top: 2rem; padding-bottom: 4rem;}}
    
    /* 3. Buttons and dashboard tabs use the primary color */
    div.stButton > button {{
        width: 100%;
        height: 3.25rem;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-weight: 600;
        color: white !important;
        border-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
        background-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
    }}

    div.stButton > button:hover,
    div.stButton > button[kind="primary"]:hover {{
        background-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
        filter: brightness(0.9);
    }}

    /* Target primary buttons (like 'Save' or 'Log in') */
    div.stButton > button[kind="primary"] {{
        background-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
        color: white !important; /* Keep primary text white for contrast */
        border: none;
    }}

    button[data-baseweb="tab"] {{
        color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
        border-bottom-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
    }}

    /* 4. Dashboard table styling: primary headers, secondary values */
    /* Target all table elements */
    table {{
        background-color: {st.session_state.get("theme_bg", "#FFFFFF")} !important;
        width: 100% !important;
    }}
    
    /* Style table headers */
    table thead {{
        background-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
    }}
    
    table thead th {{
        background-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
        color: white !important;
        font-weight: bold !important;
        padding: 10px !important;
        border-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
    }}

    /* Streamlit's dataframe grid uses ARIA roles instead of HTML table cells. */
    [data-testid="stDataFrame"] [role="columnheader"] {{
        background-color: {st.session_state.get("theme_primary", "#FF4B4B")} !important;
        color: white !important;
    }}
    [data-testid="stDataFrame"] [role="gridcell"] {{
        background-color: {st.session_state.get("theme_secondary", "#E8E8E8")} !important;
        color: {st.session_state.get("theme_text", "#31333F")} !important;
    }}
    
    /* Style table body */
    table tbody {{
        background-color: {st.session_state.get("theme_secondary", "#E8E8E8")} !important;
    }}
    
    table tbody tr {{
        background-color: {st.session_state.get("theme_secondary", "#E8E8E8")} !important;
    }}
    
    table tbody td {{
        color: {st.session_state.get("theme_text", "#31333F")} !important;
        background-color: {st.session_state.get("theme_secondary", "#E8E8E8")} !important;
        padding: 10px !important;
        border-color: rgba(128,128,128,.15) !important;
    }}
    
    /* Alternate row colors for better readability */
    table tbody tr:nth-child(odd) td {{
        background-color: {st.session_state.get("theme_secondary", "#E8E8E8")} !important;
    }}
    
    table tbody tr:hover td {{
        background-color: {st.session_state.get("theme_secondary", "#E8E8E8")} !important;
        filter: brightness(0.9);
    }}

    /* 5. Metrics */
    [data-testid="stMetric"] {{
        border: 1px solid rgba(128,128,128,.22); 
        border-radius: .8rem; 
        padding: .85rem;
        background-color: {st.session_state.get("theme_primary", "#FF4B4B")};
    }}
    [data-testid="stMetricValue"] {{
        white-space: nowrap;
        overflow: visible;
        color: {st.session_state.get("theme_text", "#31333F")};
    }}
    [data-testid="stMetricLabel"] {{
        color: {st.session_state.get("theme_text", "#31333F")};
    }}
    
    /* 6. Status boxes */
    .week-status-label {{
        font-size: .875rem;
        margin-bottom: .42rem;
    }}
    .week-status-box {{
        min-height: 2.5rem;
        padding: 0 .8rem;
        border: 1px solid rgba(128,128,128,.35);
        border-radius: .5rem;
        display: flex;
        align-items: center;
        gap: .55rem;
        font-weight: 600;
        background: rgba(128,128,128,.04);
    }}
    .week-status-box.open {{border-color: rgba(35,170,90,.65);}}
    .week-status-box.closed {{border-color: rgba(220,70,70,.65);}}
    .week-status-dot.open {{color: rgb(35,170,90);}}
    .week-status-dot.closed {{color: rgb(220,70,70);}}
    </style>
    """,
    unsafe_allow_html=True,
)


def render_themed_dataframe(dataframe: pd.DataFrame, **kwargs) -> None:
    primary = st.session_state.get("theme_primary", "#FF4B4B")
    body_color = st.session_state.get("theme_secondary", "#E8E8E8")
    text = st.session_state.get("theme_text", "#31333F")
    column_config = kwargs.pop("column_config", {}) or {}
    hide_index = kwargs.pop("hide_index", False)
    kwargs.pop("use_container_width", None)

    labels = {}
    for column, config in column_config.items():
        if isinstance(config, str):
            labels[column] = config
        else:
            labels[column] = getattr(config, "label", column)
    display_dataframe = dataframe.rename(columns=labels)
    currency_columns = {
        column: "₱{:,.2f}"
        for column in display_dataframe.select_dtypes(include="number").columns
    }

    styled = (
        display_dataframe.style.set_properties(
            **{"color": text, "background-color": body_color}
        )
        .format(currency_columns)
        .set_table_styles(
            [
                {
                    "selector": "thead th",
                    "props": [
                        ("background-color", primary),
                        ("color", "white"),
                        ("font-weight", "bold"),
                    ],
                }
            ]
        )
    )
    if hide_index:
        styled = styled.hide(axis="index")
    st.table(styled)


def save_current_theme(user_id: str) -> None:
    update_theme(
        user_id,
        st.session_state.get("theme_primary", "#FF4B4B"),
        st.session_state.get("theme_secondary", "#E8E8E8"),
        st.session_state.get("theme_bg", "#FFFFFF"),
        st.session_state.get("theme_text", "#31333F"),
    )


def logout() -> None:
    current_user_id = st.session_state.get("user_id")
    if current_user_id:
        save_current_theme(current_user_id)
    st.session_state["user_id"] = None
    st.session_state["user_name"] = None
    st.session_state["selected_period_id"] = None


def show_login() -> None:
    st.title("My Money Dashboard")
    st.write("A simple weekly view of where your money came from and where it went.")
    login_tab, register_tab = st.tabs(["Log in", "Create profile"])

    with login_tab:
        with st.form("login_form"):
            name = st.text_input("Your name")
            pin = st.text_input("4-digit PIN", type="password", max_chars=4)
            submitted = st.form_submit_button("Open my dashboard", type="primary")
        if submitted:
            try:
                user = authenticate_user(name, pin)
                st.session_state["user_id"] = user["id"]
                st.session_state["user_name"] = user["display_name"]
                st.session_state["theme_primary"] = user.get("theme_primary", "#FF4B4B")
                st.session_state["theme_secondary"] = user.get(
                    "theme_secondary", "#E8E8E8"
                )
                st.session_state["theme_bg"] = user.get("theme_bg", "#FFFFFF")
                st.session_state["theme_text"] = user.get("theme_text", "#31333F")
                st.rerun()
            except (AuthenticationError, FinancialTrackerError) as exc:
                st.error(str(exc))
            except Exception as e:
                st.error(f"The dashboard is unavailable right now. Error: {str(e)}")

    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Your name", key="new_name")
            pin = st.text_input("Choose a 4-digit PIN", type="password", max_chars=4)
            confirm = st.text_input("Enter the PIN again", type="password", max_chars=4)
            submitted = st.form_submit_button("Create my profile", type="primary")
        if submitted:
            if pin != confirm:
                st.error("The two PINs do not match.")
            else:
                try:
                    user = register_user(name, pin)
                    st.session_state["user_id"] = user["id"]
                    st.session_state["user_name"] = user["display_name"]
                    st.rerun()
                except FinancialTrackerError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error(
                        "The profile could not be created. Please try again later."
                    )


@st.dialog("Customize Theme Colors", width="small")
def theme_dialog() -> None:
    st.write("Personalize how your dashboard looks.")

    new_primary = st.color_picker(
        "Primary Color (buttons & table headers)",
        st.session_state.get("theme_primary", "#FF4B4B"),
    )
    new_secondary = st.color_picker(
        "Secondary Color (table background)",
        st.session_state.get("theme_secondary", "#E8E8E8"),
    )
    new_bg = st.color_picker(
        "Background Color", st.session_state.get("theme_bg", "#FFFFFF")
    )
    new_text = st.color_picker(
        "Text Color", st.session_state.get("theme_text", "#31333F")
    )

    if st.button("Apply & Save", type="primary"):
        try:
            # 1. Save to database permanently
            update_theme(user_id, new_primary, new_secondary, new_bg, new_text)

            # 2. Update current active session
            st.session_state["theme_primary"] = new_primary
            st.session_state["theme_secondary"] = new_secondary
            st.session_state["theme_bg"] = new_bg
            st.session_state["theme_text"] = new_text

            # 3. Reload screen
            st.rerun()
        except Exception:
            st.error("Could not save theme. Please try again.")


if not st.session_state.get("user_id"):
    show_login()
    st.stop()

user_id = st.session_state["user_id"]
user_name = st.session_state["user_name"]

title_col, theme_col, logout_col = st.columns([5, 1, 1])
with title_col:
    st.title(f"Hello, {user_name}")
    st.caption("Here is the complete story of your money for the week.")
with theme_col:
    if st.button("Customize Theme", use_container_width=True):
        theme_dialog()
with logout_col:
    if st.button("Log out", use_container_width=True):
        try:
            logout()
            st.rerun()
        except FinancialTrackerError as exc:
            st.error(str(exc))

period_col, state_col = st.columns(2)
with period_col:
    period, periods = choose_period(user_id)
with state_col:
    status_text = "Closed" if period["is_closed"] else "Open"
    status_class = "closed" if period["is_closed"] else "open"
    st.markdown(
        f"""
        <div class="week-status-label">Week Status</div>
        <div class="week-status-box {status_class}">
            <span class="week-status-dot {status_class}">●</span>
            <span>{status_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

period_id = period["id"]
is_closed = bool(period["is_closed"])
period_start = dt.date.fromisoformat(period["start_date"])
period_end = period_start + dt.timedelta(days=6)
incomes = get_incomes(user_id, period_id)
budgets = get_budgets(user_id, period_id)
transactions = get_transactions(user_id, period_id)
notes = get_notes(user_id, period_id)
summary = get_period_summary(user_id, period_id)
performance = get_budget_performance(user_id, period_id)
needs_reflection = any(item["Actual"] > item["Budget"] for item in performance) or any(
    item["category_group"] == "Unbudgeted" for item in transactions
)


@st.dialog("Manage income", width="large")
def income_dialog() -> None:
    st.write("Record money received during this week.")
    form_version = st.session_state.get("income_form_version", 0)
    entry_count = int(
        st.number_input(
            "How many income entries are you adding?",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key=f"income_entry_count_{form_version}",
        )
    )

    entries = []
    for index in range(entry_count):
        with st.container(border=True):
            st.markdown(f"**Income {index + 1}**")
            source_col, amount_col = st.columns([2, 1])
            with source_col:
                source = st.text_input(
                    "Where did the money come from?",
                    placeholder="Allowance, salary, freelance work…",
                    key=f"income_source_{form_version}_{index}",
                )
            with amount_col:
                amount = st.number_input(
                    "How much?",
                    min_value=0.0,
                    step=100.0,
                    format="%.2f",
                    key=f"income_amount_{form_version}_{index}",
                )
            entries.append({"source_name": source, "amount": amount})

    entry_word = "entry" if entry_count == 1 else "entries"
    if st.button(f"Save {entry_count} income {entry_word}", type="primary"):
        try:
            log_incomes_batch(user_id, period_id, entries)
            st.session_state["income_form_version"] = form_version + 1
            st.rerun()
        except FinancialTrackerError as exc:
            st.error(str(exc))

    if incomes:
        st.divider()
        labels = {
            item["id"]: f"{item['source_name']} — {format_currency(item['amount'])}"
            for item in incomes
        }

        st.caption("Select an income entry to edit.")
        selected_income_id = st.pills(
            "Income entry to edit",
            list(labels),
            format_func=labels.get,
            selection_mode="single",
            key="income_to_edit",
        )
        if selected_income_id:
            selected_income = next(
                item for item in incomes if item["id"] == selected_income_id
            )
            with st.form(f"edit_income_form_{selected_income_id}"):
                edit_source_col, edit_amount_col = st.columns([2, 1])
                with edit_source_col:
                    edited_source = st.text_input(
                        "Where did the money come from?",
                        value=selected_income["source_name"],
                    )
                with edit_amount_col:
                    edited_amount = st.number_input(
                        "How much?",
                        min_value=0.0,
                        value=float(selected_income["amount"]),
                        step=100.0,
                        format="%.2f",
                    )
                edit_submitted = st.form_submit_button(
                    "Save income changes",
                    type="primary",
                )
            if edit_submitted:
                try:
                    update_income(
                        user_id,
                        period_id,
                        selected_income_id,
                        edited_source,
                        edited_amount,
                    )
                    st.rerun()
                except FinancialTrackerError as exc:
                    st.error(str(exc))

        st.divider()
        st.caption("Select one or more incorrect entries to remove.")
        selected_income_ids = st.pills(
            "Income entries to remove",
            list(labels),
            format_func=labels.get,
            selection_mode="multi",
            key="income_to_delete",
        )
        if st.button(
            "Remove selected income",
            disabled=not selected_income_ids,
        ):
            for selected_income_id in selected_income_ids:
                delete_income(user_id, period_id, selected_income_id)
            st.rerun()


@st.dialog("Plan the week", width="large")
def budget_dialog() -> None:
    st.write(
        "Give each part of your income a job. A fixed expense is something "
        "you expect to pay every week."
    )
    form_version = st.session_state.get("budget_form_version", 0)
    entry_count = int(
        st.number_input(
            "How many budget categories are you adding?",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key=f"budget_entry_count_{form_version}",
        )
    )

    entries = []
    for index in range(entry_count):
        with st.container(border=True):
            st.markdown(f"**Budget Category {index + 1}**")
            category_col, amount_col = st.columns(2)
            with category_col:
                group = st.selectbox(
                    "Is this a need, want, or savings?",
                    GROUPS,
                    key=f"budget_group_{form_version}_{index}",
                )
                category = st.text_input(
                    "What is it for?",
                    placeholder="Transport, groceries, emergency fund…",
                    key=f"budget_category_{form_version}_{index}",
                )
            with amount_col:
                amount = st.number_input(
                    "Planned amount",
                    min_value=0.0,
                    step=100.0,
                    format="%.2f",
                    key=f"budget_amount_{form_version}_{index}",
                )
                is_fixed = st.checkbox(
                    "I expect to pay this every week",
                    key=f"budget_fixed_{form_version}_{index}",
                )
            entries.append(
                {
                    "category_group": group,
                    "category_name": category,
                    "amount": amount,
                    "is_fixed": is_fixed,
                }
            )

    category_word = "category" if entry_count == 1 else "categories"
    if st.button(
        f"Save {entry_count} budget {category_word}",
        type="primary",
    ):
        try:
            upsert_budgets_batch(user_id, period_id, entries)
            st.session_state["budget_form_version"] = form_version + 1
            st.rerun()
        except FinancialTrackerError as exc:
            st.error(str(exc))

    if budgets:
        st.divider()
        budget_labels = {
            item["id"]: (
                f"{item['category_name']} — "
                f"{format_currency(item['allocated_amount'])}"
            )
            for item in budgets
        }

        st.caption("Select a budget category to edit.")
        selected_budget_id = st.pills(
            "Budget category to edit",
            list(budget_labels),
            format_func=budget_labels.get,
            selection_mode="single",
            key="budget_to_edit",
        )
        if selected_budget_id:
            selected_budget = next(
                item for item in budgets if item["id"] == selected_budget_id
            )
            with st.form(f"edit_budget_form_{selected_budget_id}"):
                edit_category_col, edit_amount_col = st.columns(2)
                with edit_category_col:
                    edited_group = st.selectbox(
                        "Is this a need, want, or savings?",
                        GROUPS,
                        index=GROUPS.index(selected_budget["category_group"]),
                    )
                    edited_category = st.text_input(
                        "What is it for?",
                        value=selected_budget["category_name"],
                    )
                with edit_amount_col:
                    edited_amount = st.number_input(
                        "Planned amount",
                        min_value=0.0,
                        value=float(selected_budget["allocated_amount"]),
                        step=100.0,
                        format="%.2f",
                    )
                    edited_is_fixed = st.checkbox(
                        "I expect to pay this every week",
                        value=bool(selected_budget.get("is_fixed")),
                    )
                edit_submitted = st.form_submit_button(
                    "Save budget changes",
                    type="primary",
                )
            if edit_submitted:
                try:
                    update_budget(
                        user_id,
                        period_id,
                        selected_budget_id,
                        edited_group,
                        edited_category,
                        edited_amount,
                        edited_is_fixed,
                    )
                    st.rerun()
                except FinancialTrackerError as exc:
                    st.error(str(exc))

        st.divider()
        st.caption("Select one or more unused categories to remove.")
        used_budget_ids = {
            item.get("budget_id") for item in transactions if item.get("budget_id")
        }
        removable_budgets = [
            item for item in budgets if item["id"] not in used_budget_ids
        ]
        removable_labels = {
            item[
                "id"
            ]: f"{item['category_name']} — {format_currency(item['allocated_amount'])}"
            for item in removable_budgets
        }
        if removable_labels:
            selected_budget_ids = st.pills(
                "Budget categories to remove",
                list(removable_labels),
                format_func=removable_labels.get,
                selection_mode="multi",
                key="budget_to_delete",
            )
            if st.button(
                "Remove selected categories",
                disabled=not selected_budget_ids,
            ):
                try:
                    for selected_budget_id in selected_budget_ids:
                        delete_budget(user_id, period_id, selected_budget_id)
                    st.rerun()
                except FinancialTrackerError as exc:
                    st.error(str(exc))
        else:
            st.info(
                "Every budget category is currently connected to an expense. "
                "Remove those expenses first if you also want to remove a category."
            )


@st.dialog("Manage spending", width="large")
def transaction_dialog() -> None:
    st.write(
        "Choose how many transactions you want to enter, fill them in, then "
        "save everything once."
    )
    options = [None] + [item["id"] for item in budgets]
    by_id = {item["id"]: item for item in budgets}

    def label(value):
        if value is None:
            return "Something not in my plan"
        item = by_id[value]
        return f"{item['category_group']} · {item['category_name']}"

    form_version = st.session_state.get("transaction_form_version", 0)
    entry_count = int(
        st.number_input(
            "How many transactions are you entering?",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key=f"batch_entry_count_{form_version}",
        )
    )

    entries = []
    for index in range(entry_count):
        with st.container(border=True):
            st.markdown(f"**Transaction {index + 1}**")
            category_col, amount_col, date_col = st.columns([2, 1, 1.25])
            with category_col:
                selected = st.selectbox(
                    "Where did the money go?",
                    options,
                    format_func=label,
                    key=f"batch_category_{form_version}_{index}",
                )
            with amount_col:
                amount = st.number_input(
                    "How much?",
                    min_value=0.0,
                    step=50.0,
                    format="%.2f",
                    key=f"batch_amount_{form_version}_{index}",
                )
            with date_col:
                transaction_date = st.date_input(
                    "When was it?",
                    value=None,
                    min_value=period_start,
                    max_value=period_end,
                    format="MM-DD-YYYY",
                    key=f"batch_date_{form_version}_{index}",
                )

            custom = ""
            if selected is None:
                custom = st.text_input(
                    "What was it?",
                    placeholder="Medicine, repair, school fee…",
                    key=f"batch_custom_{form_version}_{index}",
                )
            entries.append(
                {
                    "budget_id": selected,
                    "amount": amount,
                    "transaction_date": transaction_date,
                    "unbudgeted_category": custom,
                }
            )

    if st.button(f"Save {entry_count} transaction(s)", type="primary"):
        try:
            log_transactions_batch(user_id, period_id, entries)
            st.session_state["transaction_form_version"] = form_version + 1
            st.rerun()
        except FinancialTrackerError as exc:
            st.error(str(exc))

    if transactions:
        st.divider()
        st.caption("Select one or more incorrect transactions to remove.")
        labels = {
            item["id"]: (
                f"{item['transaction_date']} · {item['category_name']} — "
                f"{format_currency(item['amount'])}"
            )
            for item in transactions
        }
        transaction_ids = st.pills(
            "Transactions to remove",
            list(labels),
            format_func=labels.get,
            selection_mode="multi",
        )
        if st.button(
            "Remove selected transactions",
            disabled=not transaction_ids,
        ):
            try:
                for transaction_id in transaction_ids:
                    delete_transaction(user_id, period_id, transaction_id)
                st.rerun()
            except FinancialTrackerError as exc:
                st.error(str(exc))


@st.dialog("Add a budget note", width="medium")
def note_dialog() -> None:
    st.write(
        "Use this when real life did not follow the plan. The goal is to "
        "understand, not to judge yourself."
    )
    budget_options = [None] + [item["id"] for item in budgets]
    budget_names = {item["id"]: item["category_name"] for item in budgets}
    note_type = st.selectbox("What changed?", NOTE_TYPES)
    budget_id = st.selectbox(
        "Which part of the plan?",
        budget_options,
        format_func=lambda value: (
            "The week in general" if value is None else budget_names[value]
        ),
    )
    note_text = st.text_area(
        "What happened?", placeholder="I spent more on transport because…"
    )
    next_action = st.text_area(
        "What will I try next time? (optional)",
        placeholder="Increase this budget, prepare earlier, or leave it unchanged…",
    )
    if st.button("Save note", type="primary"):
        try:
            add_note(user_id, period_id, note_type, note_text, next_action, budget_id)
            st.rerun()
        except FinancialTrackerError as exc:
            st.error(str(exc))

    if notes:
        st.divider()
        labels = {
            item[
                "id"
            ]: f"{item['note_type']} · {item.get('category_name') or 'General'}"
            for item in notes
        }
        note_id = st.selectbox("Saved note", list(labels), format_func=labels.get)
        if st.button("Remove selected note"):
            delete_note(user_id, period_id, note_id)
            st.rerun()


@st.dialog("Close this week", width="medium")
def close_dialog() -> None:
    st.write(
        "Closing saves the final balances and permanently locks the financial entries."
    )
    st.metric("Money still unassigned", format_currency(summary["unallocated"]))
    if summary["unallocated"] < 0:
        st.error(
            f"You are short by {format_currency(abs(summary['unallocated']))}. "
            "Correct an entry before closing."
        )
        return
    if needs_reflection and not notes:
        st.info(
            "This week differed from the plan. You may close it now, but adding "
            "a short note first can make next week's plan easier."
        )
    destination = st.selectbox(
        "What should happen to the money left over?",
        ["Keep as Cash", "Add to Savings", "Piggy Bank"],
    )
    projection = projected_close(period, summary, destination)
    st.info(
        f"After closing: {format_currency(projection['ending_cash'])} cash and "
        f"{format_currency(projection['total_savings'])} total savings."
    )
    confirmed = st.checkbox(
        "I understand that financial entries cannot be changed afterward."
    )
    if st.button("Close and lock this week", type="primary"):
        if not confirmed:
            st.error("Please confirm the permanent lock first.")
            return
        try:
            route_surplus_and_close(user_id, period_id, destination)
            st.rerun()
        except FinancialTrackerError as exc:
            st.error(str(exc))
        except Exception:
            st.error("The week could not be closed. Nothing was changed.")


@st.dialog("Start another week", width="small")
def new_week_dialog() -> None:
    st.write("Balances will carry forward from your latest closed week.")
    suggested_date = suggested_next_period_date(periods)
    earliest_date = dt.date.fromisoformat(periods[0]["start_date"]) + dt.timedelta(
        days=7
    )
    selected_date = st.date_input(
        "Choose any date in the new week",
        value=suggested_date,
        min_value=earliest_date,
        format="MM-DD-YYYY",
    )
    selected_iso = selected_date.isocalendar()
    selected_dates = format_iso_week_dates(selected_iso.year, selected_iso.week)
    st.info(
        f"This will create {selected_iso.year}-W{selected_iso.week:02d}: "
        f"{selected_dates}."
    )
    if st.button("Start this week", type="primary"):
        try:
            new_period = create_period(
                user_id,
                selected_iso.year,
                selected_iso.week,
            )
            st.session_state["selected_period_id"] = new_period["id"]
            st.rerun()
        except FinancialTrackerError as exc:
            st.error(str(exc))


@st.dialog("Money history", width="large")
def history_dialog() -> None:
    closed_periods = get_closed_periods(user_id)
    if not closed_periods:
        st.info("Your history will appear after you close your first week.")
        return
    periods_df = pd.DataFrame(closed_periods)
    periods_df["Week"] = (
        periods_df["year"].astype(str)
        + "-W"
        + periods_df["week_number"].astype(int).astype(str).str.zfill(2)
    )
    periods_df["ending_cash"] = pd.to_numeric(periods_df["ending_cash"])
    periods_df["total_savings"] = pd.to_numeric(periods_df["total_savings"])
    st.subheader("Cash and savings over time")
    st.line_chart(periods_df.set_index("Week")[["ending_cash", "total_savings"]])

    historical = get_historical_transactions(user_id, periods_df["id"].tolist())
    if historical:
        tx_df = pd.DataFrame(historical)
        tx_df["amount"] = pd.to_numeric(tx_df["amount"])
        merged = tx_df.merge(
            periods_df[["id", "Week"]], left_on="period_id", right_on="id"
        )
        spending = merged[merged["category_group"].isin(["Need", "Want", "Unbudgeted"])]
        if not spending.empty:
            st.subheader("Actual spending over time")
            chart = (
                spending.groupby(["Week", "category_name"])["amount"]
                .sum()
                .unstack(fill_value=0)
            )
            st.bar_chart(chart)


@st.dialog("Opening balances", width="small")
def opening_balance_dialog() -> None:
    can_edit = not is_closed and can_set_initial_balances(user_id, period_id)

    if can_edit:
        st.write("Tell the dashboard what you already had before tracking began.")
        cash = st.number_input(
            "Cash already on hand",
            min_value=0.0,
            value=float(period["starting_cash"]),
            format="%.2f",
        )
        savings = st.number_input(
            "Savings already accumulated",
            min_value=0.0,
            value=float(period["total_savings"]),
            format="%.2f",
        )
        if st.button("Save opening balances", type="primary"):
            try:
                set_initial_balances(user_id, period_id, cash, savings)
                st.rerun()
            except FinancialTrackerError as exc:
                st.error(str(exc))
        return

    if is_closed:
        st.write("This week is closed, so its balances can no longer be changed.")
        balance_cols = st.columns(2)
        balance_cols[0].metric(
            "Starting Cash",
            format_currency(period["starting_cash"]),
        )
        balance_cols[1].metric(
            "Final Total Savings",
            format_currency(period["total_savings"]),
        )
        return

    st.write("These balances were carried forward from your latest closed week.")
    balance_cols = st.columns(2)
    balance_cols[0].metric(
        "Starting Cash",
        format_currency(period["starting_cash"]),
    )
    balance_cols[1].metric(
        "Savings Carried In",
        format_currency(period["total_savings"]),
    )
    st.info("Close the previous week to change what carries into the next one.")


st.markdown(
    "<h2 style='text-align: center;'>What would you like to do?</h2>",
    unsafe_allow_html=True,
)
action_cols = st.columns(4)
manage_income_clicked = action_cols[0].button(
    "Manage Income", disabled=is_closed, use_container_width=True
)
budget_clicked = action_cols[1].button(
    "Manage Budget", disabled=is_closed, use_container_width=True
)
transaction_clicked = action_cols[2].button(
    "Manage Spending", disabled=is_closed, use_container_width=True
)
note_clicked = action_cols[3].button("Add Note", use_container_width=True)

secondary_cols = st.columns(4)

close_clicked = secondary_cols[0].button(
    "Close Week", disabled=is_closed, use_container_width=True
)
history_clicked = secondary_cols[1].button("View History", use_container_width=True)
has_open_period = any(not item["is_closed"] for item in periods)
opening_balance_clicked = secondary_cols[2].button(
    "Opening Balances", use_container_width=True
)
new_week_clicked = secondary_cols[3].button(
    "New Week", disabled=has_open_period, use_container_width=True
)

if manage_income_clicked:
    income_dialog()
elif budget_clicked:
    budget_dialog()
elif transaction_clicked:
    transaction_dialog()
elif note_clicked:
    note_dialog()
elif close_clicked:
    close_dialog()
elif history_clicked:
    history_dialog()
elif opening_balance_clicked:
    opening_balance_dialog()
elif new_week_clicked:
    new_week_dialog()

st.divider()
display_savings = (
    period["total_savings"]
    if is_closed
    else float(period["total_savings"]) + float(summary["savings_contributions"])
)

balance_cols = st.columns(2)
balance_cols[0].metric("Starting Cash", format_currency(period["starting_cash"]))
balance_cols[1].metric("Total Savings", format_currency(display_savings))

metric_cols = st.columns(4)
metric_cols[0].metric("Money Received", format_currency(summary["income"]))
metric_cols[1].metric("Actual Expenses", format_currency(summary["expenses"]))
metric_cols[2].metric(
    "Saved This Week", format_currency(summary["savings_contributions"])
)
metric_cols[3].metric("Still Unassigned", format_currency(summary["unallocated"]))

if summary["income"] == 0:
    st.info(
        "Start with **Manage Income** so the dashboard knows how much money arrived this week."
    )
elif not budgets:
    st.info("Next, choose **Manage budget** to decide where the money should go.")
elif summary["unallocated"] < 0:
    st.error(
        f"Your actual activity is {format_currency(abs(summary['unallocated']))} "
        "more than this week's income."
    )
elif not transactions:
    st.info(
        "Your plan is ready. Use **Manage spending** whenever money is spent "
        "or moved to savings."
    )
else:
    st.success(
        f"You still have {format_currency(summary['unallocated'])} to assign "
        "before closing the week."
    )

if needs_reflection and not notes:
    st.warning(
        "Something went beyond the plan or was unplanned. Use **Add note** to "
        "record what happened and what you may change next time."
    )

left, right = st.columns(2)
with left:
    st.subheader("1. Sources of Income")
    if incomes:
        income_df = pd.DataFrame(incomes)
        income_df["amount"] = pd.to_numeric(income_df["amount"])
        render_themed_dataframe(
            income_df[["source_name", "amount"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "source_name": "Source",
                "amount": st.column_config.NumberColumn("Amount", format="₱%.2f"),
            },
        )
    else:
        st.caption("No income has been recorded yet.")

with right:
    st.subheader("2. Fixed Expenses")
    fixed = [item for item in performance if item["Type"] == "Fixed"]
    if fixed:
        fixed_df = pd.DataFrame(fixed)
        fixed_df["Status"] = fixed_df.apply(
            lambda row: fixed_expense_status(row["Budget"], row["Actual"]), axis=1
        )
        render_themed_dataframe(
            fixed_df[["Category", "Budget", "Actual", "Status"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Budget": st.column_config.NumberColumn("Expected", format="₱%.2f"),
                "Actual": st.column_config.NumberColumn("Actual", format="₱%.2f"),
            },
        )
    else:
        st.caption("Mark recurring categories as fixed when planning the budget.")

st.subheader("3. Budget Plan vs Actual Expense")
if performance:
    plan_df = pd.DataFrame(performance)
    render_themed_dataframe(
        plan_df[["Group", "Category", "Type", "Budget", "Actual", "Remaining"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Budget": st.column_config.NumberColumn(format="₱%.2f"),
            "Actual": st.column_config.NumberColumn(format="₱%.2f"),
            "Remaining": st.column_config.NumberColumn(format="₱%.2f"),
        },
    )
else:
    st.caption("No budget plan has been created for this week.")

st.subheader("4. Actual Expenses")
expense_rows = [item for item in transactions if item["category_group"] != "Savings"]
if expense_rows:
    expense_df = pd.DataFrame(expense_rows)
    expense_df["Date"] = pd.to_datetime(expense_df["transaction_date"]).dt.strftime(
        "%m-%d-%Y"
    )
    expense_df["amount"] = pd.to_numeric(expense_df["amount"])
    render_themed_dataframe(
        expense_df[["Date", "category_group", "category_name", "amount"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "category_group": "Type",
            "category_name": "Expense",
            "amount": st.column_config.NumberColumn("Amount", format="₱%.2f"),
        },
    )
else:
    st.caption("No actual expenses have been recorded.")

st.subheader("Budget Notes")
st.caption("A short reflection for moments when the plan and real life did not match.")
if notes:
    notes_df = pd.DataFrame(notes)
    notes_df["Category"] = notes_df["category_name"].fillna("Whole week")
    notes_df["Next time"] = notes_df["next_action"].fillna("—")
    render_themed_dataframe(
        notes_df[["note_type", "Category", "note_text", "Next time"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "note_type": "Reason",
            "note_text": "What happened",
        },
    )
else:
    st.caption("No notes yet. Add one only when it would help you understand the week.")
