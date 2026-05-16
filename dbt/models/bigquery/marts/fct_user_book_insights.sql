-- Model: fct_user_book_insights
-- Description: Fact table capturing user-book interactions with derived insights such as age groups, average ratings, and rating deviations.
-- Sources: {{ source('raw', 'ratings') }}
-- Refs: {{ ref('dim_users') }}, {{ ref('dim_books') }}

WITH
ratings AS (
    SELECT
        `User-ID` AS user_id,
        ISBN AS book_id,
        `Book-Rating` AS book_rating
    FROM {{ source('raw', 'ratings') }}
),

users AS (
    SELECT * FROM {{ ref('dim_users') }}
),

books AS (
    SELECT * FROM {{ ref('dim_books') }}
),

transformed AS (
    SELECT
        u.user_id,
        b.book_id,
        b.author_name,
        b.publisher_name,
        r.book_rating,
        u.age,
        u.location,
        CASE
            WHEN u.age < 18 THEN 'Under 18'
            WHEN u.age BETWEEN 18 AND 25 THEN '18-25'
            WHEN u.age BETWEEN 26 AND 40 THEN '26-40'
            WHEN u.age > 40 THEN '40+'
            ELSE 'Unknown'
        END AS user_age_group,
        SPLIT(u.location, ',')[SAFE_OFFSET(2)] AS user_location_country,
        CASE WHEN r.book_rating >= 8 THEN 1 ELSE 0 END AS high_rating_flag,
        AVG(r.book_rating) OVER (PARTITION BY u.user_id) AS avg_user_rating,
        AVG(r.book_rating) OVER (PARTITION BY b.book_id) AS avg_book_rating,
        r.book_rating - AVG(r.book_rating) OVER (PARTITION BY b.book_id) AS rating_deviation
    FROM ratings r
    JOIN users u ON r.user_id = u.user_id
    JOIN books b ON r.book_id = b.book_id
)

SELECT
    ROW_NUMBER() OVER () AS insight_id,
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
FROM transformed