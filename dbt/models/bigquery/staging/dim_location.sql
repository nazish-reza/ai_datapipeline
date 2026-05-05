/*
  Model: dim_location
  Description: Dimension table for location data extracted from users table
  Source Tables: users
*/

with users as (
  select * from {{ source('raw', 'users') }}
),

dim_location as (
  select distinct
    dense_rank() over(order by Location) as location_id,
    split(Location, ',')[SAFE_OFFSET(0)] as city,
    split(Location, ',')[SAFE_OFFSET(1)] as state,
    split(Location, ',')[SAFE_OFFSET(2)] as country
  from users
)

select * from dim_location