/*
  dim_authors
  Staging model for author dimension table
  Source tables: books
*/

WITH source_books AS (
    SELECT
        `Book-Author`
    FROM {{ source('raw', 'books') }}
),

transformed AS (
    SELECT
        trim(`Book-Author`) as author_name,
        dense_rank() over(order by trim(`Book-Author`)) as author_id
    FROM source_books
)

SELECT DISTINCT
    author_id,
    author_name
FROM transformed