-- Secure schema for the Streamlit financial tracker.
-- This migration upgrades the original schema in place when possible.

create extension if not exists pgcrypto;

create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    display_name text not null,
    created_at timestamptz not null default now()
);

alter table public.users alter column id set default gen_random_uuid();

alter table public.users add column if not exists display_name_normalized text;
alter table public.users add column if not exists pin_hash text;
alter table public.users add column if not exists failed_login_attempts integer not null default 0;
alter table public.users add column if not exists locked_until timestamptz;

-- Safely upgrade plaintext PINs created by the original prototype.
do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'users' and column_name = 'pin_code'
    ) then
        execute $sql$
            update public.users
            set pin_hash = crypt(pin_code, gen_salt('bf', 12))
            where pin_hash is null and pin_code is not null
        $sql$;
    end if;
end
$$;

update public.users
set display_name = regexp_replace(trim(display_name), '\s+', ' ', 'g'),
    display_name_normalized = lower(regexp_replace(trim(display_name), '\s+', ' ', 'g'));

do $$
begin
    if exists (
        select display_name_normalized
        from public.users
        group by display_name_normalized
        having count(*) > 1
    ) then
        raise exception 'Duplicate display names exist after normalization. Rename duplicates before rerunning this migration.';
    end if;
    if exists (select 1 from public.users where pin_hash is null) then
        raise exception 'At least one user has no PIN hash. Set pin_hash before rerunning this migration.';
    end if;
end
$$;

alter table public.users alter column display_name_normalized set not null;
alter table public.users alter column pin_hash set not null;
create unique index if not exists users_display_name_normalized_key
    on public.users (display_name_normalized);

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'users' and column_name = 'pin_code'
    ) then
        alter table public.users drop column pin_code;
    end if;
end
$$;

create table if not exists public.financial_periods (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    year integer not null,
    week_number integer not null,
    start_date date not null,
    is_closed boolean not null default false,
    starting_cash numeric(14,2) not null default 0,
    ending_cash numeric(14,2) not null default 0,
    total_savings numeric(14,2) not null default 0,
    created_at timestamptz not null default now(),
    closed_at timestamptz,
    unique (user_id, year, week_number)
);

alter table public.financial_periods alter column id set default gen_random_uuid();

alter table public.financial_periods add column if not exists created_at timestamptz not null default now();
alter table public.financial_periods add column if not exists closed_at timestamptz;
update public.financial_periods
set start_date = to_date(year::text || lpad(week_number::text, 2, '0'), 'IYYYIW');

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'financial_periods_week_check') then
        alter table public.financial_periods
            add constraint financial_periods_week_check check (week_number between 1 and 53);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'financial_periods_year_check') then
        alter table public.financial_periods
            add constraint financial_periods_year_check check (year between 2000 and 2200);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'financial_periods_nonnegative_check') then
        alter table public.financial_periods
            add constraint financial_periods_nonnegative_check
            check (starting_cash >= 0 and ending_cash >= 0 and total_savings >= 0);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'financial_periods_iso_monday_check') then
        alter table public.financial_periods
            add constraint financial_periods_iso_monday_check
            check (
                extract(isoyear from start_date)::integer = year
                and extract(week from start_date)::integer = week_number
                and extract(isodow from start_date)::integer = 1
            );
    end if;
end
$$;

-- Only one mutable period can exist for a user at any time.
create unique index if not exists financial_periods_one_open_per_user
    on public.financial_periods (user_id) where is_closed = false;
create index if not exists financial_periods_user_start_idx
    on public.financial_periods (user_id, start_date desc);

create table if not exists public.incomes (
    id uuid primary key default gen_random_uuid(),
    period_id uuid not null references public.financial_periods(id) on delete cascade,
    source_name text not null,
    amount numeric(14,2) not null check (amount > 0),
    created_at timestamptz not null default now()
);
alter table public.incomes alter column id set default gen_random_uuid();
alter table public.incomes add column if not exists created_at timestamptz not null default now();
create index if not exists incomes_period_idx on public.incomes (period_id);

