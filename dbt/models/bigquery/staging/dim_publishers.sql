{{ config( materialized='table' ) }}

-- Model: dim_publishers
-- Description: Staging dimension table of publishers with surrogate keys
-- Inputs: {{ source('raw', 'books') }}

with

books as (
  select * from {{ source('raw', 'books') }}
),

publisher_names as (
  select
    trim(`Publisher`) as publisher_name
  from books
  group by trim(`Publisher`)
),

transformed as (
  select
    dense_rank() over(order by publisher_name) as publisher_id,
    publisher_name
  from publisher_names
),

final as (
  select * from transformed
)

select * from final