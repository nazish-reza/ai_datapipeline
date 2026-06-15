{{ config( materialized='table' ) }}

-- Model: dim_publishers
-- Description: Staging dimension table of distinct publishers
-- Inputs: source('raw', 'books')

with

books as (
  select * from {{ source('raw', 'books') }}
),

publisher_list as (
  select
    trim(publisher) as publisher_name
  from books
  group by 1
),

ranked_publishers as (
  select
    publisher_name,
    dense_rank() over (order by publisher_name) as publisher_id
  from publisher_list
),

final as (
  select
    publisher_id,
    publisher_name
  from ranked_publishers
)

select * from final