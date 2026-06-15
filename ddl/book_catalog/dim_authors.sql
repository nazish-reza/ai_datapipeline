-- DDL for dim_authors
-- Project: genuine-arena-458814-u7 | Dataset: books_stg
CREATE TABLE IF NOT EXISTS `genuine-arena-458814-u7.books_stg.dim_authors` (
  author_id                           INT64 NOT NULL,
  author_name                         STRING NOT NULL
);