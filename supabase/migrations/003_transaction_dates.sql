-- Adds a user-selected expense date while preserving created_at as the audit timestamp.
-- Run this after 001 and 002 when upgrading an existing deployment.

alter table public.transactions
    add column if not exists transaction_date date;

update public.transactions
set transaction_date = (created_at at time zone 'Asia/Manila')::date
where transaction_date is null;

alter table public.transactions
    alter column transaction_date set default current_date;

alter table public.transactions
    alter column transaction_date set not null;

create index if not exists transactions_period_date_idx
    on public.transactions (period_id, transaction_date desc, created_at desc);
