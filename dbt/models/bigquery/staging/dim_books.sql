-- dim_books
-- Description: Staging dimension table for books
-- Source tables: raw.books

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