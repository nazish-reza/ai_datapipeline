{{ config( materialized='table' ) }}
-- Model: fct_user_book_insights
-- Description: User-book rating insights with aggregated metrics and user demographics
-- Inputs: dim_users, dim_books, source('raw', 'ratings')

with
dim_users as (
  select * from {{ ref('dim_users') }}
),

dim_books as (
  select * from {{ ref('dim_books') }}
),

raw_ratings as (
  select * from {{ source('raw', 'ratings') }}
),

ratings_clean as (
  select
    safe_cast(`User-ID` as int64) as user_id,
    safe_cast(`Book-ID` as int64) as book_id,
    safe_cast(`Rating` as float64) as rating
  from raw_ratings
),

joined as (
  select
    rc.user_id,
    rc.book_id,
    rc.rating,
    u.age_group,
    u.location_raw,
    b.author_name,
    b.publisher_name
  from ratings_clean rc
  left join dim_users u on rc.user_id = u.user_id
  left join dim_books b on rc.book_id = b.book_id
),

transformed as (
  select
    row_number() over () as insight_id,
    user_id,
    book_id,
    author_name,
    publisher_name,
    age_group as user_age_group,
    avg(rating) over (partition by user_id) as avg_user_rating,
    avg(rating) over (partition by book_id) as avg_book_rating,
    rating - avg(rating) over (partition by book_id) as rating_deviation,
    split(location_raw, ',')[SAFE_OFFSET(1)] as user_location_country,
    case when rating >= 8 then 1 else 0 end as high_rating_flag
  from joined
),

final as (
  select * from transformed
)

select * from final