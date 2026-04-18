-- Sync preview/deployment columns expected by Forge runtime.
-- Safe to run multiple times.

alter table if exists projects
  add column if not exists preview_url text;

alter table if exists projects
  add column if not exists preview_status text;

alter table if exists projects
  add column if not exists preview_deployment_id text;

alter table if exists projects
  add column if not exists preview_updated_at timestamptz;

alter table if exists projects
  add column if not exists preview_metadata jsonb not null default '{}'::jsonb;

alter table if exists project_revisions
  add column if not exists preview_url text;

alter table if exists project_revisions
  add column if not exists preview_status text;

alter table if exists project_revisions
  add column if not exists preview_deployment_id text;

alter table if exists project_revisions
  add column if not exists preview_metadata jsonb not null default '{}'::jsonb;

