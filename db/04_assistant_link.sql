alter table assistant_queries
  add column if not exists radiograph_id uuid references radiographs (id) on delete set null;