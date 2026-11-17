-- ============ agent runs (the journal) ============
create table agent_runs (
  id          uuid primary key default gen_random_uuid(),
  agent       text not null,                                   -- 'watch', later others
  doctor_id   uuid not null references profiles (id) on delete cascade,
  started_by  text not null default 'manual',                  -- manual | schedule
  status      text not null default 'running' check (status in ('running', 'completed', 'stopped', 'failed')),
  dry_run     boolean not null default false,
  goal        text not null default '',
  summary     text not null default '',
  model       text not null default '',
  steps       jsonb not null default '[]',                     -- one entry per step: action, args, thought, observation
  notified    int not null default 0,
  created_at  timestamptz not null default now(),
  finished_at timestamptz
);
create index on agent_runs (doctor_id, created_at desc);

revoke all on agent_runs from anon, authenticated;
alter table agent_runs enable row level security;
grant select on agent_runs to authenticated;          -- written by the backend only
create policy agent_runs_select on agent_runs for select to authenticated
  using (doctor_id = (select auth.uid()));

-- ============ conferences (used by the next step) ============
create table event_sources (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  url        text not null unique,
  active     boolean not null default true,
  created_at timestamptz not null default now()
);
create table events (
  id         uuid primary key default gen_random_uuid(),
  title      text not null,
  starts_on  date,
  ends_on    date,
  location   text not null default '',
  url        text not null unique,
  topics     text[] not null default '{}',
  source_id  uuid references event_sources (id) on delete set null,
  created_at timestamptz not null default now()
);
create index on events (starts_on);

revoke all on event_sources, events from anon, authenticated;
alter table event_sources enable row level security;  -- backend only: no grant, no policy
alter table events enable row level security;
grant select on events to authenticated;
create policy events_select on events for select to authenticated using (true);

alter table notifications drop constraint if exists notifications_kind_check;
alter table notifications add constraint notifications_kind_check
  check (kind in ('new_article', 'appointment', 'analysis_ready', 'system', 'event'));
alter table notifications add column if not exists event_id uuid references events (id) on delete set null;
create unique index if not exists notifications_user_event on notifications (user_id, event_id);