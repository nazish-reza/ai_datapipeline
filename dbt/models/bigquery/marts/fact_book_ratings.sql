-- model: fact_book_ratings
-- description: Fact table for book ratings including rating category and timestamp
-- sources: {{ source('raw', 'ratings') }}

with source_ratings as (
    select
        `User-ID`,
        ISBN,
        `Book-Rating`
    from {{ source('raw', 'ratings') }}
),

transformed as (
    select
        row_number() over() as rating_id,
        cast(`User-ID` as int) as user_id,
        cast(ISBN as string) as book_id,
        `Book-Rating` as rating,
        case
            when `Book-Rating` >= 8 then 'High'
            when `Book-Rating` between 5 and 7 then 'Medium'
            else 'Low'
        end as rating_category,
        current_timestamp() as rating_date
    from source_ratings
)

select
    rating_id,
    user_id,
    book_id,
    rating,
    rating_category,
    rating_date
from transformed