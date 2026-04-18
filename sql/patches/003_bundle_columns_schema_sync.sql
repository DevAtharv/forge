-- Sync bundle-related columns expected by Forge runtime.
-- Safe to run multiple times.

alter table if exists project_revisions
  add column if not exists bundle_name text;

alter table if exists project_revisions
  add column if not exists bundle_file_count integer not null default 0;

alter table if exists missions
  add column if not exists bundle_name text;

