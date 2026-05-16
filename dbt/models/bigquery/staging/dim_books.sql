-- dim_books: Dimension table for books
-- Sources: {{ source('raw', 'books') }}

WITH raw_books AS (
    SELECT * FROM {{ source('raw', 'books') }}
),

transformed_books AS (
    SELECT
        CAST(ISBN AS STRING) AS book_id,
        TRIM(`Book-Title`) AS title,
        INITCAP(TRIM(`Book-Author`)) AS author_name,
        NULLIF(`Year-Of-Publication`, 0) AS publication_year,
        TRIM(Publisher) AS publisher_name,
        `Image-URL-S` AS image_small,
        `Image-URL-M` AS image_medium,
        `Image-URL-L` AS image_large
    FROM raw_books
)

SELECT
    book_id,
    title,
    author_name,
    publication_year,
    publisher_name,
    image_small,
    image_medium,
    image_large
FROM transformed_books