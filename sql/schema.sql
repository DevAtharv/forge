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

create table if not exists account_links (
  web_user_id text primary key,
  workspace_user_id bigint not null,
  web_email text,
  telegram_user_id bigint not null unique,
  telegram_username text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists account_links_workspace_idx on account_links(workspace_user_id);

create table if not exists link_tokens (
  code text primary key,
  web_user_id text not null,
  workspace_user_id bigint not null,
  web_email text,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  telegram_user_id bigint,
  telegram_username text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists link_tokens_web_user_idx on link_tokens(web_user_id, created_at desc);
create index if not exists link_tokens_expires_idx on link_tokens(expires_at);

create table if not exists oauth_connections (
  id uuid primary key default gen_random_uuid(),
  workspace_user_id bigint not null,
  provider text not null check (provider in ('github', 'vercel')),
  account_id text not null,
  account_name text,
  access_token_encrypted text not null,
  refresh_token_encrypted text,
  expires_at timestamptz,
  scopes jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_user_id, provider)
);

create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  workspace_user_id bigint not null,
  name text not null,
  slug text not null,
  prompt text not null,
  archetype text not null,
  repo_owner text,
  repo_name text,
  repo_url text,
  default_branch text not null default 'main',
  latest_manifest jsonb not null default '{}'::jsonb,
  deployment_metadata jsonb not null default '{}'::jsonb,
  latest_preview text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_user_id, slug)
);

create table if not exists project_revisions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  workspace_user_id bigint not null,
  mission_id uuid,
  summary text not null,
  file_manifest jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists deployments (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  workspace_user_id bigint not null,
  provider text not null check (provider in ('vercel')),
  status text not null,
  deployment_url text,
  external_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists missions (
  id uuid primary key default gen_random_uuid(),
  workspace_user_id bigint not null,
  chat_id bigint,
  source text not null check (source in ('telegram', 'web')),
  kind text not null check (kind in ('build', 'deploy', 'edit', 'status')),
  status text not null check (status in ('queued', 'planning', 'building', 'reviewing', 'deploying', 'awaiting_approval', 'completed', 'failed')),
  prompt text not null,
  project_id uuid references projects(id) on delete set null,
  plan jsonb not null default '{}'::jsonb,
  result_summary text,
  response_text text,
  repo_url text,
  deployment_url text,
  changed_files jsonb not null default '[]'::jsonb,
  approval_request jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists oauth_connections_user_provider_idx on oauth_connections(workspace_user_id, provider);
create index if not exists projects_user_updated_idx on projects(workspace_user_id, updated_at desc);
create index if not exists project_revisions_project_created_idx on project_revisions(project_id, created_at desc);
create index if not exists deployments_project_created_idx on deployments(project_id, created_at desc);
create index if not exists missions_claim_idx on missions(status, created_at);

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

drop trigger if exists account_links_set_updated_at on account_links;
create trigger account_links_set_updated_at
before update on account_links
for each row
execute function set_updated_at();

drop trigger if exists link_tokens_set_updated_at on link_tokens;
create trigger link_tokens_set_updated_at
before update on link_tokens
for each row
execute function set_updated_at();

drop trigger if exists oauth_connections_set_updated_at on oauth_connections;
create trigger oauth_connections_set_updated_at
before update on oauth_connections
for each row
execute function set_updated_at();

drop trigger if exists projects_set_updated_at on projects;
create trigger projects_set_updated_at
before update on projects
for each row
execute function set_updated_at();

drop trigger if exists deployments_set_updated_at on deployments;
create trigger deployments_set_updated_at
before update on deployments
for each row
execute function set_updated_at();

drop trigger if exists missions_set_updated_at on missions;
create trigger missions_set_updated_at
before update on missions
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

create or replace function create_link_token(
  p_web_user_id text,
  p_workspace_user_id bigint,
  p_web_email text,
  p_expires_in_seconds integer default 600
)
returns link_tokens
language plpgsql
security definer
as $$
declare
  token_row link_tokens;
  generated_code text;
begin
  select *
  into token_row
  from link_tokens
  where web_user_id = p_web_user_id
    and consumed_at is null
    and expires_at > now()
  order by created_at desc
  limit 1;

  if found then
    return token_row;
  end if;

  generated_code := upper(substr(encode(gen_random_bytes(6), 'hex'), 1, 6));

  insert into link_tokens (
    code,
    web_user_id,
    workspace_user_id,
    web_email,
    expires_at
  )
  values (
    generated_code,
    p_web_user_id,
    p_workspace_user_id,
    p_web_email,
    now() + make_interval(secs => p_expires_in_seconds)
  )
  returning * into token_row;

  return token_row;
end;
$$;

create or replace function consume_link_token(
  p_code text,
  p_telegram_user_id bigint,
  p_telegram_username text
)
returns account_links
language plpgsql
security definer
as $$
declare
  token_row link_tokens;
  link_row account_links;
begin
  select *
  into token_row
  from link_tokens
  where code = upper(trim(p_code))
    and consumed_at is null
    and expires_at > now()
  for update;

  if not found then
    return null;
  end if;

  update link_tokens
  set consumed_at = now(),
      telegram_user_id = p_telegram_user_id,
      telegram_username = p_telegram_username
  where code = token_row.code;

  delete from account_links where telegram_user_id = p_telegram_user_id;

  insert into account_links (
    web_user_id,
    workspace_user_id,
    web_email,
    telegram_user_id,
    telegram_username
  )
  values (
    token_row.web_user_id,
    token_row.workspace_user_id,
    token_row.web_email,
    p_telegram_user_id,
    p_telegram_username
  )
  on conflict (web_user_id) do update
    set workspace_user_id = excluded.workspace_user_id,
        web_email = excluded.web_email,
        telegram_user_id = excluded.telegram_user_id,
        telegram_username = excluded.telegram_username
  returning * into link_row;

  return link_row;
end;
$$;

create or replace function claim_missions(
  p_worker_id text,
  p_limit integer default 1,
  p_lock_timeout_seconds integer default 300
)
returns setof missions
language plpgsql
security definer
as $$
begin
  return query
  with candidates as (
    select id
    from missions
    where (
      status = 'queued'
      or (
        status in ('planning', 'building', 'reviewing', 'deploying')
        and updated_at < now() - make_interval(secs => p_lock_timeout_seconds)
      )
    )
    order by created_at
    for update skip locked
    limit p_limit
  ),
  updated as (
    update missions
    set status = 'planning',
        plan = coalesce(plan, '{}'::jsonb) || jsonb_build_object('claimed_by', p_worker_id)
    where id in (select id from candidates)
    returning *
  )
  select * from updated;
end;
$$;
