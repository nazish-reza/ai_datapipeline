/*
Model: fct_user_book_insights
Description: Fact table containing user-book insights including ratings, age groups, and location data
Sources:
  - {{ source('raw', 'ratings') }}
  - {{ ref('dim_users') }}
  - {{ ref('dim_books') }}
*/

with

dim_users as (
    select * from {{ ref('dim_users') }}
),

dim_books as (
    select * from {{ ref('dim_books') }}
),

raw_ratings as (
    select
        `User-ID` as user_id,
        ISBN as isbn,
        `Book-Rating` as book_rating
    from {{ source('raw', 'ratings') }}
),

final as (
    select
        row_number() over() as insight_id,
        u.user_id,
        b.isbn as book_id,
        b.book_author as author_name,
        b.publisher as publisher_name,
        case
            when u.age < 18 then 'Under 18'
            when u.age between 18 and 25 then '18-25'
            when u.age between 26 and 40 then '26-40'
            when u.age > 40 then '40+'
            else 'Unknown'
        end as user_age_group,
        avg(r.book_rating) over(partition by u.user_id) as avg_user_rating,
        avg(r.book_rating) over(partition by b.isbn) as avg_book_rating,
        r.book_rating - avg(r.book_rating) over(partition by b.isbn) as rating_deviation,
        split(u.location, ',')[SAFE_OFFSET(2)] as user_location_country,
        case when r.book_rating >= 8 then 1 else 0 end as high_rating_flag
    from dim_users u
    join raw_ratings r on u.user_id = r.user_id
    join dim_books b on b.isbn = r.isbn
)

select * from final