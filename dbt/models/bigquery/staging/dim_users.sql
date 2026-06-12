```sql
{{ config( materialized='table' ) }}

-- Model: dim_users
-- Description: User dimension table with cleaned user attributes
-- Inputs: {{ source('raw', 'users') }}

with

users as (
  select * from {{ source('raw', 'users') }}
),

transformed as (
  select
    SAFE_CAST(`User-ID` as int64) as user_id,
    trim(`Location`) as location_raw,
    SAFE_CAST(`Age` as int64) as age,
    case
      when SAFE_CAST(`Age` as int64) < 18 then 'Under 18'
      when SAFE_CAST(`Age` as int64) between 18 and 25 then '18-25'
      when SAFE_CAST(`Age` as int64) between 26 and 40 then '26-40'
      when SAFE_CAST(`Age` as int64) > 40 then '40+'
      else 'Unknown'
    end as age_group
  from users
),

final as (
  select * from transformed
)

select * from final
```