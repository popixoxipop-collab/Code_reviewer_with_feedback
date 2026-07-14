-- D-B (PLAN.md): "내 DB" for the team pipeline lab (docs/lab/). Run this once against a
-- fresh Supabase project (SQL Editor -> paste -> Run). Safe to re-run (IF NOT EXISTS
-- guards) except the RLS policies, which use CREATE POLICY without IF NOT EXISTS --
-- drop them first if you're re-applying this after editing a policy.

create table if not exists members (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  email text,
  created_at timestamptz not null default now()
);

create table if not exists runs (
  id uuid primary key default gen_random_uuid(),
  member_id uuid not null references members(id) on delete cascade,
  pipeline text not null check (pipeline in ('p01', 'p02', 'p03')),
  model text,
  status text not null default 'done',
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  input_meta jsonb not null default '{}'::jsonb,
  overrides jsonb not null default '{}'::jsonb,
  overrides_hash text,
  rubric_overridden boolean not null default false,
  manifest_version text,
  client_commit text,
  error text,
  created_at timestamptz not null default now()
);
create index if not exists runs_member_id_idx on runs(member_id);
create index if not exists runs_pipeline_idx on runs(pipeline);
create index if not exists runs_created_at_idx on runs(created_at desc);

create table if not exists stage_events (
  id bigserial primary key,
  run_id uuid not null references runs(id) on delete cascade,
  stage_id text not null,
  seq int not null default 0,
  resolved_prompt text,
  output jsonb,
  latency_ms int,
  error text,
  created_at timestamptz not null default now()
);
create index if not exists stage_events_run_id_idx on stage_events(run_id);

create table if not exists artifacts (
  id bigserial primary key,
  run_id uuid not null references runs(id) on delete cascade,
  kind text not null, -- unit_map | graph | questions | findings | transcript | grades
  content jsonb not null default '{}'::jsonb,
  truncated boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists artifacts_run_id_idx on artifacts(run_id);

create table if not exists presets (
  id bigserial primary key,
  member_id uuid not null references members(id) on delete cascade,
  pipeline text not null check (pipeline in ('p01', 'p02', 'p03')),
  stage_id text not null,
  name text not null,
  body jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists presets_member_id_idx on presets(member_id);

-- Auto-create a `members` row the first time someone signs in (magic link), so app
-- code never has to remember to do it and RLS below always has a matching row to check.
create or replace function public.handle_new_member()
returns trigger as $$
begin
  insert into public.members (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_member();

-- RLS: every table is readable by any authenticated team member (this is a comparison
-- tool -- PLAN.md open question 2 flags this as a decision point, change to
-- `member_id = auth.uid()` on the select policies below for owner-only visibility).
-- Writes are always restricted to your own member_id, enforced structurally (not by the
-- app remembering to filter), which is the actual point of using Supabase auth instead
-- of a free-text name field.

alter table members enable row level security;
alter table runs enable row level security;
alter table stage_events enable row level security;
alter table artifacts enable row level security;
alter table presets enable row level security;

create policy "members read all" on members for select to authenticated using (true);
create policy "members update own" on members for update to authenticated using (id = auth.uid());

create policy "runs read all" on runs for select to authenticated using (true);
create policy "runs insert own" on runs for insert to authenticated with check (member_id = auth.uid());
create policy "runs update own" on runs for update to authenticated using (member_id = auth.uid());

create policy "stage_events read all" on stage_events for select to authenticated using (true);
create policy "stage_events insert own" on stage_events for insert to authenticated
  with check (exists (select 1 from runs where runs.id = run_id and runs.member_id = auth.uid()));

create policy "artifacts read all" on artifacts for select to authenticated using (true);
create policy "artifacts insert own" on artifacts for insert to authenticated
  with check (exists (select 1 from runs where runs.id = run_id and runs.member_id = auth.uid()));

create policy "presets read all" on presets for select to authenticated using (true);
create policy "presets insert own" on presets for insert to authenticated with check (member_id = auth.uid());
create policy "presets delete own" on presets for delete to authenticated using (member_id = auth.uid());
