-- model: dim_users
-- description: Staging dimension table for users
-- sources: {{ source('raw', 'users') }}

with source_data as (
    select
        `User-ID`,
        `Location`,
        `Age`
    from {{ source('raw', 'users') }}
),

transformed_data as (
    select
        cast(`User-ID` as int) as user_id,
        trim(`Location`) as location_raw,
        cast(`Age` as int) as age,
        case
            when `Age` < 18 then 'Under 18'
            when `Age` between 18 and 25 then '18-25'
            when `Age` between 26 and 40 then '26-40'
            when `Age` > 40 then '40+'
            else 'Unknown'
        end as age_group
    from source_data
)

select
    user_id,
    location_raw,
    age,
    age_group
from transformed_data