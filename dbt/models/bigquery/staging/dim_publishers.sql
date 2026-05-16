/*
  Model: dim_publishers
  Description: Dimension table for publishers

  Sources:
    - {{ source('raw', 'books') }}
*/

with raw_books as (
    select
        "Publisher"
    from {{ source('raw', 'books') }}
),

distinct_publishers as (
    select
        distinct trim("Publisher") as publisher_name
    from raw_books
)

select
    dense_rank() over(order by publisher_name) as publisher_id,
    publisher_name
from distinct_publishers