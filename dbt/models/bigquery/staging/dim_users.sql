/*
  Model: dim_users
  Description: Staging dimension table for users
  Sources:
    - {{ source('raw', 'users') }}
*/

WITH raw_users AS (
  SELECT * FROM {{ source('raw', 'users') }}
),

users_transformed AS (
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
  FROM raw_users
)

SELECT
  user_id,
  location_raw,
  age,
  age_group
FROM users_transformed