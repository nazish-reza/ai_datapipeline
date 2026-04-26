{{ config(severity='warn') }}
 
SELECT *
FROM {{ ref('books_clean_stg') }}
WHERE SAFE_CAST(year_of_publication AS INT64) NOT BETWEEN 1000 AND 2025
  AND year_of_publication IS NOT NULL