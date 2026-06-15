-- DDL for dim_books
-- Project: genuine-arena-458814-u7 | Dataset: books_stg
CREATE TABLE IF NOT EXISTS `genuine-arena-458814-u7.books_stg.dim_books` (
  book_id                             STRING NOT NULL,
  title                               STRING NOT NULL,
  author_name                         STRING NOT NULL,
  publication_year                    INT64,
  publisher_name                      STRING,
  image_small                         STRING,
  image_medium                        STRING,
  image_large                         STRING
);