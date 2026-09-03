-- Apply this after 001 when upgrading a deployment that already used the
-- earlier secure version. It is safe to run after the updated 001 migration.

alter table public.budgets
    add column if not exists is_fixed boolean not null default false;

create table if not exists public.period_notes (
    id uuid primary key default gen_random_uuid(),
    period_id uuid not null references public.financial_periods(id) on delete cascade,
    budget_id uuid references public.budgets(id) on delete set null,
    note_type text not null default 'General',
    category_name text,
    note_text text not null,
    next_action text,
    created_at timestamptz not null default now(),
    constraint period_notes_type_check check (
        note_type in ('General', 'Overspent', 'Skipped plan', 'Unexpected expense', 'Changed priority')
    ),
    constraint period_notes_text_check check (char_length(trim(note_text)) between 1 and 1000)
);

create index if not exists period_notes_period_idx
    on public.period_notes (period_id, created_at desc);

alter table public.period_notes enable row level security;
revoke all on table public.period_notes from anon, authenticated;

