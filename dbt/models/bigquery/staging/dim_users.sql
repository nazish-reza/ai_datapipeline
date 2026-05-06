/*
  Model: dim_users
  Description: Staging model for user dimension table
  Source Tables:
    - raw.users
*/

WITH source_users AS (
    SELECT * FROM {{ source('raw', 'users') }}
),

transformed_users AS (
    SELECT
        cast(`User-ID` as int) as user_id,
        trim(Location) as location_raw,
        cast(Age as int) as age,
        case
            when Age < 18 then 'Under 18'
            when Age between 18 and 25 then '18-25'
            when Age between 26 and 40 then '26-40'
            when Age > 40 then '40+'
            else 'Unknown'
        end as age_group
    FROM source_users
)

SELECT * FROM transformed_users