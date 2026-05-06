-- model: dim_location
-- description: Dimension table for locations extracted from user data
-- sources: {{ source('raw', 'users') }}

WITH source_users AS (
    SELECT
        Location
    FROM {{ source('raw', 'users') }}
),

transformed AS (
    SELECT
        dense_rank() over(order by Location) AS location_id,
        split(Location, ',')[SAFE_OFFSET(0)] AS city,
        split(Location, ',')[SAFE_OFFSET(1)] AS state,
        split(Location, ',')[SAFE_OFFSET(2)] AS country
    FROM source_users
)

SELECT
    location_id,
    city,
    state,
    country
FROM transformed