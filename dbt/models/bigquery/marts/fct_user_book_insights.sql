/*
model: fct_user_book_insights
description: Fact table with user-book interaction insights including ratings, averages, and derived metrics
sources: {{ source('raw', 'ratings') }}
refs: {{ ref('dim_users') }}, {{ ref('dim_books') }}
*/

WITH raw_ratings AS (
    SELECT
        `User-ID`,
        ISBN,
        `Book-Rating`
    FROM {{ source('raw', 'ratings') }}
),

dim_users AS (
    SELECT
        user_id,
        age,
        location
    FROM {{ ref('dim_users') }}
),

dim_books AS (
    SELECT
        book_id,
        author_name,
        publisher_name
    FROM {{ ref('dim_books') }}
),

joined_data AS (
    SELECT
        r.`Book-Rating` AS book_rating,
        u.user_id,
        u.age,
        u.location,
        b.book_id,
        b.author_name,
        b.publisher_name
    FROM raw_ratings r
    JOIN dim_users u ON r.`User-ID` = u.user_id
    JOIN dim_books b ON r.ISBN = b.book_id
)

SELECT
    row_number() OVER() AS insight_id,
    user_id,
    book_id,
    author_name,
    publisher_name,
    CASE
        WHEN age < 18 THEN 'Under 18'
        WHEN age BETWEEN 18 AND 25 THEN '18-25'
        WHEN age BETWEEN 26 AND 40 THEN '26-40'
        WHEN age > 40 THEN '40+'
        ELSE 'Unknown'
    END AS user_age_group,
    AVG(book_rating) OVER(PARTITION BY user_id) AS avg_user_rating,
    AVG(book_rating) OVER(PARTITION BY book_id) AS avg_book_rating,
    book_rating - AVG(book_rating) OVER(PARTITION BY book_id) AS rating_deviation,
    split(location, ',')[SAFE_OFFSET(2)] AS user_location_country,
    CASE WHEN book_rating >= 8 THEN 1 ELSE 0 END AS high_rating_flag
FROM joined_data