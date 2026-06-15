{{ config( materialized='table' ) }}

-- Model: fact_book_ratings
-- Description: Fact table of book ratings by users
-- Inputs: ref('dim_users'), ref('dim_books'), source('raw', 'ratings')

with

-- import CTEs
dim_users as (
  select * from {{ ref('dim_users') }}
),

dim_books as (
  select * from {{ ref('dim_books') }}
),

ratings as (
  select * from {{ source('raw', 'ratings') }}
),

-- logical CTEs
cleaned_ratings as (
  select
    safe_cast(`User-ID` as int64) as user_id,
    safe_cast(`Book-ID` as int64) as book_id,
    safe_cast(`Rating` as int64) as rating,
    `_loaded_at` as load_timestamp
  from ratings
),

joined as (
  select
    cr.user_id,
    cr.book_id,
    cr.rating,
    cr.load_timestamp
  from cleaned_ratings cr
  join dim_users du on cr.user_id = du.user_id
  join dim_books db on cr.book_id = db.book_id
),

transformed as (
  select
    row_number() over () as rating_id,
    user_id,
    book_id,
    rating,
    case
      when rating between 0 and 3 then 'low'
      when rating between 4 and 6 then 'medium'
      when rating between 7 and 8 then 'high'
      when rating between 9 and 10 then 'very_high'
      else 'unknown'
    end as rating_category,
    safe_cast(load_timestamp as date) as rating_date
  from joined
),

final as (
  select
    rating_id,
    user_id,
    book_id,
    rating,
    rating_category,
    rating_date
  from transformed
)

select * from final