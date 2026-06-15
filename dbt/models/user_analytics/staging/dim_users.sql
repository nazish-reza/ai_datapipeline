```sql
{{ config( materialized='table' ) }}

-- Model: dim_users
-- Description: User dimension table with cleaned and derived fields
-- Inputs: source('raw', 'users')

with

-- import CTEs
users as (
  select * from {{ source('raw', 'users') }}
),

-- logical CTEs
transformed as (
  select
    safe_cast(`User-ID` as int64) as user_id,
    trim(`Location`) as location_raw,
    safe_cast(`Age` as int64) as age,
    case
      when safe_cast(`Age` as int64) < 18 then 'under_18'
      when safe_cast(`Age` as int64) between 18 and 24 then '18-24'
      when safe_cast(`Age` as int64) between 25 and 34 then '25-34'
      when safe_cast(`Age` as int64) between 35 and 44 then '35-44'
      when safe_cast(`Age` as int64) between 45 and 54 then '45-54'
      when safe_cast(`Age` as int64) between 55 and 64 then '55-64'
      when safe_cast(`Age` as int64) >= 65 then '65_plus'
      else 'unknown'
    end as age_group
  from users
),

-- final select
final as (
  select * from transformed
)

select * from final
```