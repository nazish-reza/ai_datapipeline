/*
  Model: fact_book_ratings
  Description: Fact table containing book ratings with derived categories
  Source tables: raw.ratings
*/

with raw_ratings as (
    select * from {{ source('raw', 'ratings') }}
),

transformed_ratings as (
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
    from raw_ratings
)

select * from transformed_ratings