-- DDL for dim_users
-- Project: genuine-arena-458814-u7 | Dataset: books_stg
CREATE TABLE IF NOT EXISTS `genuine-arena-458814-u7.books_stg.dim_users` (
  user_id                             INT64 NOT NULL,
  location_raw                        STRING,
  age                                 INT64,
  age_group                           STRING NOT NULL
);