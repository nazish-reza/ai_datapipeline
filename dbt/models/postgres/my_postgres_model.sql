{{ config(materialized='table', tags=['postgres']) }}

select
  actor_id,
  first_name,
  last_update
from {{ source('postgres_raw', 'actor') }}
