```sql
{{ config( materialized='table' ) }}

-- Model: dim_books
-- Description: Staging dimension table for books
-- Inputs: {{ source('raw', 'books') }}

with
-- import CTEs
books as (
  select * from {{ source('raw', 'books') }}
),
-- logical CTEs
transformed as (
  select
    safe_cast(ISBN as string) as book_id,
    trim(`Book-Title`) as title,
    initcap(trim(`Book-Author`)) as author_name,
    nullif(`Year-Of-Publication`, 0) as publication_year,
    trim(Publisher) as publisher_name,
    `Image-URL-S` as image_small,
    `Image-URL-M` as image_medium,
    `Image-URL-L` as image_large
  from books
),
-- final select
final as (
  select * from transformed
)

select * from final
```