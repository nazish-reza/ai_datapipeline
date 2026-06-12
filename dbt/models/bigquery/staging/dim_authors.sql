```sql
{{ config( materialized='table' ) }}

-- Model: dim_authors
-- Description: Dimension table with one row per distinct author from books data
-- Inputs: {{ source('raw', 'books') }}

with

-- import CTEs
books as (
  select * from {{ source('raw', 'books') }}
),

-- logical CTEs
transformed as (
  select
    dense_rank() over (order by author_name) as author_id,
    author_name
  from (
    select
      distinct trim(`Book-Author`) as author_name
    from books
    where trim(`Book-Author`) is not null
  )
),

-- final select
final as (
  select
    author_id,
    author_name
  from transformed
)

select * from final
```