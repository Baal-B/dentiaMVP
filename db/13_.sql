alter table event_sources
  add column if not exists slug text,
  add column if not exists last_checked_at timestamptz,
  add column if not exists last_status text;
create unique index if not exists event_sources_slug_key on event_sources (slug);

alter table events
  add column if not exists added_by text not null default 'agent',
  add column if not exists created_by uuid references auth.users (id) on delete set null;

alter table notifications alter column article_id drop not null;

insert into event_sources (slug, name, url) values
  ('fdi', 'FDI World Dental Federation', 'https://fdiworlddental.org/all-events'),
  ('efficience', 'Efficience Summit', 'https://efficience-dentaire.fr/summit'),
  ('dentex', 'DENTEX Algérie', 'https://dentex.dz/'),
  ('ids', 'IDS Cologne', 'https://ids-cologne.de/')
on conflict (url) do update set slug = excluded.slug, name = excluded.name, active = true;

notify pgrst, 'reload schema';