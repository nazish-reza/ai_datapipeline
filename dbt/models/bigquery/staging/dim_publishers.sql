-- model: dim_publishers
-- description: Dimension table for publishers
-- sources: {{ source('raw', 'books') }}

WITH raw_books AS (
    SELECT
        Publisher
    FROM {{ source('raw', 'books') }}
),

transformations AS (
    SELECT DISTINCT
        trim(Publisher) AS publisher_name,
        dense_rank() over(order by trim(Publisher)) AS publisher_id
    FROM raw_books
)

SELECT
    publisher_id,
    publisher_name
FROM transformations
ORDER BY publisher_id