/*
model: dim_authors
description: Staging dimension table for authors
sources:
  - {{ source('raw', 'books') }}
*/

with
src_books as (
    select
        trim(`Book-Author`) as trimmed_author
    from {{ source('raw', 'books') }}
    where `Book-Author` is not null
),

transformations as (
    select
        dense_rank() over (order by trimmed_author) as author_id,
        trimmed_author as author_name
    from (
        select distinct trimmed_author
        from src_books
    )
)

select
    author_id,
    author_name
from transformations
order by author_id