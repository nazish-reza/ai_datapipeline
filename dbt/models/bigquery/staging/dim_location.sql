-- model: dim_location
-- description: Staging dimension table for locations with surrogate key and parsed city, state, country from raw users data
-- sources: {{ source('raw', 'users') }}

WITH raw_users AS (
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
    FROM raw_users
)

SELECT
    location_id,
    city,
    state,
    country
FROM transformed