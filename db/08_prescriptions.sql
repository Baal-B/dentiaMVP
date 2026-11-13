-- header details printed on the prescription
alter table profiles add column if not exists license_number   text not null default '';
alter table profiles add column if not exists practice_name    text not null default '';
alter table profiles add column if not exists practice_address text not null default '';
alter table profiles add column if not exists practice_phone   text not null default '';
grant update (license_number, practice_name, practice_address, practice_phone) on profiles to authenticated;

-- accent-insensitive text for searching
create or replace function norm_text(t text) returns text language sql immutable as $$
  select translate(replace(lower(coalesce(t, '')), 'œ', 'oe'),
                   'àâäáãéèêëíìîïóòôöõúùûüýÿç', 'aaaaaeeeeiiiiooooouuuuyyc')
$$;

-- medication catalogue: doctor_id null = shared catalogue, otherwise the doctor's own additions
create table medications (
  id          uuid primary key default gen_random_uuid(),
  doctor_id   uuid references profiles (id) on delete cascade,
  cis         text unique,                    -- BDPM identifier (null for custom entries)
  name        text not null,
  form        text not null default '',
  routes      text not null default '',
  ingredients text not null default '',
  source      text not null default 'custom' check (source in ('seed', 'bdpm', 'custom')),
  search      text not null default '',
  created_at  timestamptz not null default now()
);
create index on medications (doctor_id);

create function medications_search() returns trigger language plpgsql as $$
begin
  new.search = norm_text(new.name || ' ' || new.ingredients);
  return new;
end $$;
create trigger medications_search before insert or update on medications
  for each row execute function medications_search();

-- the doctor's own reusable prescriptions
create table rx_templates (
  id         uuid primary key default gen_random_uuid(),
  doctor_id  uuid not null references profiles (id) on delete cascade,
  name       text not null,
  lines      jsonb not null default '[]',
  created_at timestamptz not null default now()
);
create index on rx_templates (doctor_id);

create table prescriptions (
  id         uuid primary key default gen_random_uuid(),
  doctor_id  uuid not null,
  patient_id uuid not null,
  content    jsonb not null default '{"lines": [], "notes": ""}',
  status     text not null default 'draft' check (status in ('draft', 'signed')),
  signed_at  timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (status = 'draft' or signed_at is not null),
  foreign key (patient_id, doctor_id) references patients (id, doctor_id) on delete cascade
);
create index on prescriptions (doctor_id, patient_id);

-- same rule as reports: a signed prescription is frozen
create function prescriptions_lock() returns trigger language plpgsql as $$
begin
  if old.status = 'signed' then
    raise exception 'a signed prescription cannot be changed or deleted';
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
create trigger prescriptions_lock before update or delete on prescriptions
  for each row execute function prescriptions_lock();
create trigger audit_prescriptions after insert or update or delete on prescriptions
  for each row execute function log_change();

-- access rules
revoke all on medications, rx_templates, prescriptions from anon, authenticated;
alter table medications   enable row level security;
alter table rx_templates  enable row level security;
alter table prescriptions enable row level security;

grant select, insert, update, delete on medications, rx_templates, prescriptions to authenticated;

create policy meds_select on medications for select to authenticated
  using (doctor_id is null or doctor_id = (select auth.uid()));
create policy meds_insert on medications for insert to authenticated
  with check (doctor_id = (select auth.uid()) and source = 'custom');
create policy meds_update on medications for update to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()) and source = 'custom');
create policy meds_delete on medications for delete to authenticated
  using (doctor_id = (select auth.uid()));

create policy rx_templates_own on rx_templates for all to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()));
create policy prescriptions_own on prescriptions for all to authenticated
  using (doctor_id = (select auth.uid())) with check (doctor_id = (select auth.uid()));

-- starter list so the page works before importing the real catalogue. Names only: NOT a recommendation.
insert into medications (name, form, ingredients, source)
select v.name, v.form, v.ingredients, 'seed'
from (values
  ('Amoxicilline', 'gélule / comprimé', 'amoxicilline'),
  ('Amoxicilline + acide clavulanique', 'comprimé / sachet', 'amoxicilline + acide clavulanique'),
  ('Clindamycine', 'gélule', 'clindamycine'),
  ('Métronidazole', 'comprimé', 'métronidazole'),
  ('Spiramycine + métronidazole', 'comprimé', 'spiramycine + métronidazole'),
  ('Azithromycine', 'comprimé', 'azithromycine'),
  ('Paracétamol', 'comprimé / sachet', 'paracétamol'),
  ('Ibuprofène', 'comprimé', 'ibuprofène'),
  ('Kétoprofène', 'comprimé / gélule', 'kétoprofène'),
  ('Naproxène', 'comprimé', 'naproxène'),
  ('Tramadol', 'comprimé / gélule', 'tramadol'),
  ('Paracétamol + codéine', 'comprimé', 'paracétamol + codéine'),
  ('Prednisolone', 'comprimé', 'prednisolone'),
  ('Chlorhexidine', 'bain de bouche', 'chlorhexidine')
) as v(name, form, ingredients)
where not exists (select 1 from medications where source = 'seed');