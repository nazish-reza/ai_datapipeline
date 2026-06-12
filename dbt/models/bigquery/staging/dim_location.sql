{{ config( materialized='table' ) }}
-- Model: dim_location
-- Description: Location dimension table with city, state, and country information
-- Inputs: {{ source('raw', 'users') }}

with
-- import CTEs (one per input, named after the input)
users as (
    select * from {{ source('raw', 'users') }}
),

-- logical CTEs (transformations)
transformed as (
    select
        dense_rank() over(order by `Location`) as location_id,
        split(`Location`, ',')[SAFE_OFFSET(0)] as city,
        split(`Location`, ',')[SAFE_OFFSET(1)] as state,
        split(`Location`, ',')[SAFE_OFFSET(2)] as country
    from users
),

-- final select
final as (
    select * from transformed
)

select * from final