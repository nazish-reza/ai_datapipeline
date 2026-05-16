/*
model: dim_location
description: Staging dimension table for location data
sources: {{ source('raw', 'users') }}
*/

WITH raw_users AS (
    SELECT
        Location
    FROM {{ source('raw', 'users') }}
),

location_transformed AS (
    SELECT
        dense_rank() over(order by Location) as location_id,
        split(Location, ',')[SAFE_OFFSET(0)] as city,
        split(Location, ',')[SAFE_OFFSET(1)] as state,
        split(Location, ',')[SAFE_OFFSET(2)] as country
    FROM raw_users
)

SELECT
    location_id,
    city,
    state,
    country
FROM location_transformed