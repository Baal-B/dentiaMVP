-- one notification per doctor per article (NULL article_ids stay unconstrained)
create unique index if not exists notifications_user_article on notifications (user_id, article_id);