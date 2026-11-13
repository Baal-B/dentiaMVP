alter table profiles
  add column if not exists name_ar             text not null default '',
  add column if not exists title_fr            text not null default 'Médecin dentiste',
  add column if not exists title_ar            text not null default 'طبيب أسنان',
  add column if not exists extra_fr            text not null default '',
  add column if not exists extra_ar            text not null default '',
  add column if not exists practice_address_ar text not null default '',
  add column if not exists practice_email      text not null default '';

grant update (name_ar, title_fr, title_ar, extra_fr, extra_ar, practice_address_ar, practice_email)
  on profiles to authenticated;