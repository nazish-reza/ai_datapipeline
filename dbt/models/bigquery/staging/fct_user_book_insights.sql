{{ config( materialized='table' ) }}

-- Model: fct_user_book_insights
-- Description: User book rating insights with user and book metadata
-- Inputs: source('raw', 'books'), source('raw', 'ratings'), source('raw', 'users')

with

books as (
  select * from {{ source('raw', 'books') }}
),

ratings as (
  select * from {{ source('raw', 'ratings') }}
),

users as (
  select * from {{ source('raw', 'users') }}
),

transformed as (
  select
    row_number() over() as insight_id,
    u.`User-ID` as user_id,
    b.ISBN as book_id,
    b.`Book-Author` as author_name,
    b.Publisher as publisher_name,
    case
      when u.Age < 18 then 'Under 18'
      when u.Age between 18 and 25 then '18-25'
      when u.Age between 26 and 40 then '26-40'
      when u.Age > 40 then '40+'
      else 'Unknown'
    end as user_age_group,
    avg(r.`Book-Rating`) over(partition by u.`User-ID`) as avg_user_rating,
    avg(r.`Book-Rating`) over(partition by b.ISBN) as avg_book_rating,
    r.`Book-Rating` - avg(r.`Book-Rating`) over(partition by b.ISBN) as rating_deviation,
    split(u.Location, ',')[SAFE_OFFSET(2)] as user_location_country,
    case when r.`Book-Rating` >= 8 then 1 else 0 end as high_rating_flag
  from ratings r
  join users u on r.`User-ID` = u.`User-ID`
  join books b on r.ISBN = b.ISBN
),

final as (
  select * from transformed
)

select * from final