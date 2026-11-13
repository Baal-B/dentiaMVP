-- =====================================================================================
-- 01_schema.sql : application database for the dental platform
-- Target: Supabase (PostgreSQL 15+).
-- Run it in: Supabase dashboard -> SQL Editor -> New query -> paste everything -> Run.
--
-- What this file guarantees (enforced by the database itself, not by app code):
--   * a doctor can only see and change their OWN patients, appointments, radiographs, analyses and reports
--   * the AI's raw output (analyses.findings) cannot be edited from the browser; only the backend writes it
--   * a signed report can never be changed or deleted
--   * a doctor cannot be double-booked
--   * new accounts are always "doctor"; admins are promoted by hand (see the end of this file)
--   * every change to patients / radiographs / analyses / reports is written to audit_log
-- Synthetic patients only. Never load real patient data into this project.
-- =====================================================================================

create extension if not exists btree_gist;     -- needed for the "no double booking" rule

-- ---------- helper ----------
create or replace function set_updated_at() returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- =====================================================================================
-- TABLES
-- =====================================================================================

-- One row per login (created automatically, see the trigger below).
create table profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text not null default '',
  role        text not null default 'doctor' check (role in ('doctor', 'admin')),
  specialty   text not null default 'dentistry',
  language    text not null default 'fr' check (language in ('fr', 'en')),
  interests   text[] not null default '{}',          -- topics used for "new article" notifications
  created_at  timestamptz not null default now()
);

create table patients (
  id              uuid primary key default gen_random_uuid(),
  doctor_id       uuid not null references profiles (id),
  first_name      text not null,
  last_name       text not null,
  birth_date      date,
  sex             text check (sex in ('F', 'M', 'other')),
  phone           text,
  email           text,
  medical_history text not null default '',          -- allergies, conditions, medications (free text for now)
  is_synthetic    boolean not null default true,     -- keep true: no real patients in this project
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (id, doctor_id)        -- lets child tables prove they belong to the SAME doctor as the patient
);
create index on patients (doctor_id);
create trigger patients_updated_at before update on patients
  for each row execute function set_updated_at();

create table appointments (
  id          uuid primary key default gen_random_uuid(),
  doctor_id   uuid not null,
  patient_id  uuid not null,
  starts_at   timestamptz not null,
  ends_at     timestamptz not null,
  status      text not null default 'scheduled'
              check (status in ('scheduled', 'completed', 'cancelled', 'no_show')),
  reason      text not null default '',
  notes       text not null default '',
  created_at  timestamptz not null default now(),
  check (ends_at > starts_at),
  unique (id, doctor_id),
  foreign key (patient_id, doctor_id) references patients (id, doctor_id) on delete cascade,
  -- a doctor cannot have two scheduled appointments that overlap
  exclude using gist (doctor_id with =, tstzrange(starts_at, ends_at) with &&) where (status = 'scheduled')
);
create index on appointments (doctor_id, starts_at);

create table radiographs (
  id             uuid primary key default gen_random_uuid(),
  doctor_id      uuid not null,
  patient_id     uuid not null,
  appointment_id uuid,
  -- path inside the private "radiographs" storage bucket. It MUST be <doctor_id>/<patient_id>/<file>:
  -- the backend downloads this path with a privileged key, so it must never point into someone else's folder.
  storage_path   text not null,
  kind           text not null default 'panoramic' check (kind in ('panoramic', 'periapical', 'bitewing')),
  width          int,
  height         int,
  taken_at       date,
  created_at     timestamptz not null default now(),
  unique (id, doctor_id),
  check (storage_path like doctor_id::text || '/' || patient_id::text || '/%'),
  foreign key (patient_id, doctor_id) references patients (id, doctor_id) on delete cascade,
  foreign key (appointment_id, doctor_id) references appointments (id, doctor_id)
    on delete set null (appointment_id)
);
create index on radiographs (doctor_id, patient_id);

