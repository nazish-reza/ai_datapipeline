{{ config( materialized='table' ) }}

-- Model: fact_book_ratings
-- Description: Staging fact table for book ratings with derived categories
-- Inputs: {{ source('raw', 'ratings') }}

with

ratings as (
  select * from {{ source('raw', 'ratings') }}
),

transformed as (
  select
    row_number() over() as rating_id,
    safe_cast(`User-ID` as int64) as user_id,
    safe_cast(ISBN as string) as book_id,
    `Book-Rating` as rating,
    case
      when `Book-Rating` >= 8 then 'High'
      when `Book-Rating` between 5 and 7 then 'Medium'
      else 'Low'
    end as rating_category,
    current_timestamp() as rating_date
  from ratings
),

final as (
  select * from transformed
)

select * from final