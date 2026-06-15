-- DDL for fact_book_ratings
-- Project: genuine-arena-458814-u7 | Dataset: books_mart
CREATE TABLE IF NOT EXISTS `genuine-arena-458814-u7.books_mart.fact_book_ratings` (
  rating_id                           INT64 NOT NULL,
  user_id                             INT64 NOT NULL,
  book_id                             STRING NOT NULL,
  rating                              INT64 NOT NULL,
  rating_category                     STRING NOT NULL,
  rating_date                         TIMESTAMP NOT NULL
);