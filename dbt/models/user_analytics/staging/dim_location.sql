```sql
{{ config( materialized='table' ) }}

-- Model: dim_location
-- Description: Location dimension table with city, state, country
-- Inputs: {{ source('raw', 'users') }}

with

-- import CTEs
users as (
    select * from {{ source('raw', 'users') }}
),

-- logical CTEs
transformed as (
    select
        dense_rank() over (order by location) as location_id,
        trim(split(location, ',')[SAFE_OFFSET(0)]) as city,
        trim(split(location, ',')[SAFE_OFFSET(1)]) as state,
        trim(split(location, ',')[SAFE_OFFSET(2)]) as country
    from users
    where location is not null
    qualify row_number() over (partition by location) = 1
),

-- final select
final as (
    select * from transformed
)

select * from final
```