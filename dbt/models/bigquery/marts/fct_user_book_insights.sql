/*
Model: fct_user_book_insights
Description: Fact table containing user-book insights including ratings, age groups, and derived metrics
Sources:
  - {{ source('raw', 'ratings') }}
Refs:
  - {{ ref('dim_users') }}
  - {{ ref('dim_books') }}
*/

with

ratings as (
    select
        "User-ID" as raw_user_id,
        "ISBN" as raw_book_id,
        "Book-Rating" as book_rating
    from {{ source('raw', 'ratings') }}
),

users as (
    select
        user_id,
        age,
        location
    from {{ ref('dim_users') }}
),

books as (
    select
        book_id,
        author_name,
        publisher_name
    from {{ ref('dim_books') }}
),

joined as (
    select
        r.book_rating,
        u.user_id,
        u.age,
        u.location,
        b.book_id,
        b.author_name,
        b.publisher_name
    from ratings r
    join users u on r.raw_user_id = u.user_id
    join books b on r.raw_book_id = b.book_id
),

with_window as (
    select
        *,
        avg(book_rating) over (partition by user_id) as avg_user_rating,
        avg(book_rating) over (partition by book_id) as avg_book_rating
    from joined
),

transformed as (
    select
        *,
        case
            when age < 18 then 'Under 18'
            when age between 18 and 25 then '18-25'
            when age between 26 and 40 then '26-40'
            when age > 40 then '40+'
            else 'Unknown'
        end as user_age_group,
        split(location, ',')[SAFE_OFFSET(2)] as user_location_country,
        case when book_rating >= 8 then 1 else 0 end as high_rating_flag,
        book_rating - avg_book_rating as rating_deviation
    from with_window
)

select
    row_number() over () as insight_id,
    user_id,
    book_id,
    author_name,
    publisher_name,
    user_age_group,
    avg_user_rating,
    avg_book_rating,
    rating_deviation,
    user_location_country,
    high_rating_flag
from transformed