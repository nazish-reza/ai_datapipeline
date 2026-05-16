-- model: fact_book_ratings
-- description: Fact table containing book ratings with derived categories and timestamps
-- sources: {{ source('raw', 'ratings') }}

WITH raw_ratings AS (
    SELECT
        `User-ID`,
        ISBN,
        `Book-Rating`
    FROM {{ source('raw', 'ratings') }}
),

transformed_ratings AS (
    SELECT
        cast(`User-ID` as int) as user_id,
        cast(ISBN as string) as book_id,
        `Book-Rating` as rating,
        CASE
            WHEN `Book-Rating` >= 8 THEN 'High'
            WHEN `Book-Rating` BETWEEN 5 AND 7 THEN 'Medium'
            ELSE 'Low'
        END as rating_category,
        current_timestamp() as rating_date
    FROM raw_ratings
)

SELECT
    row_number() over() as rating_id,
    user_id,
    book_id,
    rating,
    rating_category,
    rating_date
FROM transformed_ratings