-- dim_authors: staging dimension table for authors
-- source: {{ source('raw', 'books') }}

WITH source_books AS (
    SELECT
        `Book-Author`
    FROM {{ source('raw', 'books') }}
),

transformations AS (
    SELECT
        dense_rank() OVER (ORDER BY trimmed_author) AS author_id,
        trimmed_author AS author_name
    FROM (
        SELECT DISTINCT
            trim(`Book-Author`) AS trimmed_author
        FROM source_books
    )
)

SELECT
    author_id,
    author_name
FROM transformations