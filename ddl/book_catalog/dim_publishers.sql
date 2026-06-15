-- DDL for dim_publishers
-- Project: genuine-arena-458814-u7 | Dataset: books_stg
CREATE TABLE IF NOT EXISTS `genuine-arena-458814-u7.books_stg.dim_publishers` (
  publisher_id                        INT64 NOT NULL,
  publisher_name                      STRING NOT NULL
);