-- One AI analysis of one radiograph. Written by the backend only.
create table analyses (
  id                 uuid primary key default gen_random_uuid(),
  doctor_id          uuid not null,
  radiograph_id      uuid not null,
  status             text not null default 'pending' check (status in ('pending', 'completed', 'failed')),
  model_info         jsonb not null default '{}',     -- e.g. {"pathology": "best_dentex_v1.pt", "restoration": "best_kaggle_v1.pt"}
  findings           jsonb not null default '[]',     -- raw output of the vision service. Never edited.
  validation_status  text not null default 'pending' check (validation_status in ('pending', 'validated', 'rejected')),
  validated_findings jsonb,                           -- the doctor's corrected version (also useful as training feedback)
  validated_at       timestamptz,                     -- set automatically
  error              text,
  created_at         timestamptz not null default now(),
  unique (id, doctor_id),
  foreign key (radiograph_id, doctor_id) references radiographs (id, doctor_id) on delete cascade
);
create index on analyses (doctor_id, radiograph_id);

create function analyses_validation_stamp() returns trigger language plpgsql as $$
begin
  if old.validation_status = 'pending' and new.validation_status <> 'pending' then
    new.validated_at = now();
  end if;
  return new;
end $$;
create trigger analyses_stamp before update on analyses
  for each row execute function analyses_validation_stamp();

create table reports (
  id          uuid primary key default gen_random_uuid(),
  doctor_id   uuid not null,
  patient_id  uuid not null,
  analysis_id uuid,
  title       text not null default '',
  content     jsonb not null default '{}',     -- sections: findings, differential, recommendations, ...
  -- COPY of every cited source (title, doi, url, exact passage) at the time of writing. The saved report must
  -- never depend on the RAG index, which can be rebuilt later.
  citations   jsonb not null default '[]',
  status      text not null default 'draft' check (status in ('draft', 'signed')),
  signed_at   timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  check (status = 'draft' or signed_at is not null),
  foreign key (patient_id, doctor_id) references patients (id, doctor_id) on delete cascade,
  foreign key (analysis_id, doctor_id) references analyses (id, doctor_id) on delete set null (analysis_id)
);
create index on reports (doctor_id, patient_id);

-- Signing: draft -> signed sets signed_at. After that the row is frozen (no update, no delete).
-- Consequence: a patient who has a signed report cannot be deleted.
create function reports_lock() returns trigger language plpgsql as $$
begin
  if old.status = 'signed' then
    raise exception 'a signed report cannot be changed or deleted';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  if new.status = 'signed' then
    new.signed_at = now();
  end if;
  new.updated_at = now();
  return new;
end $$;
create trigger reports_lock before update or delete on reports
  for each row execute function reports_lock();

-- Questions the doctor asked the RAG assistant. Written by the backend only.
create table assistant_queries (
  id                    uuid primary key default gen_random_uuid(),
  doctor_id             uuid not null references profiles (id),
  patient_id            uuid,                      -- null for a general question
  question              text not null,
  answer                text not null default '',
  citations             jsonb not null default '[]',
  insufficient_evidence boolean not null default false,
  created_at            timestamptz not null default now(),
  foreign key (patient_id, doctor_id) references patients (id, doctor_id) on delete cascade
);
create index on assistant_queries (doctor_id, created_at desc);

-- Lightweight metadata about scientific articles, filled by the scraping job. Used for notifications and citations.
-- (The article text and embeddings live in the RAG person's vector store, not here.)
create table articles (
  id           uuid primary key default gen_random_uuid(),
  title        text not null,
  authors      text not null default '',
  journal      text,
  published_at date,
  doi          text unique,
  url          text not null unique,
  source       text not null default 'pubmed',
  topics       text[] not null default '{}',
  created_at   timestamptz not null default now()
);
create index on articles using gin (topics);

create table notifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references profiles (id) on delete cascade,
  kind        text not null check (kind in ('new_article', 'appointment', 'analysis_ready', 'system')),
  title       text not null,
  body        text not null default '',
  article_id  uuid references articles (id) on delete set null,
  link        text,
  read_at     timestamptz,
  created_at  timestamptz not null default now()
);
create index on notifications (user_id, created_at desc);

