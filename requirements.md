# Personal Finance Tracker — Final Requirements

## 1. Purpose

The system is a private, two-user personal finance tracker. Both users share one
Supabase PostgreSQL project, while all application reads and writes remain
isolated by user ownership. The interface is built with Streamlit and supports
multiple ISO weeks across multiple years.

## 2. Authentication and isolation

- A user registers with a unique display name and exactly four numeric PIN digits.
- The PIN is stored only as a bcrypt hash; plaintext PINs are never persisted.
- Five failed attempts lock the profile for 15 minutes.
- Authentication and all database calls execute on the trusted Streamlit server.
- The Supabase secret/service key must never be exposed to the browser or committed.
- PostgreSQL RLS is enabled and `anon` and `authenticated` receive no direct table access.
- Every service operation verifies that the requested period belongs to the session user.
- Logout clears user and selected-period session state.

PIN-only authentication is intentionally convenient for a private deployment,
but it is not equivalent to a strong password or multifactor authentication.

## 3. Financial periods

- A period is identified by `(user_id, ISO year, ISO week)` and begins on Monday.
- Week selectors show both the ISO identifier and the Monday-to-Sunday date range.
- Each user can have at most one open period.
- New periods must be chronologically later than the user's latest period.
- New periods are chosen from a calendar date; the system derives the ISO year and week.
- A new period inherits ending cash and total savings from the latest earlier closed period.
- The first period permits one opening-balance setup for existing cash and savings.
- Opening Balances remains visible on every period. It is editable only for the
  first open period and otherwise explains the carried or locked balances.
- Closed periods are permanently immutable.

## 4. Income and budgets

- An open period accepts positive income entries with a source label.
- Existing income entries can be edited while their period remains open.
- Budget categories belong to Need, Want, or Savings.
- A category can be marked as a fixed weekly expense.
- Existing budget categories can be edited while their period remains open.
- Fixed weekly categories automatically copy into the next period's budget plan.
- Category names are unique within a period, ignoring case.
- Budget totals may exceed income but the UI must show a warning.
- Entries may be deleted only while the period is open.
- A budget category referenced by a transaction cannot be deleted.

## 5. Transactions and financial meaning

- Transactions are positive amounts assigned to a budget or an Unbudgeted category.
- The user chooses how many transactions to enter and can save up to 20 at once.
- Every transaction requires a user-selected date within its financial week;
  the interface does not automatically choose the submission date.
- The transaction date and database creation timestamp are stored separately.
- A batch is validated completely before one atomic database insert, preventing partial saves.
- A transaction may exceed its budget; actual spending is never capped.
- Need, Want, and Unbudgeted transactions count as expenses.
- Savings transactions reduce unallocated weekly income and become accumulated savings at close.
- Piggy Bank is a hidden sink recorded only by the close-week operation.
- Unallocated funds equal income minus every non-sink transaction.

## 6. Closing a week

- A deficit period cannot be closed.
- Nonnegative unallocated funds are routed to Keep as Cash, Add to Savings, or Piggy Bank.
- Savings-category transactions always increase accumulated savings.
- Closing, balance calculation, optional sink insertion, and locking occur atomically in PostgreSQL.
- The user must explicitly acknowledge the permanent lock.

## 7. Views

- The product uses one main dashboard and no sidebar page navigation.
- Week status is shown as a colored read-only status box rather than a disabled input.
- Plain-language buttons open focused dialogs for income, budget planning,
  batch spending management, notes, week closing, history, and starting another week.
- Income, budget, and transaction deletion use explicit multi-selection and confirmation buttons.
- The main dashboard explicitly answers four questions: where income came from,
  which fixed expenses exist, what the budget plan was, and what was actually spent.
- Historical charts appear from the View history button without leaving the dashboard.

## 8. Budget reflection notes

- A note can describe overspending, a skipped plan, an unexpected expense, a
  changed priority, or a general observation.
- A note can be attached to one budget category or the whole week.
- A note records what happened and an optional action for next time.
- Notes do not change balances and may be added after a period is closed.
- Notes remain isolated through period ownership checks.

## 9. Nonfunctional requirements

- Monetary calculations use decimal values rounded to two places.
- UUID ownership is verified before child-table queries or mutations.
- Dates display as `MM-DD-YYYY` in transaction tables.
- Secrets are supplied through Streamlit secrets locally and environment variables on Render.
- The repository includes a reproducible SQL migration and calculation tests.

## 10. Acceptance criteria

The release is acceptable when two profiles can register, cannot retrieve each
other's periods through service calls, can independently progress through weeks,
receive correct cash/savings rollovers, cannot mutate closed periods, and the
included test suite passes.
