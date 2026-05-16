/*
model: dim_publishers
description: Dimension table for publishers with surrogate keys
sources:
  - {{ source('raw', 'books') }}
*/
WITH
source_books AS (
    SELECT
        trim(Publisher) AS publisher_name
    FROM {{ source('raw', 'books') }}
),

transformations AS (
    SELECT DISTINCT
        publisher_name,
        dense_rank() over (order by publisher_name) AS publisher_id
    FROM source_books
)

SELECT
    publisher_id,
    publisher_name
FROM transformations