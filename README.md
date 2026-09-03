# Personal Finance Tracker

A secure, single-dashboard Streamlit + Supabase tracker for two isolated
PIN-based profiles, weekly budgeting, reflection notes, savings, closing,
rollover, and multi-year analytics.

## Important upgrade notes

The migration upgrades the prototype schema and converts existing plaintext
`pin_code` values into bcrypt hashes before dropping that column. Back up the
database before applying any migration. If normalized duplicate names exist
(for example `Kai` and `kai`), the migration stops and asks you to rename them.
Likewise, resolve duplicate budget category names that differ only by case before
adding the new uniqueness constraint.

## 1. Create or upgrade the database

Open the Supabase SQL Editor and run these files in order:

`supabase/migrations/001_secure_financial_tracker.sql`

`supabase/migrations/002_single_dashboard_notes.sql`

`supabase/migrations/003_transaction_dates.sql`

The migration enables RLS, removes browser-role table access, adds ownership and
data constraints, installs closed-period mutation guards, and creates the atomic
`close_financial_period` function. The second migration adds fixed-expense flags
and budget-reflection notes. The third adds manually selected expense dates while
preserving the automatic database creation timestamp. Run all three in order.

## 2. Configure local secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "YOUR_SERVER_ONLY_SECRET_KEY"
```

Use a Supabase secret key when available; the legacy service-role key is also
accepted. This key bypasses RLS, so it must remain server-only.

## 3. Run locally

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## 4. Run tests

```bash
python -m unittest discover -s tests -v
python -m compileall app.py database.py ui.py services
```

## 5. Deploy to Render

Connect the repository to Render and use `render.yaml`. Add `SUPABASE_URL` and
`SUPABASE_SECRET_KEY` as secret environment variables. The database module reads
Render environment variables first and local Streamlit secrets second.

## Financial rules

- Budget allocations are plans; transactions are actual movements.
- Need, Want, and Unbudgeted transactions are expenses.
- Savings transactions become accumulated savings when the week closes.
- Remaining weekly funds can become cash, savings, or an untracked piggy-bank sink.
- A deficit must be corrected before closing.
- Closing is atomic and permanent.
- Fixed weekly expenses copy into the next week's plan automatically.
- Reflection notes explain deviations without affecting any balance.

## User experience

There is one dashboard and no sidebar navigation. Its action buttons open small,
focused dialogs for managing income, planning a budget, logging spending, writing
a note, closing the week, viewing history, and starting a new week. The dashboard
always shows income sources, fixed weekly expenses, budget versus actual, and
actual expenses in that order.

The Week selector includes the Monday-to-Sunday date range. Week Status uses a
colored status box, and New Week uses a calendar date while deriving the ISO week
automatically. Opening Balances remains available on every week: the first open
week is editable, while later weeks show the balances carried forward.

The income, budget, and spending dialogs support up to 20 entries at once.
Existing income and budget records can be edited inside their management dialogs
while the week is open. Every spending entry requires a manually selected date
within the chosen ISO week. Deletion uses inline multi-selection instead of
dropdown menus.

See `requirements.md` for the complete accepted behavior.