create table if not exists public.budgets (
    id uuid primary key default gen_random_uuid(),
    period_id uuid not null references public.financial_periods(id) on delete cascade,
    category_group text not null,
    category_name text not null,
    allocated_amount numeric(14,2) not null default 0,
    is_fixed boolean not null default false,
    created_at timestamptz not null default now()
);
alter table public.budgets alter column id set default gen_random_uuid();
alter table public.budgets add column if not exists created_at timestamptz not null default now();
alter table public.budgets add column if not exists category_key text;
alter table public.budgets add column if not exists is_fixed boolean not null default false;
update public.budgets
set category_name = regexp_replace(trim(category_name), '\s+', ' ', 'g'),
    category_key = lower(regexp_replace(trim(category_name), '\s+', ' ', 'g'));
alter table public.budgets alter column category_key set not null;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'budgets_group_check') then
        alter table public.budgets
            add constraint budgets_group_check check (category_group in ('Need', 'Want', 'Savings'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'budgets_amount_check') then
        alter table public.budgets
            add constraint budgets_amount_check check (allocated_amount >= 0);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'budgets_period_category_key') then
        alter table public.budgets
            add constraint budgets_period_category_key unique (period_id, category_key);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'budgets_period_id_id_key') then
        alter table public.budgets
            add constraint budgets_period_id_id_key unique (period_id, id);
    end if;
end
$$;
create index if not exists budgets_period_idx on public.budgets (period_id);

create table if not exists public.transactions (
    id uuid primary key default gen_random_uuid(),
    period_id uuid not null references public.financial_periods(id) on delete cascade,
    budget_id uuid references public.budgets(id) on delete restrict,
    category_group text not null default 'Unbudgeted',
    category_name text not null,
    amount numeric(14,2) not null check (amount > 0),
    is_sink boolean not null default false,
    transaction_date date not null default current_date,
    created_at timestamptz not null default now()
);
alter table public.transactions alter column id set default gen_random_uuid();
alter table public.transactions add column if not exists budget_id uuid references public.budgets(id) on delete restrict;
alter table public.transactions add column if not exists category_group text;
alter table public.transactions add column if not exists transaction_date date;
alter table public.transactions add column if not exists created_at timestamptz not null default now();

update public.transactions
set transaction_date = (created_at at time zone 'Asia/Manila')::date
where transaction_date is null;

alter table public.transactions alter column transaction_date set default current_date;
alter table public.transactions alter column transaction_date set not null;

update public.transactions t
set budget_id = b.id,
    category_group = b.category_group
from public.budgets b
where t.period_id = b.period_id
  and lower(trim(t.category_name)) = b.category_key
  and t.budget_id is null;