create table audit_log (
  id          bigint generated always as identity primary key,
  at          timestamptz not null default now(),
  user_id     uuid,                  -- null when the backend (service role) made the change
  action      text not null,         -- INSERT | UPDATE | DELETE
  table_name  text not null,
  record_id   uuid
);

create function log_change() returns trigger language plpgsql security definer set search_path = public as $$
declare
  rec jsonb := case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end;
begin
  insert into audit_log (user_id, action, table_name, record_id)
  values (auth.uid(), tg_op, tg_table_name, (rec ->> 'id')::uuid);
  return null;
end $$;
create trigger audit_patients    after insert or update or delete on patients    for each row execute function log_change();
create trigger audit_radiographs after insert or update or delete on radiographs for each row execute function log_change();
create trigger audit_analyses    after insert or update or delete on analyses    for each row execute function log_change();
create trigger audit_reports     after insert or update or delete on reports     for each row execute function log_change();

-- =====================================================================================
-- NEW ACCOUNTS
-- =====================================================================================
-- Every new login gets a profile. The role is ALWAYS 'doctor': it is never read from user-supplied metadata,
-- otherwise anyone could sign up as an admin.
create function handle_new_user() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''));
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function handle_new_user();

create function is_admin() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid() and role = 'admin');
$$;

-- =====================================================================================
-- ACCESS RULES
-- "authenticated" = a logged-in user in the browser. The backend uses the service role, which bypasses these rules.
-- Everything is switched off first, then only what is needed is granted back.
-- =====================================================================================
revoke all on profiles, patients, appointments, radiographs, analyses, reports,
              assistant_queries, articles, notifications, audit_log from anon, authenticated;

alter table profiles          enable row level security;
alter table patients          enable row level security;
alter table appointments      enable row level security;
alter table radiographs       enable row level security;
alter table analyses          enable row level security;
alter table reports           enable row level security;
alter table assistant_queries enable row level security;
alter table articles          enable row level security;
alter table notifications     enable row level security;
alter table audit_log         enable row level security;

-- profiles: read your own; change only harmless columns (never "role")
grant select on profiles to authenticated;
grant update (full_name, specialty, language, interests) on profiles to authenticated;
create policy profiles_select on profiles for select to authenticated
  using (id = (select auth.uid()) or is_admin());
create policy profiles_update on profiles for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- patients, appointments, radiographs, reports: full access, but only to your own rows
grant select, insert, update, delete on patients, appointments, radiographs, reports to authenticated;
create policy patients_own     on patients     for all to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()));
create policy appointments_own on appointments for all to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()));
create policy radiographs_own  on radiographs  for all to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()));
create policy reports_own      on reports      for all to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()));

-- analyses: read your own; the doctor may only validate (never edit the AI's findings, never create or delete)
grant select on analyses to authenticated;
grant update (validation_status, validated_findings) on analyses to authenticated;
create policy analyses_select on analyses for select to authenticated
  using (doctor_id = (select auth.uid()));
create policy analyses_update on analyses for update to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()));

-- assistant_queries: read your own (the backend writes them)
grant select on assistant_queries to authenticated;
create policy assistant_queries_select on assistant_queries for select to authenticated
  using (doctor_id = (select auth.uid()));

-- articles: every logged-in user can read (the scraping job writes them with the service role)
grant select on articles to authenticated;
create policy articles_select on articles for select to authenticated using (true);

-- notifications: read your own and mark them read
grant select on notifications to authenticated;
grant update (read_at) on notifications to authenticated;
create policy notifications_select on notifications for select to authenticated
  using (user_id = (select auth.uid()));
create policy notifications_update on notifications for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

-- audit_log: admins can read; nobody can write from the browser (the trigger above writes it)
grant select on audit_log to authenticated;
create policy audit_log_select on audit_log for select to authenticated using (is_admin());

-- =====================================================================================
-- AFTER YOU SIGN UP YOUR FIRST ACCOUNT: make yourself admin (SQL Editor, run once, replace the email)
--   update profiles set role = 'admin' where id = (select id from auth.users where email = 'you@example.com');
-- =====================================================================================
