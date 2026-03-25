create extension if not exists pgcrypto;

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  agents_used text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists conversations_user_created_idx on conversations(user_id, created_at desc);

create table if not exists user_profiles (
  user_id bigint primary key,
  username text,
  stack jsonb not null default '[]'::jsonb,
  skill_level text not null default 'intermediate',
  current_projects jsonb not null default '[]'::jsonb,
  preferences jsonb not null default '{}'::jsonb,
  summary text,
  active_context jsonb not null default '{}'::jsonb,
  last_seen timestamptz,
  last_context_refresh timestamptz,
  message_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists message_jobs (
  id uuid primary key default gen_random_uuid(),
  telegram_update_id bigint not null unique,
  user_id bigint not null,
  chat_id bigint not null,
  raw_update jsonb not null,
  status text not null default 'queued' check (status in ('queued', 'running', 'retrying', 'completed', 'dead_letter')),
  pipeline jsonb,
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  locked_at timestamptz,
  locked_by text,
  error text,
  result_preview text,
  status_message_id bigint,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists message_jobs_claim_idx on message_jobs(status, available_at, created_at);

drop trigger if exists conversations_set_updated_at on conversations;
create trigger conversations_set_updated_at
before update on conversations
for each row
execute function set_updated_at();

drop trigger if exists user_profiles_set_updated_at on user_profiles;
create trigger user_profiles_set_updated_at
before update on user_profiles
for each row
execute function set_updated_at();

drop trigger if exists message_jobs_set_updated_at on message_jobs;
create trigger message_jobs_set_updated_at
before update on message_jobs
for each row
execute function set_updated_at();

create or replace function enqueue_message_job(
  p_telegram_update_id bigint,
  p_user_id bigint,
  p_chat_id bigint,
  p_raw_update jsonb
)
returns message_jobs
language plpgsql
security definer
as $$
declare
  job_row message_jobs;
begin
  insert into message_jobs (
    telegram_update_id,
    user_id,
    chat_id,
    raw_update,
    status,
    available_at
  )
  values (
    p_telegram_update_id,
    p_user_id,
    p_chat_id,
    p_raw_update,
    'queued',
    now()
  )
  on conflict (telegram_update_id) do update
    set raw_update = excluded.raw_update,
        user_id = excluded.user_id,
        chat_id = excluded.chat_id
  returning * into job_row;

  return job_row;
end;
$$;

create or replace function claim_message_jobs(
  p_worker_id text,
  p_limit integer default 1,
  p_lock_timeout_seconds integer default 300
)
returns setof message_jobs
language plpgsql
security definer
as $$
begin
  return query
  with candidates as (
    select id
    from message_jobs
    where (
      (status in ('queued', 'retrying') and coalesce(available_at, now()) <= now())
      or (status = 'running' and locked_at is not null and locked_at < now() - make_interval(secs => p_lock_timeout_seconds))
    )
    order by created_at
    for update skip locked
    limit p_limit
  ),
  updated as (
    update message_jobs
    set status = 'running',
        locked_by = p_worker_id,
        locked_at = now(),
        started_at = coalesce(started_at, now()),
        error = null
    where id in (select id from candidates)
    returning *
  )
  select * from updated;
end;
$$;

create or replace function complete_message_job(
  p_job_id uuid,
  p_result_preview text
)
returns message_jobs
language plpgsql
security definer
as $$
declare
  job_row message_jobs;
begin
  update message_jobs
  set status = 'completed',
      result_preview = p_result_preview,
      locked_at = null,
      locked_by = null,
      completed_at = now(),
      error = null
  where id = p_job_id
  returning * into job_row;

  return job_row;
end;
$$;

create or replace function fail_message_job(
  p_job_id uuid,
  p_error text,
  p_max_attempts integer default 3,
  p_retry_delay_seconds integer default 30
)
returns message_jobs
language plpgsql
security definer
as $$
declare
  job_row message_jobs;
  next_attempt integer;
begin
  select * into job_row from message_jobs where id = p_job_id for update;
  next_attempt := coalesce(job_row.attempts, 0) + 1;

  update message_jobs
  set attempts = next_attempt,
      error = p_error,
      locked_at = null,
      locked_by = null,
      status = case when next_attempt >= p_max_attempts then 'dead_letter' else 'retrying' end,
      available_at = case
        when next_attempt >= p_max_attempts then null
        else now() + make_interval(secs => p_retry_delay_seconds * next_attempt)
      end
  where id = p_job_id
  returning * into job_row;

  return job_row;
end;
$$;
