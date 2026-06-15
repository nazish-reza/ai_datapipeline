-- DDL for fct_user_book_insights
-- Project: genuine-arena-458814-u7 | Dataset: books_mart
CREATE TABLE IF NOT EXISTS `genuine-arena-458814-u7.books_mart.fct_user_book_insights` (
  insight_id                          INT64 NOT NULL,
  user_id                             INT64 NOT NULL,
  book_id                             STRING NOT NULL,
  author_name                         STRING,
  publisher_name                      STRING,
  user_age_group                      STRING NOT NULL,
  avg_user_rating                     FLOAT64,
  avg_book_rating                     FLOAT64,
  rating_deviation                    FLOAT64,
  user_location_country               STRING,
  high_rating_flag                    INT64 NOT NULL
);