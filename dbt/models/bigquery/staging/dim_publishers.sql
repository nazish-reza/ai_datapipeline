/*
Model: dim_publishers
Description: Staging dimension table for publishers with surrogate keys
Source tables: raw.books
*/

with books as (
    select
        Publisher
    from {{ source('raw', 'books') }}
),

publishers as (
    select
        distinct trim(Publisher) as publisher_name
    from books
)

select
    dense_rank() over(order by publisher_name) as publisher_id,
    publisher_name
from publishers
order by publisher_id