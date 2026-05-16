-- model: dim_books
-- description: Staging dimension table for books
-- sources: {{ source('raw', 'books') }}
-- refs: none

WITH raw_books AS (
    SELECT * FROM {{ source('raw', 'books') }}
),

transformed_books AS (
    SELECT
        cast(ISBN as string) as book_id,
        trim(`Book-Title`) as title,
        initcap(trim(`Book-Author`)) as author_name,
        nullif(`Year-Of-Publication`, 0) as publication_year,
        trim(Publisher) as publisher_name,
        `Image-URL-S` as image_small,
        `Image-URL-M` as image_medium,
        `Image-URL-L` as image_large
    FROM raw_books
)

SELECT * FROM transformed_books