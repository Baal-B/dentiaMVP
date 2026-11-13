-- =====================================================================================
-- 02_storage.sql : private bucket for radiographs (Supabase only)
-- Run AFTER 01_schema.sql, in the same SQL Editor.
-- Convention: every file is stored at   <doctor_id>/<patient_id>/<filename>
-- so each doctor can only touch files inside their own folder.
-- NOTE: this file could not be tested outside Supabase. If a statement fails, send the error message.
-- =====================================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('radiographs', 'radiographs', false, 31457280, array['image/png', 'image/jpeg'])
on conflict (id) do nothing;

create policy "doctors read own radiographs" on storage.objects
  for select to authenticated
  using (bucket_id = 'radiographs' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "doctors upload own radiographs" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'radiographs' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "doctors delete own radiographs" on storage.objects
  for delete to authenticated
  using (bucket_id = 'radiographs' and (storage.foldername(name))[1] = (select auth.uid())::text);