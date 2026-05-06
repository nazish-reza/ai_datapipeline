/*
  Model: dim_books
  Description: Staging dimension table for books
  Sources:
    - {{ source('raw', 'books') }}
*/

WITH source_books AS (
    SELECT * FROM {{ source('raw', 'books') }}
),

transformed AS (
    SELECT
        cast(ISBN as string) as book_id,
        trim(`Book-Title`) as title,
        initcap(trim(`Book-Author`)) as author_name,
        nullif(`Year-Of-Publication`, 0) as publication_year,
        trim(Publisher) as publisher_name,
        `Image-URL-S` as image_small,
        `Image-URL-M` as image_medium,
        `Image-URL-L` as image_large
    FROM source_books
)

SELECT * FROM transformed