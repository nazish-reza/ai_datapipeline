-- model: dim_publishers
-- description: Dimension table for publishers
-- sources: {{ source('raw', 'books') }}

WITH source_books AS (
    SELECT
        Publisher
    FROM {{ source('raw', 'books') }}
),

transformed AS (
    SELECT DISTINCT
        TRIM(Publisher) AS publisher_name,
        DENSE_RANK() OVER (ORDER BY TRIM(Publisher)) AS publisher_id
    FROM source_books
)

SELECT
    publisher_id,
    publisher_name
FROM transformed
ORDER BY publisher_id