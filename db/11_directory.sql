alter table profiles add column if not exists practice_city   text not null default '';
alter table profiles add column if not exists booking_listed  boolean not null default false;
grant update (practice_city, booking_listed) on profiles to authenticated;