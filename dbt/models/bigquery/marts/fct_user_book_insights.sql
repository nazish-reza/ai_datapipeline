{{
  config(
    materialized='table'
  )
}}

-- Model: fct_user_book_insights
-- Description: Fact table containing user-book interaction insights with various metrics
-- Source tables: raw.users, raw.books, raw.ratings

WITH

users AS (
    SELECT * FROM {{ source('raw', 'users') }}
),

books AS (
    SELECT * FROM {{ source('raw', 'books') }}
),

ratings AS (
    SELECT * FROM {{ source('raw', 'ratings') }}
),

joined_data AS (
    SELECT
        u.`User-ID` AS user_id,
        b.ISBN AS book_id,
        b.`Book-Author` AS author_name,
        b.Publisher AS publisher_name,
        u.Age AS user_age,
        u.Location AS user_location,
        r.`Book-Rating` AS book_rating
    FROM users u
    JOIN ratings r ON u.`User-ID` = r.`User-ID`
    JOIN books b ON r.ISBN = b.ISBN
)

SELECT
    row_number() OVER() AS insight_id,
    user_id,
    book_id,
    author_name,
    publisher_name,
    CASE
        WHEN user_age < 18 THEN 'Under 18'
        WHEN user_age BETWEEN 18 AND 25 THEN '18-25'
        WHEN user_age BETWEEN 26 AND 40 THEN '26-40'
        WHEN user_age > 40 THEN '40+'
        ELSE 'Unknown'
    END AS user_age_group,
    avg(book_rating) OVER(PARTITION BY user_id) AS avg_user_rating,
    avg(book_rating) OVER(PARTITION BY book_id) AS avg_book_rating,
    book_rating - avg(book_rating) OVER(PARTITION BY book_id) AS rating_deviation,
    split(user_location, ',')[SAFE_OFFSET(2)] AS user_location_country,
    CASE WHEN book_rating >= 8 THEN 1 ELSE 0 END AS high_rating_flag
FROM joined_data