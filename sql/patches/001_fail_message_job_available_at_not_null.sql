-- Apply in Supabase → SQL Editor if message_jobs.fail_message_job sets available_at to NULL
-- (column is NOT NULL — dead_letter rows must keep a timestamp).
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
        when next_attempt >= p_max_attempts then now()
        else now() + make_interval(secs => p_retry_delay_seconds * next_attempt)
      end
  where id = p_job_id
  returning * into job_row;

  return job_row;
end;
$$;
