-- model: dim_authors
-- description: Dimension table for authors
-- sources: {{ source('raw', 'books') }}

WITH raw_books AS (
    SELECT
        `Book-Author`
    FROM {{ source('raw', 'books') }}
),

clean_authors AS (
    SELECT
        DISTINCT TRIM(`Book-Author`) AS author_name
    FROM raw_books
    WHERE TRIM(`Book-Author`) IS NOT NULL
),

final AS (
    SELECT
        DENSE_RANK() OVER (ORDER BY author_name) AS author_id,
        author_name
    FROM clean_authors
)

SELECT
    author_id,
    author_name
FROM final