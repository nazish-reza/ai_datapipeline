/*
  model: dim_location
  description: Dimension table for location data extracted from users table
  sources:
    - raw.users
*/

with source_data as (
  select distinct Location
  from {{ source('raw', 'users') }}
),

transformed as (
  select
    dense_rank() over(order by Location) as location_id,
    split(Location, ',')[SAFE_OFFSET(0)] as city,
    split(Location, ',')[SAFE_OFFSET(1)] as state,
    split(Location, ',')[SAFE_OFFSET(2)] as country
  from source_data
)

select * from transformed