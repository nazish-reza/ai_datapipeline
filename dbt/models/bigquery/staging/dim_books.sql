/*
  Model: dim_books
  Description: Staging dimension table for books
  Sources:
    - raw.books
*/

with raw_books as (
  select
    `ISBN`,
    `Book-Title`,
    `Book-Author`,
    `Year-Of-Publication`,
    `Publisher`,
    `Image-URL-S`,
    `Image-URL-M`,
    `Image-URL-L`
  from {{ source('raw', 'books') }}
),

transformed as (
  select
    cast(`ISBN` as string) as book_id,
    trim(`Book-Title`) as title,
    initcap(trim(`Book-Author`)) as author_name,
    nullif(`Year-Of-Publication`,0) as publication_year,
    trim(`Publisher`) as publisher_name,
    `Image-URL-S` as image_small,
    `Image-URL-M` as image_medium,
    `Image-URL-L` as image_large
  from raw_books
)

select * from transformed