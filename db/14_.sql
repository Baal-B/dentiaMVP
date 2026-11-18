alter table profiles
  add column if not exists notify_articles boolean not null default true,
  add column if not exists notify_events   boolean not null default true;
grant select (notify_articles, notify_events), update (notify_articles, notify_events) on profiles to authenticated;
notify pgrst, 'reload schema';