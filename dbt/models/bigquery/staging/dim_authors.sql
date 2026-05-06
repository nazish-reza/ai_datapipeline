/*
  model: dim_authors
  description: Staging dimension table for authors
  sources:
    - raw.books
*/

with raw_books as (
    select
        `Book-Author`
    from {{ source('raw', 'books') }}
),

transformed as (
    select distinct
        dense_rank() over (order by trim(`Book-Author`)) as author_id,
        trim(`Book-Author`) as author_name
    from raw_books
)

select
    author_id,
    author_name
from transformed
order by author_id