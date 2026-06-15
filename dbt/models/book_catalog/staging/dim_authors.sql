{{ config( materialized='table' ) }}

-- Model: dim_authors
-- Description: Staging dimension table of authors with surrogate keys
-- Inputs: source('raw', 'books')

with -- import CTEs (one per input, named after the input)
books as (
  select * from {{ source('raw', 'books') }}
),

-- logical CTEs (transformations)
distinct_authors as (
  select distinct
    trim(`author`) as author_name
  from books
),

transformed as (
  select
    dense_rank() over (order by author_name) as author_id,
    author_name
  from distinct_authors
),

-- final select
final as (
  select * from transformed
)

select * from final