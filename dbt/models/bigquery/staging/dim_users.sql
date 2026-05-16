-- model: dim_users
-- description: Dimension table for users with cleaned and transformed fields
-- sources: {{ source('raw', 'users') }}
-- refs: none

WITH source_data AS (
    SELECT
        `User-ID`,
        `Location`,
        `Age`
    FROM {{ source('raw', 'users') }}
),

transformed_data AS (
    SELECT
        CAST(`User-ID` AS INT) AS user_id,
        TRIM(`Location`) AS location_raw,
        CAST(`Age` AS INT) AS age,
        CASE
            WHEN `Age` < 18 THEN 'Under 18'
            WHEN `Age` BETWEEN 18 AND 25 THEN '18-25'
            WHEN `Age` BETWEEN 26 AND 40 THEN '26-40'
            WHEN `Age` > 40 THEN '40+'
            ELSE 'Unknown'
        END AS age_group
    FROM source_data
)

SELECT
    user_id,
    location_raw,
    age,
    age_group
FROM transformed_data