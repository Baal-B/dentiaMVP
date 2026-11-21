alter table appointments add column if not exists reminder_sent_at timestamptz;

-- the only thing n8n may read: tomorrow's scheduled appointments of patients who have an email
create view reminder_due as
select a.id as appointment_id, a.starts_at, p.first_name, p.email,
       pr.practice_name, pr.practice_phone
from appointments a
join patients p  on p.id = a.patient_id and p.doctor_id = a.doctor_id
join profiles pr on pr.id = a.doctor_id
where a.status = 'scheduled'
  and a.reminder_sent_at is null
  and coalesce(p.email, '') <> ''
  and a.starts_at >= (date_trunc('day', now() at time zone 'Africa/Tunis') + interval '1 day') at time zone 'Africa/Tunis'
  and a.starts_at <  (date_trunc('day', now() at time zone 'Africa/Tunis') + interval '2 days') at time zone 'Africa/Tunis';

create function mark_reminder_sent(p_id uuid) returns void
language sql security definer set search_path = public as $$
  update appointments set reminder_sent_at = now() where id = p_id
$$;

revoke all on reminder_due from anon, authenticated;
revoke all on function mark_reminder_sent(uuid) from public, anon, authenticated;

create role n8n_reminders login password 'place_holder_password';
grant usage on schema public to n8n_reminders;
grant select on reminder_due to n8n_reminders;
grant execute on function mark_reminder_sent(uuid) to n8n_reminders;