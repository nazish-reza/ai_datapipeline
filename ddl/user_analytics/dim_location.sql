-- DDL for dim_location
-- Project: genuine-arena-458814-u7 | Dataset: books_stg
CREATE TABLE IF NOT EXISTS `genuine-arena-458814-u7.books_stg.dim_location` (
  location_id                         INT64 NOT NULL,
  city                                STRING,
  state                               STRING,
  country                             STRING
);