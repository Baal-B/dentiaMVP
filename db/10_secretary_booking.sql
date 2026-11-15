-- ============ 1. secretary role ============
alter table profiles drop constraint if exists profiles_role_check;
alter table profiles add constraint profiles_role_check check (role in ('doctor', 'admin', 'secretary'));

alter table profiles add column if not exists works_for uuid references profiles (id);
alter table profiles add constraint secretary_has_doctor check (role <> 'secretary' or works_for is not null);

-- public booking page of a doctor: /reserver/<booking_slug>
alter table profiles add column if not exists booking_slug text unique
  check (booking_slug is null or booking_slug ~ '^[a-z0-9-]{3,40}$');
alter table profiles add column if not exists booking_open boolean not null default false;
grant update (booking_slug, booking_open) on profiles to authenticated;

-- the doctor whose data the current user may work on (a doctor: themselves; a secretary: their employer)
create or replace function acting_doctor() returns uuid
language sql stable security definer set search_path = public as $$
  select case when role = 'secretary' then works_for else id end
  from profiles where id = auth.uid()
$$;
revoke all on function acting_doctor() from public, anon;
grant execute on function acting_doctor() to authenticated;

-- a secretary can read her doctor's profile (name, header), a doctor still only reads their own
drop policy profiles_select on profiles;
create policy profiles_select on profiles for select to authenticated
  using (id = (select auth.uid()) or id = (select acting_doctor()) or is_admin());

-- ============ 2. agenda: the secretary works on her doctor's appointments ============
drop policy appointments_own on appointments;
create policy appointments_own on appointments for all to authenticated
  using (doctor_id = (select acting_doctor()))
  with check (doctor_id = (select acting_doctor()));

-- ============ 3. patients: the secretary sees identity and contact only ============
-- The patients table itself stays doctor-only (its policy is unchanged), so a secretary reading it gets nothing.
-- This view leaves out medical_history and is_synthetic, and filters on acting_doctor().
create view patients_basic with (security_barrier = true) as
  select id, doctor_id, first_name, last_name, birth_date, sex, phone, email
  from patients
  where doctor_id = acting_doctor()
  with check option;

revoke all on patients_basic from anon, authenticated;
grant select, insert, update on patients_basic to authenticated;

-- ============ 4. booking requests (public form -> secretary inbox) ============
create table booking_requests (
  id             uuid primary key default gen_random_uuid(),
  doctor_id      uuid not null references profiles (id),
  first_name     text not null check (char_length(first_name) between 1 and 80),
  last_name      text not null check (char_length(last_name) between 1 and 80),
  phone          text not null check (char_length(phone) between 6 and 30),
  email          text check (email is null or char_length(email) <= 120),
  preferred_date date not null,
  preferred_slot text not null default 'any' check (preferred_slot in ('morning', 'afternoon', 'any')),
  note           text not null default '' check (char_length(note) <= 300),   -- reason only, no medical details
  status         text not null default 'pending' check (status in ('pending', 'confirmed', 'declined')),
  appointment_id uuid,
  client_hash    text,                      -- HMAC of the IP, for rate limiting (never the raw IP)
  decided_at     timestamptz,
  created_at     timestamptz not null default now(),
  foreign key (appointment_id, doctor_id) references appointments (id, doctor_id)
    on delete set null (appointment_id)
);
create index on booking_requests (doctor_id, status, created_at desc);
create index on booking_requests (client_hash, created_at);

-- a handled request is frozen
create function booking_decided() returns trigger language plpgsql as $$
begin
  if old.status <> 'pending' then
    raise exception 'this request was already handled';
  end if;
  if new.status <> 'pending' then
    new.decided_at = now();
  end if;
  return new;
end $$;
create trigger booking_decided before update on booking_requests
  for each row execute function booking_decided();

revoke all on booking_requests from anon, authenticated;
alter table booking_requests enable row level security;
grant select on booking_requests to authenticated;
grant update (status, appointment_id) on booking_requests to authenticated;
-- no INSERT grant: only the backend (service role) can create requests, after its own checks

create policy booking_select on booking_requests for select to authenticated
  using (doctor_id = (select acting_doctor()));
create policy booking_update on booking_requests for update to authenticated
  using (doctor_id = (select acting_doctor()))
  with check (doctor_id = (select acting_doctor()));

-- confirm a request in ONE transaction: create the appointment and mark the request.
-- SECURITY INVOKER (default): the caller's RLS still applies, and the overlap constraint still rejects clashes.
create function confirm_booking_request(p_request uuid, p_patient uuid, p_starts timestamptz, p_ends timestamptz)
returns uuid language plpgsql as $$
declare v_appt uuid;
begin
  insert into appointments (doctor_id, patient_id, starts_at, ends_at, reason)
  select doctor_id, p_patient, p_starts, p_ends, note
  from booking_requests where id = p_request and status = 'pending'
  returning id into v_appt;

  if v_appt is null then
    raise exception 'request not found or already handled';
  end if;

  update booking_requests set status = 'confirmed', appointment_id = v_appt where id = p_request;
  return v_appt;
end $$;
revoke all on function confirm_booking_request(uuid, uuid, timestamptz, timestamptz) from public, anon;
grant execute on function confirm_booking_request(uuid, uuid, timestamptz, timestamptz) to authenticated;