update public.transactions
set category_group = case when is_sink then 'Sink' else 'Unbudgeted' end
where category_group is null;
alter table public.transactions alter column category_group set not null;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'transactions_group_check') then
        alter table public.transactions
            add constraint transactions_group_check
            check (category_group in ('Need', 'Want', 'Savings', 'Unbudgeted', 'Sink'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'transactions_budget_same_period_fk') then
        alter table public.transactions
            add constraint transactions_budget_same_period_fk
            foreign key (period_id, budget_id)
            references public.budgets(period_id, id)
            on delete restrict;
    end if;
end
$$;
create index if not exists transactions_period_idx on public.transactions (period_id);
create index if not exists transactions_budget_idx on public.transactions (budget_id);
create index if not exists transactions_period_date_idx
    on public.transactions (period_id, transaction_date desc, created_at desc);

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
alter table public.period_notes alter column id set default gen_random_uuid();
create index if not exists period_notes_period_idx on public.period_notes (period_id, created_at desc);

-- Reject changes to child rows once their financial period is closed.
create or replace function public.reject_closed_period_mutation()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
    target_period_id uuid;
    closed boolean;
begin
    target_period_id := case when tg_op = 'DELETE' then old.period_id else new.period_id end;
    select p.is_closed into closed
    from public.financial_periods p
    where p.id = target_period_id;

    if closed then
        raise exception 'This financial period is closed and cannot be changed.';
    end if;
    return case when tg_op = 'DELETE' then old else new end;
end
$$;

drop trigger if exists incomes_reject_closed on public.incomes;
create trigger incomes_reject_closed before insert or update or delete on public.incomes
for each row execute function public.reject_closed_period_mutation();

drop trigger if exists budgets_reject_closed on public.budgets;
create trigger budgets_reject_closed before insert or update or delete on public.budgets
for each row execute function public.reject_closed_period_mutation();

drop trigger if exists transactions_reject_closed on public.transactions;
create trigger transactions_reject_closed before insert or update or delete on public.transactions
for each row execute function public.reject_closed_period_mutation();

create or replace function public.reject_reopening_period()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if old.is_closed then
        raise exception 'A closed financial period is permanently locked.';
    end if;
    return new;
end
$$;

drop trigger if exists financial_periods_reject_reopen on public.financial_periods;
create trigger financial_periods_reject_reopen before update or delete on public.financial_periods
for each row when (old.is_closed = true)
execute function public.reject_reopening_period();

-- Calculates balances, records a piggy-bank sink when selected, and locks the
-- period inside one PostgreSQL transaction.
create or replace function public.close_financial_period(
    p_user_id uuid,
    p_period_id uuid,
    p_destination text
)
returns table (
    period_id uuid,
    ending_cash numeric,
    total_savings numeric,
    surplus numeric,
    savings_contributed numeric
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
    p public.financial_periods%rowtype;
    income_total numeric(14,2);
    allocated_total numeric(14,2);
    savings_total numeric(14,2);
    available numeric(14,2);
    next_cash numeric(14,2);
    next_savings numeric(14,2);
begin
    if p_destination not in ('Keep as Cash', 'Add to Savings', 'Piggy Bank') then
        raise exception 'Invalid surplus destination.';
    end if;

    select * into p
    from public.financial_periods fp
    where fp.id = p_period_id and fp.user_id = p_user_id
    for update;

    if not found then
        raise exception 'Financial period not found for this user.';
    end if;
    if p.is_closed then
        raise exception 'This financial period is already closed.';
    end if;

    select coalesce(sum(i.amount), 0) into income_total
    from public.incomes i where i.period_id = p_period_id;

    select coalesce(sum(t.amount), 0) into allocated_total
    from public.transactions t
    where t.period_id = p_period_id and t.is_sink = false;

    select coalesce(sum(t.amount), 0) into savings_total
    from public.transactions t
    where t.period_id = p_period_id
      and t.is_sink = false
      and t.category_group = 'Savings';

    available := income_total - allocated_total;
    if available < 0 then
        raise exception 'A period with a deficit cannot be closed.';
    end if;

    next_cash := p.starting_cash;
    next_savings := p.total_savings + savings_total;

    if p_destination = 'Keep as Cash' then
        next_cash := next_cash + available;
    elsif p_destination = 'Add to Savings' then
        next_savings := next_savings + available;
    elsif p_destination = 'Piggy Bank' and available > 0 then
        insert into public.transactions (
            period_id, category_group, category_name, amount, is_sink
        ) values (
            p_period_id, 'Sink', 'Piggy Bank', available, true
        );
    end if;

    update public.financial_periods fp
    set is_closed = true,
        closed_at = now(),
        ending_cash = next_cash,
        total_savings = next_savings
    where fp.id = p_period_id;

    return query select p_period_id, next_cash, next_savings, available, savings_total;
end
$$;

-- The browser-facing roles receive no direct table or function access.
alter table public.users enable row level security;
alter table public.financial_periods enable row level security;
alter table public.incomes enable row level security;
alter table public.budgets enable row level security;
alter table public.transactions enable row level security;
alter table public.period_notes enable row level security;

revoke all on table public.users from anon, authenticated;
revoke all on table public.financial_periods from anon, authenticated;
revoke all on table public.incomes from anon, authenticated;
revoke all on table public.budgets from anon, authenticated;
revoke all on table public.transactions from anon, authenticated;
revoke all on table public.period_notes from anon, authenticated;

revoke execute on function public.close_financial_period(uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.close_financial_period(uuid, uuid, text) to service_role;
